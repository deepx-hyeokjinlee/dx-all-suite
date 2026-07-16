"""Pipeline sweep and capacity-search helpers.

Extracted from runner_pipeline.py to reduce file size.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from .config import BenchmarkConfig
from .model_catalog import ModelEntry

if TYPE_CHECKING:
    from .runner_pipeline import PipelineResult

# Safety cap to prevent infinite loops (in practice FPS always declines first)
_MAX_SWEEP_STREAMS = 128


def is_capacity_pass(result: PipelineResult | dict, fps_threshold: float) -> bool:
    """Return True when a result satisfies the fixed stable-capacity rule."""
    status = result["status"] if isinstance(result, dict) else result.status
    runs = int(result.get("runs", 0) if isinstance(result, dict) else result.runs)
    requested_runs = int(
        result.get("requested_runs", runs) if isinstance(result, dict) else result.requested_runs
    )
    avg_per_channel_fps = float(
        result.get("avg_per_channel_fps", 0.0) if isinstance(result, dict) else result.avg_per_channel_fps
    )
    return status == "ok" and runs == requested_runs and avg_per_channel_fps >= fps_threshold


def estimate_start_stream(single_stream_fps: float, fps_threshold: float) -> int:
    """Estimate the initial stream count from single-stream E2E FPS."""
    if fps_threshold <= 0:
        return 1
    return max(1, int(single_stream_fps // fps_threshold))


def get_existing_capacity(existing_results: list[dict], fps_threshold: float) -> int:
    """Return the best stable capacity from existing multi-stream results."""
    passing_streams = [
        int(result.get("stream_count", 0) or 0)
        for result in existing_results
        if is_capacity_pass(result, fps_threshold)
    ]
    return max(passing_streams, default=0)


def get_boundary_search_start(
    existing_results: list[dict],
    fps_threshold: float,
    single_stream_fps: float,
) -> int | None:
    """Choose the next stream count for boundary search from existing results."""
    if not existing_results:
        return estimate_start_stream(single_stream_fps, fps_threshold)

    latest_by_stream: dict[int, dict] = {}
    for result in existing_results:
        stream_count = int(result.get("stream_count", 0) or 0)
        latest_by_stream[stream_count] = result

    pass_streams = sorted(
        stream for stream, result in latest_by_stream.items() if is_capacity_pass(result, fps_threshold)
    )
    fail_streams = sorted(
        stream for stream, result in latest_by_stream.items() if not is_capacity_pass(result, fps_threshold)
    )

    max_pass = max(pass_streams, default=0)
    min_fail = min(fail_streams, default=_MAX_SWEEP_STREAMS + 1)

    if max_pass and min_fail == max_pass + 1:
        return None
    if fail_streams and not pass_streams:
        return max(1, min_fail - 1)
    if pass_streams and not fail_streams:
        return min(_MAX_SWEEP_STREAMS, max_pass + 1)
    if pass_streams and fail_streams:
        candidate = max_pass + 1
        if candidate < min_fail:
            return candidate
        return None
    return estimate_start_stream(single_stream_fps, fps_threshold)


def run_multi_stream_sweep(
    model: ModelEntry,
    use_ort: bool,
    cfg: BenchmarkConfig,
    save_dir: Optional[Path] = None,
    start_stream: int = 1,
    existing_results: Optional[list[dict]] = None,
    retry_stream_counts: Optional[set[int]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
    result_callback: Optional[Callable[["PipelineResult"], None]] = None,
    single_stream_result: Optional[dict] = None,
) -> list[PipelineResult]:
    """Find the multi-stream boundary starting from a single-stream FPS-based estimate."""
    from .runner_pipeline import run_multi_stream  # deferred to avoid circular import

    known_results = {int(item.get("stream_count", 0) or 0): item for item in (existing_results or [])}
    results: list[PipelineResult] = []
    current = max(1, start_stream)
    direction: int | None = None
    retry_stream_counts = {
        stream_count for stream_count in (retry_stream_counts or set()) if stream_count > 0
    }
    visited: set[int] = set(known_results) - retry_stream_counts
    retried_streams: set[int] = set()  # tracks timeout retries (max 1 per stream count)

    while 1 <= current <= _MAX_SWEEP_STREAMS and current not in visited:
        if progress_callback is not None:
            progress_callback(current)

        # Reuse single-stream result for 1ch instead of running pipeline
        if current == 1 and single_stream_result and single_stream_result.get("status") in ("ok", "partial"):
            result = _make_sc1_from_single_stream(single_stream_result)
            print(f"    [multi 1ch] reusing single-stream: "
                  f"{result.avg_per_channel_fps:.1f} fps/ch", flush=True)
        else:
            result = run_multi_stream(model, use_ort, current, cfg, save_dir)

            # Retry once on timeout (multi-stream init can deadlock intermittently)
            if result.status == "timeout" and current not in retried_streams:
                retried_streams.add(current)
                print(f"    [multi {current}ch] retrying after timeout ...", flush=True)
                result = run_multi_stream(model, use_ort, current, cfg, save_dir)

        results.append(result)
        if result_callback is not None:
            result_callback(result)
        visited.add(current)

        passed = is_capacity_pass(result, cfg.fps_threshold)
        if direction is None:
            direction = 1 if passed else -1

        if direction == 1 and passed:
            current += 1
            continue
        if direction == -1 and not passed:
            current -= 1
            continue

        break

    return results


def _make_sc1_from_single_stream(single_result: dict) -> PipelineResult:
    """Convert a single-stream pipeline result dict to a multi-stream sc=1 PipelineResult."""
    from .runner_pipeline import PipelineResult as _PipelineResult  # deferred to avoid circular import

    # Extract npu_stats fields from the flat single_result dict
    npu_keys = [k for k in single_result if k.startswith("npu_")]
    npu_stats = {k: single_result[k] for k in npu_keys} if npu_keys else None

    return _PipelineResult(
        model=single_result.get("model", ""),
        task=single_result.get("task", ""),
        size=single_result.get("size", ""),
        use_ort=bool(single_result.get("use_ort")),
        video=single_result.get("video", ""),
        stream_count=1,
        frame_count=int(single_result.get("frame_count", 0)),
        runs=int(single_result.get("runs", 0)),
        requested_runs=int(single_result.get("requested_runs", 0)),
        timeout_runs=int(single_result.get("timeout_runs", 0)),
        decoder=single_result.get("decoder", "unknown"),
        avg_time_sec=float(single_result.get("avg_time_sec", 0.0)),
        avg_e2e_fps=float(single_result.get("avg_e2e_fps", 0.0)),
        fps_std=float(single_result["fps_std"]) if single_result.get("fps_std") is not None else None,
        avg_per_channel_fps=float(single_result.get("avg_e2e_fps", 0.0)),
        avg_cpu_pct=float(single_result.get("avg_cpu_pct", 0.0)),
        max_rss_mib=float(single_result.get("max_rss_mib", 0.0)),
        npu_stats=npu_stats,
        pipeline_caps=single_result.get("pipeline_caps"),
        status=single_result.get("status", "ok"),
        source="single_stream",
    )

