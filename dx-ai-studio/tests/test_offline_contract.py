"""블로킹 스위트가 인터넷 없이 돌아야 한다.

이 파일 자체는 가드가 동작하는지만 본다. 스위트 전체를 차단 상태로 돌리는 것은
`run_ci.sh --offline` 이 한다 — 한 프로세스 안에서 전역 소켓을 막으면 네트워크가
**필요한** 테스트까지 죽으므로, 스테이지를 따로 둔다.
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.request

import pytest

from tests.offline_guard import no_external_network


def test_the_guard_blocks_the_outside():
    with no_external_network():
        with pytest.raises((OSError, urllib.error.URLError)):
            urllib.request.urlopen("https://developer.deepx.ai/", timeout=5)


def test_the_guard_leaves_localhost_alone():
    """127.0.0.1 까지 막으면 모듈 서버를 띄우는 테스트가 전부 죽는다."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        with no_external_network():
            client = socket.socket()
            client.connect(listener.getsockname())
            client.close()
    finally:
        listener.close()


def test_it_puts_itself_back():
    """가드가 남으면 뒤따르는 테스트가 이유 없이 죽는다."""
    before = socket.socket.connect
    with no_external_network():
        pass
    assert socket.socket.connect is before


def test_the_gate_flag_actually_blocks():
    """`DX_OFFLINE_GUARD=1` 로 돌 때 외부 호출이 진짜 막히는지.

    가드 코드가 옳아도 conftest 가 그것을 켜지 않으면 스위트는 그냥 통과한다 —
    막혀서가 아니라 원래 안 나가서. 그건 거짓 안전감이고, 그대로 커밋할 뻔했다.
    이 검사는 플래그가 켜진 실행에서만 의미가 있으므로 꺼져 있으면 건너뛴다.
    """
    import os

    if os.environ.get("DX_OFFLINE_GUARD") != "1":
        pytest.skip("가드가 꺼져 있다 — run_ci.sh --offline 이 켠다")

    with pytest.raises(Exception) as excinfo:
        urllib.request.urlopen("https://developer.deepx.ai/", timeout=5)
    assert "BLOCKED" in str(excinfo.value), (
        f"막히긴 했으나 가드가 아니다: {excinfo.value}"
    )
