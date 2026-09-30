"""Tests for dx_app postprocessor path resolution."""

from dx_modelzoo.core.catalog import reload_catalog
from dx_modelzoo.core.postprocessor_paths import (
    format_postprocessor_path,
    resolve_postprocessor_path,
)


def test_format_postprocessor_path_uses_dx_app_prefix():
    assert format_postprocessor_path("yolov8") == (
        "dx_app/src/python_example/common/processors/yolov8_postprocessor.py"
    )


def test_resolve_postprocessor_path_for_yolo_model():
    path = resolve_postprocessor_path({"id": "yolov8n", "category": "object_detection"})
    assert path == "dx_app/src/python_example/common/processors/yolov8_postprocessor.py"


def test_resolve_postprocessor_path_for_ppu_model():
    path = resolve_postprocessor_path({"id": "scrfd500m_ppu", "category": "ppu"})
    assert path == "dx_app/src/python_example/common/processors/scrfd_ppu_postprocessor.py"


def test_resolve_postprocessor_path_for_classification_model():
    path = resolve_postprocessor_path({"id": "deit_base", "category": "classification"})
    assert path.endswith("/deit_postprocessor.py")


def test_reload_catalog_fills_postprocessor_for_all_models():
    reload_catalog()
    from dx_modelzoo.core.catalog import get_catalog

    models = get_catalog()["models"]
    assert models
    # publish page 에만 있는 새 model (anomaly · matting …) 은 지금의 dx_app 에 예제가 없어 후처리기를 모른다 —
    # per-model layout 의 config.json 이 그것을 말한다 (spec 2026-10-01 dx_app per-model layout 결정 8).
    missing = [m["id"] for m in models if not (m.get("technical") or {}).get("postprocessor")
               and not m.get("publish_only")]
    assert not missing, f"missing postprocessor path: {missing[:5]}"
