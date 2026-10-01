"""결정적 이벤트 시퀀스 — 폐쇄망 계약 검증용(기존 동작 보존).

DX_AGENT_MOCK_DELAY=<초> 면 event 사이를 그만큼 쉰다 — "도는 실행에 붙기" 를 시험하려면 실행이
붙을 틈만큼은 길어야 한다 (기본 0: 예전처럼 즉시). DX_AGENT_MOCK_REPLY 는 마지막 답글 (markdown 시험용).
"""
import os
import time

from dx_agent_dev.core.adapters.base import AgentAdapter


class MockAdapter(AgentAdapter):
    def is_available(self) -> bool:
        return True

    def run(self, prompt, session_dir, harness_dirs, run_ctx=None):
        try:
            delay = float(os.environ.get("DX_AGENT_MOCK_DELAY") or 0)
        except ValueError:
            delay = 0.0
        events = [
            {"type": "status", "text": "session_started"},
            {"type": "message", "text": f"요청 분석: {prompt}"},
            {"type": "command", "text": "dx-suite-builder --plan"},
            {"type": "log", "text": "[1/2] 모델 준비"},
            {"type": "log", "text": "[2/2] 파이프라인 구성"},
            # 답글을 정해 주면 진짜 agent 처럼 최종본 (final) 으로 보낸다 — 앞의 message 를 바꾼다
            ({"type": "message", "text": os.environ["DX_AGENT_MOCK_REPLY"], "final": True}
             if os.environ.get("DX_AGENT_MOCK_REPLY") else {"type": "message", "text": "완료되었습니다."}),
            {"type": "done", "text": "ok"},
        ]
        for i, ev in enumerate(events):
            if delay and i:
                time.sleep(delay)
            yield ev

    def cancel(self):
        pass
