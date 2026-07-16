"""Benchmark runner contract conformance tests."""

import sys
from pathlib import Path

_BENCHMARK_ROOT = str(Path(__file__).resolve().parents[2] / "dx_benchmark")


def _ensure_benchmark_path():
    for mod_name in list(sys.modules):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    if _BENCHMARK_ROOT not in sys.path:
        sys.path.insert(0, _BENCHMARK_ROOT)
    elif sys.path[0] != _BENCHMARK_ROOT:
        sys.path.remove(_BENCHMARK_ROOT)
        sys.path.insert(0, _BENCHMARK_ROOT)


def test_benchmark_result_protocol_exists():
    """BenchmarkResultProtocol is importable from core.runner_contracts."""
    _ensure_benchmark_path()
    from core.runner_contracts import BenchmarkResultProtocol

    assert hasattr(BenchmarkResultProtocol, "as_dict")


def test_benchmark_result_protocol_requires_status_and_as_dict():
    """BenchmarkResultProtocol rejects objects missing required public members."""
    _ensure_benchmark_path()
    from core.runner_contracts import BenchmarkResultProtocol

    class HasContract:
        status = "ok"

        def as_dict(self):
            return {}

    class MissingStatus:
        def as_dict(self):
            return {}

    class MissingAsDict:
        status = "ok"

    assert isinstance(HasContract(), BenchmarkResultProtocol)
    assert not isinstance(MissingStatus(), BenchmarkResultProtocol)
    assert not isinstance(MissingAsDict(), BenchmarkResultProtocol)


def test_model_result_satisfies_protocol():
    """ModelResult satisfies BenchmarkResultProtocol."""
    _ensure_benchmark_path()
    from core.runner_contracts import BenchmarkResultProtocol
    from core.runner_model import ModelResult

    result = ModelResult(
        model="test", task="detection", size="s", use_ort=False, family="throughput"
    )
    assert isinstance(result, BenchmarkResultProtocol)


def test_pipeline_result_satisfies_protocol():
    """PipelineResult satisfies BenchmarkResultProtocol."""
    _ensure_benchmark_path()
    from core.runner_contracts import BenchmarkResultProtocol
    from core.runner_pipeline import PipelineResult

    result = PipelineResult(
        model="test", task="detection", size="s", use_ort=False, video="/v.mp4"
    )
    assert isinstance(result, BenchmarkResultProtocol)


def test_benchmark_result_protocol_rejects_non_result():
    """A plain object should not satisfy BenchmarkResultProtocol."""
    _ensure_benchmark_path()
    from core.runner_contracts import BenchmarkResultProtocol

    class NotAResult:
        pass

    assert not isinstance(NotAResult(), BenchmarkResultProtocol)


def test_benchmark_result_as_dict_returns_dict():
    """Protocol contract: as_dict() returns a dict."""
    _ensure_benchmark_path()
    from core.runner_model import ModelResult

    result = ModelResult(
        model="test", task="detection", size="s", use_ort=False, family="throughput"
    )
    d = result.as_dict()
    assert isinstance(d, dict)
    assert "status" in d




def test_pipeline_sweeps_exports():
    """pipeline_sweeps module is importable and exports expected names."""
    _ensure_benchmark_path()
    from core.pipeline_sweeps import (
        is_capacity_pass,
        estimate_start_stream,
        get_existing_capacity,
        get_boundary_search_start,
        run_multi_stream_sweep,
        _make_sc1_from_single_stream,
    )
    assert callable(is_capacity_pass)
    assert callable(estimate_start_stream)
    assert callable(get_existing_capacity)
    assert callable(get_boundary_search_start)
    assert callable(run_multi_stream_sweep)
    assert callable(_make_sc1_from_single_stream)


def test_report_models_exports():
    """report_models module is importable and exports expected names."""
    _ensure_benchmark_path()
    from core.report_models import (
        _SIZE_ORDER,
        _TASK_DISPLAY_ORDER,
        _TASK_DISPLAY_NAMES,
        _GROUP_DISPLAY_NAMES,
        _GROUP_ORDER,
        _sort_by_size,
        _sort_models_by_size,
        _is_usable_result,
        _format_runs,
        _group_by_task,
    )
    assert isinstance(_SIZE_ORDER, dict)
    assert isinstance(_TASK_DISPLAY_ORDER, dict)
    assert isinstance(_TASK_DISPLAY_NAMES, dict)
    assert isinstance(_GROUP_DISPLAY_NAMES, dict)
    assert isinstance(_GROUP_ORDER, dict)
    assert callable(_sort_by_size)
    assert callable(_sort_models_by_size)
    assert callable(_is_usable_result)
    assert callable(_format_runs)
    assert callable(_group_by_task)


