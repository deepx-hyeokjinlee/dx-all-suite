"""Studio preparation requires the runnable targets it actually exposes, not any *_sync file."""
from pathlib import Path
import sys

import pytest

from dx_app.core import config, graph_cli, graph_validate, setup_steps
from shared import dx_app_layout


@pytest.fixture
def app_tree(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    build = root / "build_x86_64" / "src" / "cpp_example"
    build.mkdir(parents=True)
    monkeypatch.setattr(setup_steps, "DX_APP_ROOT", root)
    monkeypatch.setattr(setup_steps, "BUILD_DIR", build)
    monkeypatch.setattr(config, "DX_APP_ROOT", root)
    monkeypatch.setattr(config, "BUILD_DIR", build)
    monkeypatch.setattr(setup_steps, "_probe_dx_engine_venv", lambda: (True, "ready"))
    monkeypatch.setattr(setup_steps, "_find_dxcom", lambda: None)
    monkeypatch.setattr(setup_steps, "_dxcom_version", lambda: None)
    monkeypatch.setattr(setup_steps, "_get_npu_driver_version", lambda: "--")
    from shared import runtime
    monkeypatch.setattr(runtime, "_has_numpy_cv2_dxengine", lambda _: True)
    monkeypatch.setattr(runtime, "runtime_python", lambda: sys.executable)
    dx_app_layout.clear_cache()
    yield root, build
    dx_app_layout.clear_cache()


def _executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)


def _example(root, build, *, nested=False):
    folder = root / "src" / "cpp_example" / "object_detection"
    folder = folder / "yolo" / "detector" if nested else folder / "detector"
    folder.mkdir(parents=True)
    for variant in ("sync", "async"):
        (folder / f"detector_{variant}.cpp").write_text("int main() { return 0; }\n")
        _executable(build / f"detector_{variant}")


def _graphs(build):
    for name in graph_cli.NAMES.values():
        _executable(build / name)


def test_studio_build_requests_full_sdk_build_without_changing_arch():
    step = setup_steps.SETUP_STEPS["dx-app-build"]
    assert "--all" in step["args"]
    assert step["args"][step["args"].index("--arch") + 1] == "x86_64"


def test_assets_use_studio_entrypoint_not_sdk_bulk_setup():
    step = setup_steps.SETUP_STEPS["dx-app-setup"]
    assert not step.get("script"), "SDK setup.sh is not the Studio asset installer"
    assert step["cmd"]() == [sys.executable, "-m", "shared.asset_setup", "app"]
    assert step["cwd"]() == Path(setup_steps.__file__).resolve().parents[2]


def test_minimal_build_does_not_skip_graph_preparation(app_tree):
    root, build = app_tree
    _example(root, build)
    status = setup_steps.setup_status()["dx-app-build"]
    assert not status["ok"], status
    assert "multi_model_graph_sync" in status["detail"]
    assert "dx-app-build" in setup_steps.quick_start_plan()


def test_graphs_alone_are_not_a_complete_demo_build(app_tree):
    _, build = app_tree
    _graphs(build)
    assert not setup_steps.setup_status()["dx-app-build"]["ok"]


@pytest.mark.parametrize("nested,installed", [(False, False), (True, False), (True, True)])
def test_ready_build_resolves_declared_examples_and_both_graph_variants(app_tree, monkeypatch, nested, installed):
    root, build = app_tree
    if installed:
        build = root / "bin"
        monkeypatch.setattr(config, "BUILD_DIR", build)
        monkeypatch.setattr(setup_steps, "BUILD_DIR", build)
    _example(root, build, nested=nested)
    _graphs(build)
    assert setup_steps.setup_status()["dx-app-build"]["ok"]
    (build / "detector_async").unlink()
    status = setup_steps.setup_status()["dx-app-build"]
    assert not status["ok"], "a declared async runner must be executable too"
    assert "detector_async" in status["detail"]


def test_nonexecutable_graph_is_not_ready(app_tree):
    root, build = app_tree
    _example(root, build)
    _graphs(build)
    (build / "multi_model_graph_async").chmod(0o644)
    assert not setup_steps.setup_status()["dx-app-build"]["ok"]


def test_graph_missing_message_names_existing_full_or_targeted_build(monkeypatch):
    monkeypatch.setattr(graph_cli, "available", lambda: None)
    result = graph_validate.validate({"nodes": []})
    how = result["errors"][0]["how"]
    assert "./build.sh --target multi_model_graph_sync multi_model_graph_async" in how
    assert "./build.sh --all" in how
    monkeypatch.setattr(graph_cli, "binary", lambda variant: None)
    with pytest.raises(graph_cli.GraphCliMissing) as missing:
        graph_cli.run(["--help"])
    assert "./build.sh --target multi_model_graph_sync multi_model_graph_async" in str(missing.value)


