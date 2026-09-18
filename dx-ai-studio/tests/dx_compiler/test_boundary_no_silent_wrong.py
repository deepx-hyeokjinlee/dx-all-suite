"""조용히 틀린 답을 주느니 오류를 내는 편이 낫다.

500 보다 나쁜 것이 있다. **200 과 함께 오는 틀린 답**이다. 500 은 적어도
무언가 잘못됐다고 알려준다. 200 은 아무 말도 하지 않는데 사용자가 요청한 것과
실행된 것이 다르다.

2026-09-18 전수조사에서 실측한 네 건:

  POST /compile/{id}/calculate-exclude
      input_nodes="ab"    -> 200, 노드 a·b 두 개로 해석  (set("ab") == {'a','b'})
      input_nodes=["ab"]  -> 500  ← 진짜 의도한 형태가 터진다
      없는 노드            -> 500  ← 사용자 입력 오류인데 서버 오류로 보고
  POST /compile/{id}/resume
      input_nodes 가 아무 타입   -> 200, job 에 그대로 저장
                                  터지는 것은 한참 뒤 컴파일 중이라 추적이 어렵다
  POST /compile
      enhanced_scheme="{{{"     -> 200, 조용히 None
                                  DXQ 를 요청했는데 평범한 컴파일이 돈다

계약: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations

import json
import types
import urllib.error
import urllib.request
import uuid

import pytest

from tests.server_helpers import start_module_server


class _Tensor:
    def __init__(self, producer=None):
        self.producer = producer
        self.consumers = []


class _Node:
    def __init__(self, name):
        self.name = name
        self.inputs = []
        self.outputs = []


def _linear_graph(names):
    """a -> b -> c -> d 사슬. 이름이 한 글자인 것이 핵심이다.

    `set("ab")` 이 `{'a','b'}` 가 되어 **실재하는 노드 두 개로 보이는** 상황을
    만들 수 있어야 버그가 드러난다. 이름이 길면 글자 분해가 '없는 노드' 오류로
    가려져서 진짜 증상(조용한 200)이 안 보인다.
    """
    nodes = [_Node(n) for n in names]
    for prev, nxt in zip(nodes, nodes[1:]):
        t = _Tensor(producer=prev)
        t.consumers.append(nxt)
        prev.outputs.append(t)
        nxt.inputs.append(t)
    return types.SimpleNamespace(nodes=nodes)


@pytest.fixture()
def compiler_with_graph():
    """그래프가 준비된 job 을 심은 서버. 이 라우트들은 job 없이는 닿지 않는다."""
    server, port = start_module_server("dx_compiler")
    from dx_compiler.server import compiler_service
    job = types.SimpleNamespace(
        job_id="graphjob", status="running", paused=True,
        prepared_graph_ir=_linear_graph(["a", "b", "c", "d"]),
        pause_event=__import__("threading").Event(),
        selected_input_nodes=[], selected_output_nodes=[])
    compiler_service.jobs["graphjob"] = job
    try:
        yield f"http://127.0.0.1:{port}", job
    finally:
        compiler_service.jobs.pop("graphjob", None)
        server.shutdown()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except json.JSONDecodeError:
            return e.code, {}


class TestNodeListsAreNotStrings:
    def test_a_string_is_not_silently_split_into_letters(self, compiler_with_graph):
        """가장 고약한 놈. set("ab") == {'a','b'} 라 노드 두 개로 보인다.

        오류가 없다. 사용자는 "ab" 라는 노드 하나를 말했는데 서버는 a 와 b
        두 개로 알아듣고 200 을 돌려준다. 아무도 모른다.
        """
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude",
                           {"input_nodes": "ab"})
        assert code == 400, f"문자열이 글자로 쪼개진 채 통과했다 — {code} {body}"

    def test_the_string_message_shows_the_exact_fix(self, compiler_with_graph):
        """문자열 전용 메시지가 없으면 그냥 "리스트를 달라" 로 끝난다.

        그 말로는 "ab" 를 노드 하나로 쓰려던 사람이 무엇을 타이핑해야 하는지
        모른다. `['ab']` 을 보여줘야 한다.

        이 계약이 없으면 문자열 분기는 죽은 코드다 — 바로 아래 list 검사가
        문자열도 잡아 400 을 낸다. 변이 검사에서 그 분기만 살아남았고, 그래서
        분기가 실제로 하는 일(고치는 방법 제시)을 여기서 못박는다.
        """
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude",
                           {"input_nodes": "ab"})
        assert code == 400
        assert "['ab']" in body.get("error", ""), \
            f"무엇으로 고쳐야 하는지 보여주지 않는다 — {body}"

    def test_the_correct_form_for_one_node_is_accepted(self, compiler_with_graph):
        """지금은 정확히 반대다 — 틀린 형태가 200, 맞는 형태가 500.

        노드 하나를 말하는 올바른 방법은 `["a"]` 다. 그것이 통과해야 한다.
        """
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude",
                           {"input_nodes": ["a"]})
        assert code == 200, f"올바른 형태를 막았다 — {code} {body}"

    def test_a_node_that_does_not_exist_is_the_users_mistake_not_ours(self, compiler_with_graph):
        """없는 노드 이름은 사용자가 잘못 쓴 것이다. 400 이어야 한다.

        500 은 우리 잘못을 뜻하고, 사용자에게 "고칠 수 있는 게 있다" 고
        알려주지 않는다.
        """
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude",
                           {"input_nodes": ["does-not-exist"]})
        assert code == 400, f"사용자 입력 오류가 {code} 로 보고됐다 — {body}"
        assert "does-not-exist" in json.dumps(body), "어느 노드가 문제인지 말하지 않는다"

    @pytest.mark.parametrize("value", ["abc", 5, {"a": 1}, [1, 2], ["a", 3]])
    def test_unusable_node_lists_are_refused(self, compiler_with_graph, value):
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude",
                           {"input_nodes": value})
        assert code == 400, f"input_nodes={value!r} 가 {code} 를 받았다 — {body}"

    def test_an_empty_selection_still_means_everything_included(self, compiler_with_graph):
        """빈 선택은 정상 입력이다. 과잉 차단하면 안 된다."""
        base, _ = compiler_with_graph
        code, body = _post(base, "/compile/graphjob/calculate-exclude", {})
        assert code == 200, body
        assert body["included_count"] == 4


class TestResumeStoresOnlyUsableNodeLists:
    @pytest.mark.parametrize("value", ["abc", 5, {"a": 1}, [1, 2]])
    def test_the_resume_endpoint_refuses_what_it_cannot_use(self, compiler_with_graph, value):
        """지금은 아무 타입이나 200 으로 받아 job 에 저장한다.

        터지는 것은 한참 뒤 컴파일 중이고, 그때는 이 요청과 연결 짓기 어렵다.
        받는 자리에서 막는다.
        """
        base, job = compiler_with_graph
        job.paused = True
        job.selected_input_nodes = ["미리-있던-값"]
        code, body = _post(base, "/compile/graphjob/resume", {"input_nodes": value})
        assert code == 400, f"input_nodes={value!r} 를 {code} 로 받았다 — {body}"
        assert job.selected_input_nodes == ["미리-있던-값"], \
            "거부해 놓고 job 에는 써 넣었다"

    def test_a_usable_selection_still_resumes(self, compiler_with_graph):
        base, job = compiler_with_graph
        job.paused = True
        code, body = _post(base, "/compile/graphjob/resume",
                           {"input_nodes": ["a"], "output_nodes": ["c"]})
        assert code == 200, body
        assert job.selected_input_nodes == ["a"]
        assert job.selected_output_nodes == ["c"]


class TestBrokenEnhancedSchemeIsNotSwallowed:
    def test_unparseable_json_is_refused_not_dropped(self):
        """사용자가 DXQ 를 요청했는데 JSON 이 깨졌다면, 조용히 평범한 컴파일을
        돌리는 것이 최악이다. 요청한 것과 실행된 것이 다르고 아무도 모른다."""
        server, port = start_module_server("dx_compiler")
        try:
            boundary = uuid.uuid4().hex
            fields = {"model_path": "/tmp/a.onnx", "config_path": "/tmp/a.json",
                      "output_dir": "/tmp/o", "enhanced_scheme": "{{{"}
            body = "".join(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                for k, v in fields.items()) + f"--{boundary}--\r\n"
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/compile", data=body.encode(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    code = r.status
                    payload = r.read().decode()[:200]
            except urllib.error.HTTPError as e:
                code, payload = e.code, e.read().decode()[:200]
            assert code == 400, f"깨진 enhanced_scheme 이 조용히 삼켜졌다 — {code} {payload}"
        finally:
            server.shutdown()