def test_report_renderers_exports():
    """report_renderers module is importable and exports expected names."""
    _ensure_benchmark_path()
    from core.report_renderers import (
        _add_timing_section,
        _add_executive_summary,
        _add_protocol_section,
        _add_benchmark_params_section,
        _add_model_info_section,
        _add_environment_section,
        _add_video_section,
        _add_model_throughput_section,
        _add_model_latency_section,
        _add_pipeline_section,
        _add_multi_stream_section,
        _add_ort_comparison_table,
        _add_capacity_summary,
    )
    assert callable(_add_timing_section)
    assert callable(_add_executive_summary)
    assert callable(_add_protocol_section)
    assert callable(_add_benchmark_params_section)
    assert callable(_add_model_info_section)
    assert callable(_add_environment_section)
    assert callable(_add_video_section)
    assert callable(_add_model_throughput_section)
    assert callable(_add_model_latency_section)
    assert callable(_add_pipeline_section)
    assert callable(_add_multi_stream_section)
    assert callable(_add_ort_comparison_table)
    assert callable(_add_capacity_summary)


def test_run_orchestrator_exports():
    """run_orchestrator module is importable and exports expected names."""
    _ensure_benchmark_path()
    from core.run_orchestrator import (
        _make_run_id,
        _resolve_resume_dir,
        _resolve_output_dir,
        _parse_npu_log_filename,
        _backfill_from_raw_logs,
        _parse_run_log_filename,
        _backfill_fps_std,
        _backfill_sc1_from_single_stream,
        _save_result_set,
        _make_timing_history_entry,
        _load_timing_history,
        _is_failed_result,
        _should_retry_failed,
        _upsert_result,
        _get_resume_stream_start,
    )
    assert callable(_make_run_id)
    assert callable(_resolve_resume_dir)
    assert callable(_resolve_output_dir)
    assert callable(_parse_npu_log_filename)
    assert callable(_backfill_from_raw_logs)
    assert callable(_parse_run_log_filename)
    assert callable(_backfill_fps_std)
    assert callable(_backfill_sc1_from_single_stream)
    assert callable(_save_result_set)
    assert callable(_make_timing_history_entry)
    assert callable(_load_timing_history)
    assert callable(_is_failed_result)
    assert callable(_should_retry_failed)
    assert callable(_upsert_result)
    assert callable(_get_resume_stream_start)


def test_backward_compat_runner_pipeline_sweep_imports():
    """Sweep functions remain importable from runner_pipeline."""
    _ensure_benchmark_path()
    from core.runner_pipeline import run_multi_stream_sweep, is_capacity_pass
    assert callable(run_multi_stream_sweep)
    assert callable(is_capacity_pass)


def test_backward_compat_reporter_imports():
    """Reporter helpers remain importable from reporter."""
    _ensure_benchmark_path()
    from core.reporter import generate_markdown_report, _sort_by_size, _add_timing_section
    assert callable(generate_markdown_report)
    assert callable(_sort_by_size)
    assert callable(_add_timing_section)




def test_format_runs_partial():
    """_format_runs returns 'completed/requested' when they differ."""
    _ensure_benchmark_path()
    from core.report_models import _format_runs

    assert _format_runs({"runs": 2, "requested_runs": 3}) == "2/3"


def test_format_runs_equal():
    """_format_runs returns just the count when completed == requested."""
    _ensure_benchmark_path()
    from core.report_models import _format_runs

    assert _format_runs({"runs": 3, "requested_runs": 3}) == "3"


def test_format_duration_hours_min_sec():
    """_format_duration handles hours, minutes, and seconds."""
    _ensure_benchmark_path()
    from core.report_renderers import _format_duration

    assert _format_duration(3661) == "1h 1m 1s"
    assert _format_duration(125) == "2m 5s"
    assert _format_duration(9.5) == "9.5s"
    assert _format_duration(0) == "N/A"
    assert _format_duration(None) == "N/A"


def test_get_boundary_search_start_converged():
    """get_boundary_search_start returns None when boundary is found."""
    _ensure_benchmark_path()
    from core.pipeline_sweeps import get_boundary_search_start

    existing = [
        {"stream_count": 3, "fps_mean": 30.0, "status": "ok", "runs": 3, "requested_runs": 3, "avg_per_channel_fps": 30.0},
        {"stream_count": 4, "fps_mean": 10.0, "status": "ok", "runs": 3, "requested_runs": 3, "avg_per_channel_fps": 10.0},
    ]
    assert get_boundary_search_start(existing, fps_threshold=20.0, single_stream_fps=30.0) is None


