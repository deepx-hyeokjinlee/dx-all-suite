"""서버가 실행을 소유하는지 — 스트림을 끊어도 계속되고, 다시 붙을 수 있는지.

`test_live_run.py` 가 버퍼 자체를 지킨다면, 여기서는 그것이 실제로 HTTP 경로에
배선되었는지를 본다. 둘을 나눈 이유: 버퍼가 옳아도 핸들러가 예전처럼
`_runner.run()` 을 직접 돌리면 이 버그는 그대로다.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from tests.server_helpers import start_module_server


@pytest.fixture()
def agent():
    server, port = start_module_server("dx_agent_dev")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return json.loads(r.read().decode())


def _post_stream(base, payload):
    req = urllib.request.Request(
        base + "/api/agent/run",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=30)


def test_status_reports_the_current_run(agent):
    st = _get(agent, "/api/agent/status")
    for key in ("busy", "run_id", "event_count"):
        assert key in st, f"status 에 {key} 가 없다: {sorted(st)}"


def test_the_run_survives_a_consumer_that_walks_away(agent):
    """home 에서 Agent Dev 로 이동하는 것이 이 상황이다."""
    resp = _post_stream(agent, {"prompt": "make baseball game"})
    first = resp.readline()
    assert first, "스트림이 아무것도 주지 않았다"
    resp.close()                       # 창을 닫은 것과 같다
    time.sleep(0.4)

    st = _get(agent, "/api/agent/status")
    assert st.get("run_id"), "실행이 서버에 남아 있지 않다"
    assert st.get("event_count", 0) >= 1, st


def test_you_can_attach_to_a_run_you_did_not_start(agent):
    """Agent Dev 가 home 이 시작한 실행에 붙는 경로."""
    resp = _post_stream(agent, {"prompt": "make baseball game"})
    resp.readline()
    resp.close()

    with urllib.request.urlopen(agent + "/api/agent/run/events?from=0", timeout=60) as att:
        body = att.read().decode("utf-8", "replace")
    assert "data:" in body, f"붙었는데 이벤트가 없다: {body[:200]!r}"


def test_attaching_from_an_index_skips_what_was_seen(agent):
    """`from` 이 실제로 건너뛰는지. 이벤트 개수는 어댑터마다 다르므로 상대 비교한다.

    (처음에 "2개 이상 나온다" 를 전제했다가 mock 이 1개만 내서 어긋났다 — 전제를
    두지 않는 편이 맞다.)
    """
    resp = _post_stream(agent, {"prompt": "make baseball game"})
    resp.read()
    resp.close()
    full = _get(agent, "/api/agent/status")["event_count"]
    assert full >= 1, full

    def _count(from_index):
        with urllib.request.urlopen(
            agent + f"/api/agent/run/events?from={from_index}", timeout=60
        ) as att:
            return att.read().decode("utf-8", "replace").count("data:")

    beginning = _count(0)
    assert beginning >= 1, "처음부터 붙었는데 아무것도 못 받았다"
    assert _count(full) < beginning, (
        f"끝 지점에서 붙었는데 처음과 같은 양을 받았다 ({beginning})"
    )


def test_the_post_response_shape_is_unchanged(agent):
    """Agent Dev 자체 콘솔(console.js:623)이 그대로 동작해야 한다."""
    resp = _post_stream(agent, {"prompt": "make baseball game"})
    try:
        assert resp.headers.get("Content-Type", "").startswith("text/event-stream")
        line = resp.readline().decode()
        assert line.startswith("data: "), line
    finally:
        resp.close()