def test_xvfb_is_checked_with_actionable_manual_setup_guidance(app_tree, monkeypatch):
    original = setup_steps.shutil.which
    monkeypatch.setattr(setup_steps.shutil, "which",
                        lambda name, **kw: None if name == "Xvfb" else original(name, **kw))
    status = setup_steps.setup_status()["dx-app-deps"]
    assert not status["ok"]
    assert "Xvfb" in status["detail"]
    diag = next((c for c in setup_steps.deep_diagnostics()["checks"] if c["id"] == "live_display"), None)
    assert diag and not diag["ok"], "Setup diagnostics must check the Live display prerequisite"
    assert all("sudo apt install xvfb" in text for text in diag["fix"].values())


@pytest.mark.parametrize("available", [False, True])
def test_opencv_diagnostic_uses_isolated_media_probe(app_tree, monkeypatch, available):
    from shared import media
    calls = []

    def probe(operation, **params):
        calls.append(operation)
        if not available:
            raise media.MediaError("OpenCV runtime probe failed; run Python Inference Deps in Setup")
        return {"opencv": "4.99.0", "numpy": "2.0.0"}

    monkeypatch.setattr(media, "run_media", probe)
    diag = next(c for c in setup_steps.deep_diagnostics()["checks"] if c["id"] == "opencv")
    assert calls == ["probe"]
    assert diag["ok"] == available
    assert ("4.99.0" if available else "OpenCV runtime probe failed") in diag["detail"]


def test_acceptance_runnable_model_requires_executable_selected_variant():
    from tests.acceptance.test_sdkreq_474_dx_app import _runnable_model
    models = [
        {"name": "yolov8-n_640x640", "category": "object_detection", "model_exists": True,
         "cpp": False, "cpp_sync": False, "python": True, "py_sync": True},
        {"name": "async_only", "category": "object_detection", "model_exists": True,
         "cpp": True, "cpp_sync": False, "cpp_async": True},
        {"name": "ready_sync", "category": "object_detection", "model_exists": True,
         "cpp": True, "cpp_sync": True},
    ]

    class Frame:
        def evaluate(self, script):
            return models

    assert _runnable_model(Frame())["name"] == "ready_sync"


def test_acceptance_graph_missing_prerequisite_is_not_run_but_ready_catalog_error_fails():
    from tests.acceptance import test_sdkreq_474_dx_app as acceptance

    assert hasattr(acceptance, "_graph_example"), "Graph acceptance needs an explicit prerequisite check"
    with pytest.raises(pytest.skip.Exception, match="NOT RUN:.*--target"):
        acceptance._graph_example({"available": False, "error": "graph_binary_missing"})
    with pytest.raises(AssertionError, match="list_models_failed"):
        acceptance._graph_example({"available": True, "error": "list_models_failed: native failure"})
    with pytest.raises(pytest.skip.Exception, match="NOT RUN:.*model"):
        acceptance._graph_example({"available": True, "models": [], "examples": [
            {"id": "missing", "models": ["absent"]}]})
    ready = {"id": "ready", "models": ["detector"], "logic": False}
    assert acceptance._graph_example({"available": True, "models": [
        {"name": "detector", "installed": True, "ready": True, "state": "installed"}],
        "examples": [{"id": "missing", "models": ["absent"]}, ready]}) == ready


@pytest.mark.parametrize("verified", [False, True])
def test_asset_readiness_uses_local_validation_not_any_nonempty_model_and_video(app_tree, monkeypatch, verified):
    from shared import asset_setup

    root, _ = app_tree
    assets = root / "assets"
    for folder, name in (("models", "legacy.dxnn"), ("videos", "partial.mp4")):
        (assets / folder).mkdir(parents=True)
        (assets / folder / name).write_bytes(b"bad")
    monkeypatch.setattr(setup_steps, "ASSETS_DIR", assets)
    calls = []
    status = {"ok": verified, "detail": "verified transfers" if verified else "unverified legacy assets"}

    def local_status(component, sdk_root=None, resource_root=None):
        calls.append((component, sdk_root))
        return status

    monkeypatch.setattr(asset_setup, "sample_assets_status", local_status, raising=False)
    assert setup_steps.setup_status()["dx-app-setup"] == status
    assert calls == [("app", root)]
    assert ("dx-app-setup" in setup_steps.quick_start_plan()) == (not verified)
