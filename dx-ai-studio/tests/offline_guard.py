"""외부 소켓만 막고 localhost 는 살려 두는 가드.

개발이 폐쇄망에서 일반망으로 옮겨가면서 안전장치가 하나 사라졌다 — 전에는 개발
환경 자체가 "인터넷에 의존하는 코드" 를 막았다. 이제 그런 코드를 쓸 수 있고, 처음
드러나는 곳은 PR 을 올리는 폐쇄망 PC 다. 고객도 폐쇄망에 배치하므로 제품 요건이기도
하다. 자세한 등급은 docs/offline-contract.md.

localhost 를 막지 않는 것이 핵심이다. 테스트는 모듈 서버를 띄워 127.0.0.1 로 말하고,
그것까지 막으면 아무것도 돌지 않는다. 막아야 할 것은 "바깥" 이다.
"""
from __future__ import annotations

import socket
from contextlib import contextmanager

_LOCAL = ("127.", "::1", "localhost", "0.0.0.0")


def _is_local(host) -> bool:
    if host is None:
        return True
    h = str(host)
    return h.startswith("127.") or h in ("::1", "localhost", "0.0.0.0")


@contextmanager
def no_external_network():
    """이 블록 안에서는 외부로 나가는 TCP 연결이 OSError 로 막힌다."""
    real = socket.socket.connect

    def guard(self, address):
        host = address[0] if isinstance(address, tuple) else None
        if not _is_local(host):
            raise OSError(
                101,
                f"BLOCKED external connect to {host} — "
                "docs/offline-contract.md 를 보고 이 호출이 어느 등급인지 정하세요",
            )
        return real(self, address)

    socket.socket.connect = guard
    try:
        yield
    finally:
        socket.socket.connect = real


_installed = False


def install() -> None:
    """프로세스 전체에 가드를 건다 (되돌리지 않는다).

    `no_external_network()` 를 `__enter__` 만 하고 참조를 버리면 제너레이터가
    수거되면서 `finally` 가 돌아 가드가 풀린다 — 실제로 그렇게 써서 스위트가
    "막혀서" 가 아니라 "원래 안 나가서" 통과했다. 세션 내내 유지해야 하는
    설정이므로 컨텍스트 매니저가 아니라 이 함수를 쓴다.
    """
    global _installed
    if _installed:
        return
    real = socket.socket.connect

    def guard(self, address):
        host = address[0] if isinstance(address, tuple) else None
        if not _is_local(host):
            raise OSError(
                101,
                f"BLOCKED external connect to {host} — "
                "docs/offline-contract.md 를 보고 이 호출이 어느 등급인지 정하세요",
            )
        return real(self, address)

    socket.socket.connect = guard
    _installed = True
