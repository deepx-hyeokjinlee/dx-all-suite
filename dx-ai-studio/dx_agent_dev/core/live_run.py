"""실행을 HTTP 응답에서 떼어내는 자리.

예전에는 `_runner.run(...)` 제너레이터를 SSE 핸들러가 직접 돌렸다. 그래서 브라우저가
스트림 리더를 놓으면 제너레이터에 `GeneratorExit` 가 나고, `agent_runner.py` 의
`finally` 가 subprocess 를 종료했다 — 창을 닫거나 다른 모듈로 이동하는 것만으로
돌던 작업이 죽었다. home 의 `Open in DX Agent Dev` 가 정확히 그 일을 했다.

여기서는 백그라운드 스레드가 이벤트를 쌓고, 응답은 그 버퍼를 읽는다. 소비자가 없거나
중간에 사라져도 실행은 계속되고, 나중에 붙으면 처음부터(또는 원하는 지점부터) 받는다.

서버당 실행은 하나다 — `AgentRunner` 가 그렇게 만들어져 있다("서버당 실행 세션 1개").
그래서 레지스트리가 아니라 슬롯 하나다. 끝난 실행은 다음이 시작될 때까지 남는다:
끝난 직후에 붙은 창도 결과를 봐야 하기 때문이다.

버퍼는 메모리다. 서버가 죽으면 사라진다 — 실행 이력이 아니라 진행 중인 실행에
다시 붙기 위한 것이다.
"""
from __future__ import annotations

import threading
import uuid
from typing import Any, Callable, Iterable, Iterator, Optional


class LiveRun:
    def __init__(self, on_event: Optional[Callable[[dict], None]] = None):
        self._cv = threading.Condition()
        self._events: list[dict] = []
        self._done = True
        self._run_id: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._cancel: Optional[Callable[[], None]] = None
        self._on_event = on_event

    # ── 생애 ──────────────────────────────────────────────────

    def start(
        self,
        source: Iterable[dict],
        *,
        cancel: Optional[Callable[[], None]] = None,
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """`source` 를 백그라운드에서 소비하기 시작하고 run_id 를 돌려준다."""
        with self._cv:
            if not self._done:
                raise RuntimeError("run already in progress")
            run_id = uuid.uuid4().hex
            self._events = []
            self._done = False
            self._run_id = run_id
            self._cancel = cancel
            if on_event is not None:
                self._on_event = on_event
            self._cv.notify_all()

        def pump():
            try:
                for ev in source:
                    with self._cv:
                        if self._run_id != run_id:
                            break          # 다른 실행이 슬롯을 가져갔다
                        self._events.append(ev)
                        self._cv.notify_all()
                    # 대화 기록 바인딩처럼 "소비자가 없어도 일어나야 하는 일" 은
                    # 여기서 한다. 응답 쪽에 두면 창을 닫았을 때 결과가 유실된다.
                    if self._on_event is not None:
                        try:
                            self._on_event(ev)
                        except Exception:
                            pass
            finally:
                with self._cv:
                    if self._run_id == run_id:
                        self._done = True
                    self._cv.notify_all()

        thread = threading.Thread(target=pump, name=f"live-run-{run_id[:8]}", daemon=True)
        self._thread = thread
        thread.start()
        return run_id

    def cancel(self) -> None:
        with self._cv:
            cancel = self._cancel
        if cancel is not None:
            cancel()

    # ── 읽기 ──────────────────────────────────────────────────

    def events(self, from_index: int = 0) -> Iterator[dict]:
        """`from_index` 부터 흘려보낸다. 실행이 끝나면 종료된다.

        소비자가 이 제너레이터를 닫아도 실행에는 영향이 없다 — 그것이 이 클래스의
        존재 이유다.
        """
        i = max(0, int(from_index or 0))
        while True:
            with self._cv:
                while i >= len(self._events) and not self._done:
                    self._cv.wait(timeout=0.5)
                if i >= len(self._events):
                    return
                batch = self._events[i:]
                i = len(self._events)
            for ev in batch:
                yield ev

    def snapshot(self) -> dict[str, Any]:
        with self._cv:
            return {"run_id": self._run_id, "count": len(self._events), "done": self._done}
