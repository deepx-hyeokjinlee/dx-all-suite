"""RED contracts for Lab Composer workflow resolution and validation."""

import pytest

from dx_app.core.lab_portal import lab_capabilities
from dx_app.core.lab_workflow import (
    _is_runnable,
    build_quick_start_workflow,
    build_template_workflow,
    validate_workflow,
)


def _runnable_models():
    return [{
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp": True,
        "cpp_sync": True,
    }]


def _workflow(**updates):
    workflow = {
        "schema_version": 1,
        "model": {
            "name": "resnet18",
            "category": "classification",
            "model_file": "assets/models/resnet18_224x224.dxnn",
            "language": "cpp",
            "variant": "sync",
        },
        "input": {"kind": "image", "path": "sample/img/sample_dog.jpg"},
        "nodes": [
            {"id": "input", "kind": "input", "enabled": True, "params": {}},
            {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
            {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
            {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
            {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
        ],
        "plugins": [],
        "execution": {"save_output": True},
    }
    workflow.update(updates)
    return workflow


def test_quick_start_uses_runnable_registry_identity_only():
    workflow = build_quick_start_workflow(
        {"name": "ResNet-18", "category": "Image Classification"},
        models=_runnable_models(),
        assets=["sample/img/sample_dog.jpg"],
    )

    assert workflow["schema_version"] == 1
    assert workflow["id"].startswith("workflow_")
    assert workflow["source"] == "quick_start"
    assert workflow["template_id"] is None
    assert workflow["model"]["name"] == "resnet18"
    assert workflow["model"]["category"] == "classification"
    assert workflow["model"]["model_file"] == "assets/models/resnet18_224x224.dxnn"
    assert workflow["input"]["path"] == "sample/img/sample_dog.jpg"
    assert workflow["nodes"] == [
        {"id": "input", "kind": "input", "enabled": True, "params": {}},
        {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
        {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
        {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
        {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
    ]
    assert workflow["plugins"] == []
    assert workflow["execution"] == {"device_id": None, "save_output": True}
    assert validate_workflow(workflow, plugin_root=None)["status"] == "ready"


def test_quick_start_does_not_fall_back_to_display_only_catalog_rows():
    workflow = build_quick_start_workflow(
        {"name": "Download-only model", "category": "Image Classification"},
        models=_runnable_models(),
        assets=["sample/img/sample_dog.jpg"],
    )

    assert workflow["validation"]["status"] == "blocked"
    assert workflow["validation"]["blockers"] == [
        {"node_id": "model", "code": "runnable_model_not_found"}
    ]


def test_workflow_with_unresolved_custom_plugin_is_blocked(tmp_path):
    workflow = _workflow(plugins=[{
        "id": "custom_postprocess",
        "stage": "postprocess",
        "language": "python",
        "entrypoint": "plugins/postprocess/missing.py",
        "interface_version": 1,
        "enabled": True,
    }])

    result = validate_workflow(workflow, plugin_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["blockers"] == [
        {"node_id": "custom_postprocess", "code": "plugin_not_found"}
    ]


def test_workflow_with_unsafe_custom_plugin_path_is_blocked(tmp_path):
    workflow = _workflow(plugins=[{
        "id": "custom_preprocess",
        "stage": "preprocess",
        "language": "python",
        "entrypoint": "../../outside.py",
        "interface_version": 1,
        "enabled": True,
    }])

    result = validate_workflow(workflow, plugin_root=tmp_path)
    assert result["status"] == "blocked"
    assert result["blockers"] == [
        {"node_id": "custom_preprocess", "code": "plugin_path_unsafe"}
    ]


@pytest.mark.parametrize(
    ("nodes", "blocker"),
    [
        (
            [
                {"id": "input", "kind": "input", "enabled": True, "params": {}},
                {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
                {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
                {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
            ],
            {"node_id": "inference", "code": "inference_required"},
        ),
        (
            [
                {"id": "input", "kind": "input", "enabled": True, "params": {}},
                {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
                {"id": "inference-1", "kind": "inference", "enabled": True, "params": {}},
                {"id": "inference-2", "kind": "inference", "enabled": True, "params": {}},
                {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
                {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
            ],
            {"node_id": "inference", "code": "inference_count_invalid"},
        ),
        (
            [
                {"id": "input", "kind": "input", "enabled": True, "params": {}},
                {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
                {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
                {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
                {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
            ],
            {"node_id": "preprocess", "code": "core_stage_order_invalid"},
        ),
        (
            [
                {"id": "input", "kind": "input", "enabled": True, "params": {}},
                {"id": "preprocess", "kind": "builtin_preprocess", "enabled": False, "params": {}},
                {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
                {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
                {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
            ],
            {"node_id": "preprocess", "code": "core_stage_required"},
        ),
    ],
)
def test_workflow_rejects_missing_duplicate_or_reordered_core_stages(nodes, blocker):
    result = validate_workflow(_workflow(nodes=nodes), plugin_root=None)
    assert result["status"] == "blocked"
    assert blocker in result["blockers"]


def test_workflow_rejects_unknown_node_kinds():
    workflow = _workflow(nodes=[
        {"id": "input", "kind": "input", "enabled": True, "params": {}},
        {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
        {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
        {"id": "unexpected", "kind": "network_request", "enabled": True, "params": {}},
        {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
        {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
    ])

    result = validate_workflow(workflow, plugin_root=None)

    assert result["status"] == "blocked"
    assert {"node_id": "unexpected", "code": "unknown_node_kind"} in result["blockers"]


@pytest.mark.parametrize("model_exists", [None, False, 0, "", "yes"])
def test_runnable_identity_requires_literal_true_model_exists(model_exists):
    model = {
        "name": "resnet18",
        "model_exists": model_exists,
        "cpp_sync": True,
    }

    assert _is_runnable(model) is False


@pytest.mark.parametrize("runner", ("cpp_sync", "py_sync"))
def test_runnable_identity_accepts_literal_true_model_exists_with_sync_runner(runner):
    model = {"name": "resnet18", "model_exists": True, runner: True}

    assert _is_runnable(model) is True


def test_composer_capabilities_publish_canonical_templates_and_package_types():
    composer = lab_capabilities()["composer"]

    assert {
        "classification_image",
        "detection_image",
        "segmentation_image",
        "pose_image",
        "ocr_image",
        "video",
        "camera",
    } <= set(composer["templates"])
    assert composer["templates"]["detection_image"] == {
        "category": "object_detection",
        "input_kind": "image",
    }
    assert composer["templates"]["segmentation_image"] == {
        "category": "semantic_segmentation",
        "input_kind": "image",
    }
    assert set(composer["package_types"]) == {"recipe", "run", "developer"}
    assert composer["feature_flags"]["developer_package_export"] is True


def test_detection_image_template_uses_matching_runnable_model_and_real_image():
    model = {
        "name": "yolov8n",
        "category": "object_detection",
        "model_file": "assets/models/yolov8n.dxnn",
        "model_exists": True,
        "py_sync": True,
    }

    workflow = build_template_workflow(
        "detection_image",
        models=[model, _runnable_models()[0]],
        images=["sample/img/sample_dog.jpg"],
        videos=[],
    )

    assert workflow["model"]["name"] == "yolov8n"
    assert workflow["input"] == {"kind": "image", "path": "sample/img/sample_dog.jpg"}
    assert workflow["validation"]["status"] == "ready"


def test_template_without_compatible_asset_and_unknown_template_are_blocked():
    model = {
        "name": "yolov8n",
        "category": "object_detection",
        "model_file": "assets/models/yolov8n.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }

    missing_asset = build_template_workflow(
        "detection_image", models=[model], images=[], videos=[]
    )
    unknown = build_template_workflow(
        "unrecognised_template", models=[model], images=["sample/img/sample_dog.jpg"], videos=[]
    )

    assert missing_asset["validation"]["status"] == "blocked"
    assert {"node_id": "input", "code": "compatible_input_not_found"} in missing_asset["validation"]["blockers"]
    assert unknown["validation"]["status"] == "blocked"
    assert {"node_id": "template", "code": "template_not_found"} in unknown["validation"]["blockers"]


def test_camera_template_without_runtime_input_is_blocked():
    workflow = build_template_workflow(
        "camera", models=_runnable_models(), images=[], videos=[]
    )

    assert workflow["input"] == {"kind": "camera", "path": ""}
    assert workflow["validation"]["status"] == "blocked"
    assert {"node_id": "input", "code": "camera_input_not_available"} in workflow["validation"]["blockers"]