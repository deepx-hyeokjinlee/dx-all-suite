"""실행은 그 요청을 보낸 창의 것이 아니라 서버의 것이어야 한다.

home 에서 에이전트가 도는 중에 `Open in DX Agent Dev` 를 누르면 Agent Dev 에서는
아무 일도 일어나지 않았고, home 으로 돌아오면 작업이 사라져 있었다. 실행이 하나의
HTTP 응답에 묶여 있었기 때문이다 — 브라우저가 스트림 리더를 놓으면 서버 제너레이터에
`GeneratorExit` 가 나고, `agent_runner.py` 의 `finally` 가 subprocess 를 종료했다.
그 정리는 정상 완료·타임아웃에는 옳지만, "창을 닫았다" 가 거기 끼면 안 된다.

그래서 실행을 응답에서 떼어낸다: 백그라운드가 이벤트를 버퍼에 쌓고, 응답은 그 버퍼를
읽는다. 소비자가 없거나 사라져도 실행은 계속되고, 나중에 붙으면 처음부터 받는다.
"""
from __future__ import annotations

import threading
import time

import pytest

from dx_agent_dev.core.live_run import LiveRun


def _slow_source(n=5, delay=0.02, started=None, finished=None):
    def gen():
        if started:
            started.set()
        for i in range(n):
            time.sleep(delay)
            yield {"type": "message", "text": f"e{i}"}
        yield {"type": "done"}
        if finished:
            finished.set()
    return gen()


def test_events_accumulate_with_nobody_listening():
    """소비자가 붙기 전에도 실행은 진행된다."""
    run = LiveRun()
    run.start(_slow_source(3))
    deadline = time.time() + 5
    while time.time() < deadline and not run.snapshot()["done"]:
        time.sleep(0.02)
    snap = run.snapshot()
    assert snap["done"], "아무도 안 듣는다고 실행이 멈췄다"
    assert snap["count"] == 4, snap          # 3 + done


def test_attaching_late_replays_from_the_beginning():
    run = LiveRun()
    run.start(_slow_source(3))
    while not run.snapshot()["done"]:
        time.sleep(0.02)
    got = [e for e in run.events(0)]
    assert [e.get("text") for e in got[:3]] == ["e0", "e1", "e2"], got
    assert got[-1]["type"] == "done"


def test_two_consumers_see_the_same_run():
    """home 과 Agent Dev 가 동시에 같은 실행을 볼 수 있어야 한다."""
    run = LiveRun()
    run.start(_slow_source(4, delay=0.03))
    out = {}

    def drain(key):
        out[key] = [e for e in run.events(0)]

    a = threading.Thread(target=drain, args=("a",))
    b = threading.Thread(target=drain, args=("b",))
    a.start(); b.start(); a.join(10); b.join(10)
    assert out["a"] == out["b"], (out["a"], out["b"])
    assert len(out["a"]) == 5


def test_start_does_not_block_the_caller():
    """실행이 호출자 스레드에서 돌면 이 클래스는 아무것도 바꾸지 못한다.

    이 검사가 없으면 아래 "소비자가 떠나도 계속된다" 가 공짜로 참이 된다 — 동기
    펌프에서는 start() 가 끝까지 돌고 반환하므로, 소비자가 붙을 때는 이미 끝나 있다.
    (실제로 그렇게 써서 변이가 통과했다.)
    """
    run = LiveRun()
    started = threading.Event()
    run.start(_slow_source(6, delay=0.05, started=started))
    assert started.wait(5), "소스가 시작되지 않았다"
    assert not run.snapshot()["done"], "start() 가 실행을 끝내고 돌아왔다"
    run.cancel()


def test_a_consumer_giving_up_does_not_stop_the_run():
    """이 버그의 핵심. 창을 닫아도 실행은 계속되어야 한다."""
    run = LiveRun()
    finished = threading.Event()
    run.start(_slow_source(6, delay=0.05, finished=finished))

    stream = run.events(0)
    next(stream)                 # 첫 이벤트만 받고
    assert not run.snapshot()["done"], "떠나기도 전에 실행이 끝났다 — 검사가 무의미하다"
    stream.close()               # 브라우저가 떠난 것과 같다

    assert finished.wait(10), "소비자가 떠나자 실행이 멈췄다"
    assert run.snapshot()["count"] == 7


def test_resuming_from_an_index_skips_what_was_seen():
    run = LiveRun()
    run.start(_slow_source(3))
    while not run.snapshot()["done"]:
        time.sleep(0.02)
    rest = [e for e in run.events(2)]
    assert [e.get("text") for e in rest[:1]] == ["e2"], rest


def test_a_new_run_replaces_the_last_one():
    """서버당 실행 하나. 끝난 실행은 다음이 시작될 때까지만 남는다."""
    run = LiveRun()
    first = run.start(_slow_source(2))
    while not run.snapshot()["done"]:
        time.sleep(0.02)
    second = run.start(_slow_source(2))
    assert second != first
    assert run.snapshot()["run_id"] == second


def test_starting_while_busy_is_refused():
    run = LiveRun()
    run.start(_slow_source(6, delay=0.05))
    with pytest.raises(RuntimeError):
        run.start(_slow_source(2))
    run.cancel()
