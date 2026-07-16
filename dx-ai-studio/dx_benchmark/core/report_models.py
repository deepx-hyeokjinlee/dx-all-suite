"""Report ordering helpers and data grouping utilities.

Extracted from reporter.py to reduce file size.
"""
from __future__ import annotations


_SIZE_ORDER = {"n": 0, "s": 1, "m": 2, "l": 3, "x": 4}

# Canonical task display order
_TASK_DISPLAY_ORDER = {
    "object_detection": 0,
    "pose_estimation": 1,
    "segmentation": 2,
    "oriented_bbox": 3,
    "classification": 4,
}

# Friendly names for display
_TASK_DISPLAY_NAMES = {
    "object_detection": "Object Detection",
    "pose_estimation": "Pose Estimation",
    "segmentation": "Segmentation",
    "oriented_bbox": "Oriented BBox (OBB)",
    "classification": "Classification",
}

# Video group friendly names
_GROUP_DISPLAY_NAMES = {
    "cls": "Classification",
    "od_pose_seg": "Object Detection / Pose / Segmentation",
    "obb": "Oriented BBox (OBB)",
}

# Group display order
_GROUP_ORDER = {"od_pose_seg": 0, "obb": 1, "cls": 2}


def _sort_by_size(results: list[dict]) -> list[dict]:
    return sorted(results, key=lambda r: _SIZE_ORDER.get(r.get("size", ""), 99))


def _sort_models_by_size(models: list[str]) -> list[str]:
    def _size_key(name: str) -> int:
        for s, order in _SIZE_ORDER.items():
            if f"yolo26{s}-" in name or f"yolo26{s}." in name:
                return order
        return 99
    return sorted(models, key=_size_key)


def _is_usable_result(result: dict) -> bool:
    return result.get("status", "ok") in {"ok", "partial"}


def _format_runs(result: dict) -> str:
    completed = int(result.get("runs", 0) or 0)
    requested = int(result.get("requested_runs", completed) or completed)
    if requested > 0 and requested != completed:
        return f"{completed}/{requested}"
    return str(completed)


def _group_by_task(results: list[dict]) -> dict[str, list[dict]]:
    """Group results by task name, in canonical order."""
    groups: dict[str, list[dict]] = {}
    for r in results:
        task = r.get("task", "unknown")
        groups.setdefault(task, []).append(r)
    return dict(sorted(groups.items(), key=lambda kv: _TASK_DISPLAY_ORDER.get(kv[0], 99)))


def _build_legacy_timing_history(fingerprint: dict) -> list[dict]:
    """Convert legacy ``timing`` dict to a single-entry timing history list.

    Shared by report_renderers (for display) and run_orchestrator (for resume).
    """
    timing = fingerprint.get("timing")
    if not timing:
        return []
    params = fingerprint.get("benchmark_params", {})
    benchmarked_models = fingerprint.get("benchmarked_models", [])
    sizes = sorted({m.get("size") for m in benchmarked_models if m.get("size")})
    return [{
        "mode": "run",
        "start": timing.get("start"),
        "end": timing.get("end"),
        "duration_sec": timing.get("duration_sec", 0),
        "families": params.get("families", []),
        "task": "mixed",
        "sizes": sizes,
        "retry_failed": bool(params.get("retry_failed", False)),
        "outcome": "completed",
    }]

