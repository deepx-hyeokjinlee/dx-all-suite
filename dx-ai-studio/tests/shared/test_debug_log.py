import json, importlib
import pytest


@pytest.fixture
def dl(tmp_path, monkeypatch):
    mod = importlib.import_module("shared.debug_log")
    monkeypatch.setattr(mod, "_ENABLED", True)
    monkeypatch.setattr(mod, "_logger", None)
    logf = tmp_path / "studio-debug.log"
    monkeypatch.setattr(mod, "_log_path", lambda: logf)
    monkeypatch.setenv("DX_STUDIO_BOOT", "8890-123")
    return mod, logf


def _lines(logf):
    return [json.loads(l) for l in logf.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_http_action_and_exec_write_jsonl(dl):
    mod, logf = dl
    mod.log_http("proxy", "POST", "/api/run_async?x=1", 200, 18.4, "127.0.0.1",
                 extra={"model_name": "yolov5s", "category": "object_detection"})
    mod.log_action("dx_app", "run", {"model_name": "resnet18", "password": "p", "image_base64": "AAAA"})
    mod.log_exec("dx_app", ["/bin/bp", "-m", "x.dxnn", "--token", "SEKRET"], 0, 900.0)
    rows = _lines(logf)
    assert rows[0]["type"] == "http" and rows[0]["path"] == "/api/run_async"
    assert rows[0]["status"] == 200 and rows[0]["model_name"] == "yolov5s" and rows[0]["boot"] == "8890-123"
    assert rows[1]["type"] == "action" and rows[1]["params"] == {"model_name": "resnet18"}
    assert "SEKRET" not in json.dumps(rows[2]) and rows[2]["exit"] == 0


def test_noise_filtered_but_errors_kept(dl):
    mod, logf = dl
    mod.log_http("proxy", "GET", "/api/hw_stream", 200, 1.0, "127.0.0.1")
    mod.log_http("proxy", "GET", "/static/js/app.js", 304, 0.2, "127.0.0.1")
    mod.log_http("proxy", "GET", "/api/hw_status", 500, 2.0, "127.0.0.1")
    mod.log_http("proxy", "GET", "/dx_app/", 200, 5.0, "127.0.0.1")
    paths = [r["path"] for r in _lines(logf)]
    assert paths == ["/api/hw_status", "/dx_app/"]


def test_disabled_is_noop(tmp_path, monkeypatch):
    mod = importlib.import_module("shared.debug_log")
    monkeypatch.setattr(mod, "_ENABLED", False)
    logf = tmp_path / "studio-debug.log"
    monkeypatch.setattr(mod, "_log_path", lambda: logf)
    mod.log_http("proxy", "GET", "/dx_app/", 200, 1.0, "127.0.0.1")
    mod.log_action("dx_app", "run", {"model_name": "x"})
    assert not logf.exists()
