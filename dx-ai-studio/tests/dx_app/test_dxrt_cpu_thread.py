"""studio 가 돌리는 dx_app 은 DXRT_DYNAMIC_CPU_THREAD=ON 으로 (2026-10-01).

RT-DETR r18 처럼 graph 일부가 CPU task 인 model 은 그 task 가 thread 하나라 async 로 돌려도 막힌다. 이 PC
(DX-RT 3.5.0) 에서 C++ async 100 frame: OFF 4.2 FPS (CPU queue 78%) → ON 9.3 FPS (30%). DX-RT 자신이
"To improve FPS, set: 'export DXRT_DYNAMIC_CPU_THREAD=ON'" 이라고 찍고, dx_rt 문서
(04_Model_Inference.md) 와 dx_app 의 performance_patterns 도 같은 처방이다. 사용자가 이미 정한 값 (OFF 포함)
은 그대로 둔다.
"""
from pathlib import Path

from tests.dx_app.test_inference_runtime_regressions import _prepare_dx_app_runtime

ROOT = Path(__file__).resolve().parents[2]


def test_run_env_turns_dynamic_cpu_thread_on_but_keeps_a_user_choice():
    from shared import dxrt
    assert dxrt.run_env({})["DXRT_DYNAMIC_CPU_THREAD"] == "ON"
    assert dxrt.run_env({"DXRT_DYNAMIC_CPU_THREAD": "OFF"})["DXRT_DYNAMIC_CPU_THREAD"] == "OFF"
    base = {"A": "1"}
    dxrt.run_env(base)
    assert base == {"A": "1"}, "넘긴 dict 를 바꾸지 않는다"


def test_an_inference_run_gets_dynamic_cpu_thread(tmp_path, monkeypatch):
    monkeypatch.delenv("DXRT_DYNAMIC_CPU_THREAD", raising=False)
    inference, _ = _prepare_dx_app_runtime(tmp_path, monkeypatch)
    captured = {}

    class FakeProc:
        returncode = 0

        def __init__(self, cmd, stdout=None, **kwargs):
            captured["env"] = kwargs.get("env", {})
            if stdout:
                stdout.write("Overall FPS         :   9.3 FPS\n")
                stdout.flush()

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(inference.subprocess, "Popen", FakeProc)
    inference.run_inference("demo", "object_detection", "model.dxnn",
                            input_type="video", video_path="input.mp4", lang="cpp", timeout=1)
    assert captured["env"].get("DXRT_DYNAMIC_CPU_THREAD") == "ON"


def test_live_runs_use_the_same_env():
    src = (ROOT / "dx_app" / "core" / "live.py").read_text(encoding="utf-8")
    assert "run_env(" in src, "카메라 · RTSP live 실행도 같은 env 를 쓴다"
