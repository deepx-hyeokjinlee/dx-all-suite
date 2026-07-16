"""Run orchestration helpers – ID generation, resume logic, backfill utilities.

Extracted from __main__.py to reduce file size.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime
from pathlib import Path

from .config import BenchmarkConfig
from .npu_monitor import parse_npu_log_temp_clock
from .pipeline_sweeps import get_boundary_search_start
from .report_models import _build_legacy_timing_history
from .reporter import save_results_csv, save_results_json
from .result_layout import make_hw_id


def _make_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_resume_dir(resume_arg: str | None) -> Path | None:
    if not resume_arg:
        return None

    resume_path = Path(resume_arg)
    if resume_path.is_absolute():
        return resume_path

    # Keep documented `results/...` usage stable regardless of the caller's cwd.
    if resume_path.parts and resume_path.parts[0] == "results":
        return (Path(__file__).resolve().parent / resume_path).resolve()

    return resume_path.resolve()


def _resolve_output_dir(
    cfg: BenchmarkConfig,
    resume_dir: Path | None,
    fingerprint: dict,
    run_id: str,
) -> Path:
    if resume_dir:
        return resume_dir
    return cfg.get_output_dir() / make_hw_id(fingerprint) / run_id


def _parse_npu_log_filename(name: str) -> tuple[str, str, str] | None:
    """Extract (model, category, ort_tag) from an .npu.log filename.

    Supported patterns:
      model results:   {model}.throughput.run{N}.ort_{on|off}.npu.log
                       {model}.latency.run{N}.ort_{on|off}.npu.log
      pipeline:        {model}.e2e.single.ort_{on|off}.run{N}.npu.log
      multi-stream:    {model}.e2e.multi.ort_{on|off}.sc{S}.run{N}.npu.log

    Returns (model, category, ort_tag) where category is one of:
      'throughput', 'latency', 'e2e.single', 'e2e.multi'
    """
    stem = (name[:-8] if name.endswith(".npu.log") else name)
    tokens = stem.split(".")

    # Model results: ...throughput.runN.ort_on  or  ...latency.runN.ort_on
    if len(tokens) >= 4:
        ort_tag = tokens[-1]
        if ort_tag in ("ort_on", "ort_off"):
            family = tokens[-3]
            if family in ("throughput", "latency"):
                model = ".".join(tokens[:-3])
                return (model, family, ort_tag)

    # Pipeline: ...e2e.single.ort_on.runN  or  ...e2e.multi.ort_on.scS.runN
    for i, t in enumerate(tokens):
        if t == "e2e" and i + 2 < len(tokens):
            mode = tokens[i + 1]  # single or multi
            ort_tag = tokens[i + 2]
            if ort_tag in ("ort_on", "ort_off") and mode in ("single", "multi"):
                model = ".".join(tokens[:i])
                return (model, f"e2e.{mode}", ort_tag)

    return None


def _backfill_from_raw_logs(results: list[dict], raw_dir: Path, category: str) -> int:
    """Re-parse raw .npu.log files to fill missing npu_temp/clock min/max.

    *category* selects which log files to use:
      'throughput' | 'latency' | 'e2e.single' | 'e2e.multi'

    Returns the number of records patched.
    """
    # Build lookup: (model, ort_tag) → list of .npu.log paths
    npu_logs: dict[tuple[str, str], list[Path]] = {}
    for p in sorted(raw_dir.glob("*.npu.log")):
        parsed = _parse_npu_log_filename(p.name)
        if parsed is None or parsed[1] != category:
            continue
        model, _cat, ort_tag = parsed
        npu_logs.setdefault((model, ort_tag), []).append(p)

    patched = 0
    for rec in results:
        has_temp = rec.get("npu_temp_min_c") is not None
        has_clock_max = rec.get("npu_clock_mhz_max") is not None
        if has_temp and has_clock_max:
            continue

        model = rec.get("model", "")
        ort_tag = "ort_on" if rec.get("use_ort") else "ort_off"
        logs = npu_logs.get((model, ort_tag))
        if not logs:
            continue

        all_temp_min, all_temp_max = [], []
        all_clock_min, all_clock_max = [], []
        for log_path in logs:
            try:
                raw_text = log_path.read_text(errors="replace")
            except OSError:
                continue
            parsed_vals = parse_npu_log_temp_clock(raw_text)
            if parsed_vals["npu_temp_min_c"] is not None:
                all_temp_min.append(parsed_vals["npu_temp_min_c"])
            if parsed_vals["npu_temp_max_c"] is not None:
                all_temp_max.append(parsed_vals["npu_temp_max_c"])
            if parsed_vals["npu_clock_mhz_min"] is not None:
                all_clock_min.append(parsed_vals["npu_clock_mhz_min"])
            if parsed_vals["npu_clock_mhz_max"] is not None:
                all_clock_max.append(parsed_vals["npu_clock_mhz_max"])

        changed = False
        if not has_temp and all_temp_min:
            rec["npu_temp_min_c"] = round(min(all_temp_min), 1)
            rec["npu_temp_max_c"] = round(max(all_temp_max), 1)
            changed = True
        if not has_clock_max and all_clock_max:
            rec["npu_clock_mhz_max"] = round(max(all_clock_max), 0)
            if all_clock_min:
                rec["npu_clock_mhz_min"] = round(min(all_clock_min), 0)
            changed = True
        if changed:
            patched += 1

    return patched



def _parse_run_log_filename(name: str) -> tuple[str, str, str, int | None] | None:
    """Extract (model, category, ort_tag, stream_count) from a .log filename.

    Supported patterns (excluding .npu.log and warmup):
      throughput:   {model}.throughput.run{N}.ort_{on|off}.log
      e2e.single:   {model}.e2e.single.ort_{on|off}.run{N}.log
      e2e.multi:    {model}.e2e.multi.ort_{on|off}.sc{S}.run{N}.log

    Returns (model, category, ort_tag, stream_count) or None.
    stream_count is None for throughput and e2e.single.
    """
    if name.endswith(".npu.log") or "warmup" in name:
        return None
    if not name.endswith(".log"):
        return None

    stem = (name[:-4] if name.endswith(".log") else name)
    tokens = stem.split(".")

    # Throughput: {model}.throughput.run{N}.ort_{on|off}
    if len(tokens) >= 4:
        ort_tag = tokens[-1]
        if ort_tag in ("ort_on", "ort_off"):
            family = tokens[-3]
            if family == "throughput" and tokens[-2].startswith("run"):
                model = ".".join(tokens[:-3])
                return (model, "throughput", ort_tag, None)

    # Pipeline: {model}.e2e.single.ort_{on|off}.run{N}
    # Multi:    {model}.e2e.multi.ort_{on|off}.sc{S}.run{N}
    for i, t in enumerate(tokens):
        if t == "e2e" and i + 2 < len(tokens):
            mode = tokens[i + 1]
            ort_tag = tokens[i + 2]
            if ort_tag not in ("ort_on", "ort_off") or mode not in ("single", "multi"):
                continue
            model = ".".join(tokens[:i])
            sc = None
            if mode == "multi":
                for tok in tokens[i + 3:]:
                    m = re.match(r"sc(\d+)", tok)
                    if m:
                        sc = int(m.group(1))
                        break
            return (model, f"e2e.{mode}", ort_tag, sc)

    return None


def _backfill_fps_std(results: list[dict], raw_dir: Path, category: str) -> int:
    """Compute fps_std from raw run logs for results that lack it.

    *category*: 'throughput' | 'e2e.single' | 'e2e.multi'

    For throughput: parses FPS from 'FPS : xx.xx' in each run log.
    For e2e: parses 'Execution ended after H:MM:SS.nnn' and uses frame_count.

    Returns the number of records patched.
    """
    # Build lookup: key → list of (log_path, stream_count)
    # key = (model, ort_tag) for throughput/single, (model, ort_tag, sc) for multi
    run_logs: dict[tuple, list[Path]] = {}
    for p in sorted(raw_dir.glob("*.log")):
        parsed = _parse_run_log_filename(p.name)
        if parsed is None or parsed[1] != category:
            continue
        model, _cat, ort_tag, sc = parsed
        if category == "e2e.multi":
            key = (model, ort_tag, sc)
        else:
            key = (model, ort_tag)
        run_logs.setdefault(key, []).append(p)

    patched = 0
    for rec in results:
        if rec.get("fps_std") is not None:
            continue

        model = rec.get("model", "")
        ort_tag = "ort_on" if rec.get("use_ort") else "ort_off"
        if category == "e2e.multi":
            sc = rec.get("stream_count")
            key = (model, ort_tag, sc)
        else:
            key = (model, ort_tag)

        logs = run_logs.get(key)
        if not logs:
            continue

        fps_values: list[float] = []
        for log_path in logs:
            try:
                text = log_path.read_text(errors="replace")
            except OSError:
                continue

            if category == "throughput":
                # Parse FPS : xx.xx
                m = re.search(r"FPS\s*:\s*([\d.]+)", text)
                if m:
                    fps_values.append(float(m.group(1)))
            else:
                # Parse Execution ended after H:MM:SS.nnn
                m = re.search(r"Execution ended after\s+(\d+):(\d+):([\d.]+)", text)
                if m:
                    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                    frame_count = rec.get("frame_count", 0)
                    if secs > 0 and frame_count > 0:
                        fps_values.append(frame_count / secs)

        if len(fps_values) >= 2:
            rec["fps_std"] = round(statistics.stdev(fps_values), 2)
            patched += 1

    return patched



# Fields to copy from single-stream results into sc=1 multi-stream entries
_SC1_BACKFILL_FIELDS = [
    "npu_core0_avg_pct", "npu_core0_max_pct",
    "npu_core1_avg_pct", "npu_core1_max_pct",
    "npu_core2_avg_pct", "npu_core2_max_pct",
    "npu_total_avg_pct", "npu_total_max_pct",
    "npu_mem_max_mib", "npu_samples",
    "npu_temp_min_c", "npu_temp_max_c",
    "npu_clock_mhz_min", "npu_clock_mhz_max",
    "npu_throttled",
    "decoder", "pipeline_caps", "fps_std",
]


def _backfill_sc1_from_single_stream(
    multi_results: list[dict],
    pipeline_results: list[dict],
) -> int:
    """Patch multi-stream sc=1 entries with data from single-stream results.

    When multi-stream sc=1 entries were created by an older version of
    ``_make_sc1_from_single_stream`` that didn't copy NPU stats, decoder,
    etc., those fields are None/unknown.  This function fills them in from
    the matching single-stream pipeline result so that the report shows
    correct values without re-running the benchmark.

    Returns the number of records patched.
    """
    # Build lookup: (model, use_ort) → single-stream result dict
    single_lookup: dict[tuple[str, bool], dict] = {}
    for r in pipeline_results:
        if r.get("stream_count", 1) == 1:
            key = (r["model"], bool(r.get("use_ort")))
            single_lookup[key] = r

    patched = 0
    for rec in multi_results:
        if rec.get("stream_count") != 1:
            continue

        key = (rec["model"], bool(rec.get("use_ort")))
        single = single_lookup.get(key)
        if single is None:
            continue

        changed = False
        for field in _SC1_BACKFILL_FIELDS:
            src_val = single.get(field)
            dst_val = rec.get(field)
            # Backfill if destination is missing/None or is a placeholder
            if src_val is not None and (
                dst_val is None
                or (field == "decoder" and dst_val == "unknown")
            ):
                rec[field] = src_val
                changed = True
        if changed:
            patched += 1

    return patched


def _save_result_set(results: list[dict], csv_path: Path, json_path: Path) -> None:
    save_results_csv(results, csv_path)
    save_results_json(results, json_path)


def _make_timing_history_entry(
    cfg: BenchmarkConfig,
    families: list[str],
    resume_dir: Path | None,
    retry_failed: bool,
    start_iso: str,
    end_iso: str,
    duration_sec: float,
    outcome: str = "completed",
    failure_stage: str | None = None,
    failure_model: str | None = None,
    failure_ort: str | None = None,
    failure_reason: str | None = None,
) -> dict:
    if resume_dir and retry_failed:
        mode = "retry-failed"
    elif resume_dir:
        mode = "resume"
    else:
        mode = "run"

    entry = {
        "mode": mode,
        "start": start_iso,
        "end": end_iso,
        "duration_sec": round(duration_sec, 1),
        "families": families,
        "task": cfg.task,
        "sizes": list(cfg.sizes),
        "retry_failed": retry_failed,
        "outcome": outcome,
    }

    if failure_stage:
        entry["failure_stage"] = failure_stage
    if failure_model:
        entry["failure_model"] = failure_model
    if failure_ort:
        entry["failure_ort"] = failure_ort
    if failure_reason:
        entry["failure_reason"] = failure_reason

    return entry


def _load_timing_history(fingerprint: dict) -> list[dict]:
    history = fingerprint.get("timing_history")
    if isinstance(history, list):
        return list(history)

    return _build_legacy_timing_history(fingerprint)


def _is_failed_result(result: dict | None) -> bool:
    if not result:
        return False
    return result.get("status") not in {"ok", "partial"}


def _should_retry_failed(result: dict | None, retry_failed: bool) -> bool:
    return bool(retry_failed and _is_failed_result(result))


def _upsert_result(results: list[dict], new_result: dict, key_func) -> None:
    new_key = key_func(new_result)
    for idx in range(len(results) - 1, -1, -1):
        if key_func(results[idx]) == new_key:
            results[idx] = new_result
            return
    results.append(new_result)


def _get_resume_stream_start(
    existing_results: list[dict],
    fps_threshold: float,
    retry_failed: bool = False,
    single_stream_fps: float = 0.0,
) -> int | None:
    if not existing_results:
        return get_boundary_search_start([], fps_threshold, single_stream_fps)

    if retry_failed:
        failed_results = [result for result in existing_results if _is_failed_result(result)]
        if not failed_results:
            return None

        # Retry search should follow the original boundary-search strategy.
        # Failed rows are retried, but they do not determine the new start point.
        search_results = [result for result in existing_results if not _is_failed_result(result)]
        return get_boundary_search_start(search_results, fps_threshold, single_stream_fps)

    return get_boundary_search_start(existing_results, fps_threshold, single_stream_fps)