def test_build_legacy_timing_history_shared():
    """Shared _build_legacy_timing_history is usable from report_models."""
    _ensure_benchmark_path()
    from core.report_models import _build_legacy_timing_history

    fp = {
        "timing": {"start": "T0", "end": "T1", "duration_sec": 60},
        "benchmark_params": {"families": ["model"], "retry_failed": False},
        "benchmarked_models": [{"size": "s"}, {"size": "m"}],
    }
    history = _build_legacy_timing_history(fp)
    assert len(history) == 1
    assert history[0]["mode"] == "run"
    assert history[0]["task"] == "mixed"
    assert sorted(history[0]["sizes"]) == ["m", "s"]

    assert _build_legacy_timing_history({}) == []



_JS_ROOT = Path(__file__).resolve().parents[2] / "dx_benchmark" / "static" / "js"


def _read_js(name: str) -> str:
    return (_JS_ROOT / name).read_text(encoding="utf-8")


def _extract_function_body(source: str, name: str) -> str:
    anchor = f"function {name}("
    start = source.find(anchor)
    assert start != -1, f"{name} function not found"
    open_pos = source.find("{", start)
    assert open_pos != -1, f"{name} opening brace not found"
    depth = 0
    for pos in range(open_pos, len(source)):
        char = source[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_pos + 1:pos]
    raise AssertionError(f"{name} function braces are not balanced")


class TestDashboardNoLocalhostEdgeGuide:
    """dashboard.js must not hardcode http://localhost:8096."""

    def test_dashboard_js_no_localhost_8096(self):
        src = _read_js("dashboard.js")
        assert "http://localhost:8096" not in src, (
            "dashboard.js must not hardcode http://localhost:8096 for EdgeGuide"
        )

    def test_dashboard_js_no_fixed_8096_edgeguide_port(self):
        src = _read_js("dashboard.js")
        assert ":8096" not in src, (
            "dashboard.js must derive direct EdgeGuide links from origin/config, not fixed :8096"
        )

    def test_dashboard_js_edgeguide_base_function_is_used_at_link_sites(self):
        src = _read_js("dashboard.js")
        body = _extract_function_body(src, "_edgeGuideBase")

        assert "return '/planner/'" in body
        assert "plannerBaseUrl" in body and "planner_url" in body
        assert "_edgeGuideUrl" in src
        assert src.count("_appendEdgeGuideLink(") >= 2

    def test_dashboard_js_edgeguide_uses_launcher_not_new_tab(self):
        src = _read_js("dashboard.js")
        assert "window.open" not in src, (
            "dashboard.js must not open EdgeGuide in a new browser tab"
        )
        assert "target = '_blank'" not in src and 'target="_blank"' not in src, (
            "dashboard.js must not use target=_blank for EdgeGuide links"
        )
        nav_body = _extract_function_body(src, "_navigateToEdgeGuide")
        assert "_launcherLaunch()" in nav_body
        assert "launchFn('planner', query)" in nav_body
        launch_body = _extract_function_body(src, "_launcherLaunch")
        assert "typeof w.launch === 'function'" in launch_body

    def test_dashboard_js_direct_port_heuristic_skips_well_known_ports(self):
        src = _read_js("dashboard.js")
        body = _extract_function_body(src, "_edgeGuideBase")

        assert "currentPort > 1024" in body




class TestSettingsDeploymentFixed:
    """settings.js must not show misleading 'Saved' alert for deployment-fixed config."""

    def test_settings_js_no_save_button(self):
        """Settings panel must not contain a save button for path config."""
        src = _read_js("settings.js")
        assert "Settings.save()" not in src, (
            "settings.js must not have a save button calling Settings.save()"
        )

    def test_settings_js_shows_deployment_fixed_notice(self):
        """Settings panel must contain deployment-fixed or configured-at-deployment copy."""
        src = _read_js("settings.js")
        src_lower = src.lower()
        assert ("deployment" in src_lower or "read-only" in src_lower
                or "read only" in src_lower), (
            "settings.js must explain that settings are deployment-fixed or read-only"
        )

    def test_settings_js_no_misleading_save_alert(self):
        """settings.js must not alert a success message after POST."""
        src = _read_js("settings.js")
        assert "alert(" not in src or "Save" not in src.split("alert(")[1].split(")")[0] if "alert(" in src else True, (
            "settings.js must not show misleading 'Saved ✅' alert"
        )

    def test_settings_js_populates_runtime_values_from_server(self):
        """settings.js load() must populate thermal/benchmark fields from /api/config."""
        src = _read_js("settings.js")
        for field_id in ["settCooldownTemp", "settWaitInterval",
                         "settIterations", "settWarmup", "settFpsThreshold"]:
            assert field_id in src, f"settings.js must reference {field_id}"
        # load() must assign these from server data, not just hardcode in HTML
        load_block = src.split("load:")[1] if "load:" in src else ""
        for key in ["cooldown_temp", "wait_interval", "iterations",
                     "warmup", "fps_threshold"]:
            assert key in load_block, (
                f"settings.js load() must read '{key}' from server response"
            )
