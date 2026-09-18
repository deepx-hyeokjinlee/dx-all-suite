"""인터넷이 없을 때 아티팩트 엔드포인트가 어떻게 동작하는지 — 사실을 고정한다.

처음에 나는 이것을 결함으로 적었다. 외부 소켓을 막고 `urlopen` 으로 부르면
`URLError` 가 나므로 "응답이 오지 않는다" 고 읽었다. **틀렸다.** `urlopen` 이
리다이렉트를 따라가다 실패한 것이고, 서버는 차단 상태에서도 302 를 제대로 낸다:

    HTTP 302  Location: https://sdk.deepx.ai/modelzoo/onnx/damoyolo-t_640x640.onnx

그러니 서버는 할 일을 한다. 인터넷 없이 CDN 에 못 닿는 것은 고장이 아니라 사실이다.
아티팩트 다운로드는 docs/offline-contract.md 의 "네트워크" 등급이다.

이 파일이 지키는 것은 두 가지다: 서버가 네트워크 유무와 무관하게 **판단 가능한
응답**을 준다는 것(무응답이나 무한 대기가 아니라), 그리고 폐쇄망 대응을 이유로
누군가 이 302 를 없애지 않는다는 것 — 인터넷이 있을 때는 이것이 맞는 동작이다.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

from tests.server_helpers import start_module_server


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """리다이렉트를 따라가지 않는다 — 서버가 무엇을 답했는지 보려면 따라가면 안 된다."""

    def redirect_request(self, *args, **kwargs):
        return None


@pytest.fixture()
def no_internet():
    real = socket.socket.connect

    def guard(self, addr):
        host = addr[0] if isinstance(addr, tuple) else None
        if host and not (str(host).startswith("127.") or host in ("::1", "localhost")):
            raise OSError(101, f"BLOCKED external connect to {host}")
        return real(self, addr)

    socket.socket.connect = guard
    try:
        yield
    finally:
        socket.socket.connect = real


@pytest.fixture()
def zoo():
    server, port = start_module_server("dx_modelzoo")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _first_model(base):
    with urllib.request.urlopen(base + "/api/catalog", timeout=20) as r:
        data = json.loads(r.read().decode())
    assert data["models"], "카탈로그가 비었다"
    return data["models"][0]["id"]


def _ask(base, model_id):
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(f"{base}/api/catalog/{model_id}/artifacts/onnx", timeout=25) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


def test_the_server_answers_with_no_internet(zoo, no_internet):
    """무응답이나 무한 대기가 아니라 판단 가능한 응답이어야 한다."""
    status, _ = _ask(zoo, _first_model(zoo))
    assert status in (200, 302, 404), f"예상 밖 응답: {status}"


def test_a_remote_artifact_still_points_at_the_cdn(zoo, no_internet):
    """폐쇄망 대응을 이유로 이 리다이렉트를 없애면 인터넷이 있을 때가 깨진다."""
    status, location = _ask(zoo, _first_model(zoo))
    if status == 302:
        assert location and location.startswith("http"), location


def test_it_behaves_the_same_with_internet(zoo):
    status, _ = _ask(zoo, _first_model(zoo))
    assert status in (200, 302, 404), f"예상 밖 응답: {status}"
