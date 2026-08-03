"""Canonical, side-effect-free workflow helpers for the Lab Composer."""

import ast
import re
import secrets
from pathlib import Path


WORKFLOW_SCHEMA_VERSION = 1
CORE_STAGES = (
    "input",
    "builtin_preprocess",
    "inference",
    "builtin_postprocess",
    "builtin_visualizer",
)
PLUGIN_STAGES = ("preprocess", "postprocess")
PLUGIN_LANGUAGES = ("python", "cpp")
PLUGIN_INTERFACE_VERSION = 1
SUPPORTED_NODE_KINDS = CORE_STAGES
PACKAGE_TYPES = ("recipe", "run", "developer")

# Keep template data declarative so routes/UI can present it without duplicating
# the category and input compatibility rules.
WORKFLOW_TEMPLATES = {
    "classification_image": {"category": "classification", "input_kind": "image"},
    "detection_image": {"category": "object_detection", "input_kind": "image"},
    "segmentation_image": {"category": "semantic_segmentation", "input_kind": "image"},
    "pose_image": {"category": "pose_estimation", "input_kind": "image"},
    "ocr_image": {"category": "ocr", "input_kind": "image"},
    "video": {"input_kind": "video"},
    "camera": {"input_kind": "camera"},
}

_VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".webm"}
_SCAFFOLD_MARKERS = ("notimplemented", "not_implemented", "implement_me", "plugin_scaffold", "todo")
_CPP_PLUGIN_SIGNATURES = {
    "preprocess": re.compile(
        r"std::string\s+preprocess\s*\(\s*const\s+std::string\s*&\s*input_path\s*,"
        r"\s*const\s+PluginContext\s*&\s*context\s*\)",
        re.MULTILINE,
    ),
    "postprocess": re.compile(
        r"std::string\s+postprocess\s*\(\s*const\s+std::string\s*&\s*output_path\s*,"
        r"\s*const\s+PluginContext\s*&\s*context\s*\)",
        re.MULTILINE,
    ),
}
_CPP_PLUGIN_MARKERS = (
    "#pragma once",
    "#include <string>",
    "namespace dx_app_lab",
    "struct PluginContext",
)


def new_workflow_id():
    """Return an opaque, process-independent workflow identifier."""
    return "workflow_" + secrets.token_urlsafe(12).replace("-", "_")


def _normalise(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _filename(value):
    return Path(str(value or "")).name


def _is_runnable(model):
    return (
        isinstance(model, dict)
        and model.get("model_exists") is True
        and bool(model.get("cpp_sync") or model.get("py_sync"))
    )


def resolve_runnable_model(selection, models):
    """Resolve a selection to a runnable registry entry, never to catalog data."""
    if not isinstance(selection, dict):
        return None
    runnable = [model for model in (models or ()) if _is_runnable(model)]
    selected_file = _filename(
        selection.get("model_file") or selection.get("filename") or selection.get("file")
    )
    if selected_file:
        for model in runnable:
            if _normalise(_filename(model.get("model_file"))) == _normalise(selected_file):
                return dict(model)
    selected_name = _normalise(selection.get("name"))
    if selected_name:
        for model in runnable:
            if _normalise(model.get("name")) == selected_name:
                return dict(model)
    return None


def _canonical_model(model):
    if not model:
        return {}
    language = "cpp" if model.get("cpp_sync") else "python"
    return {
        "name": model.get("name", ""),
        "category": model.get("category", ""),
        "model_file": model.get("model_file", ""),
        "language": language,
        "variant": "sync",
    }


def _input_kind_for_category(category):
    return "video" if "video" in _normalise(category) else "image"


def _asset_details(asset):
    if isinstance(asset, dict):
        path = asset.get("path", "")
        kind = asset.get("kind") or asset.get("input_kind") or asset.get("type")
    else:
        path = asset or ""
        kind = None
    if not kind and path:
        kind = "video" if Path(str(path)).suffix.lower() in _VIDEO_SUFFIXES else "image"
    return str(path), kind


def _compatible_asset(assets, input_kind):
    for asset in assets or ():
        path, kind = _asset_details(asset)
        if path and kind == input_kind:
            return path
    return None


def _core_nodes():
    return [
        {"id": "input", "kind": "input", "enabled": True, "params": {}},
        {"id": "preprocess", "kind": "builtin_preprocess", "enabled": True, "params": {}},
        {"id": "inference", "kind": "inference", "enabled": True, "params": {}},
        {"id": "postprocess", "kind": "builtin_postprocess", "enabled": True, "params": {}},
        {"id": "visualize", "kind": "builtin_visualizer", "enabled": True, "params": {}},
    ]


def _workflow(model, input_kind, input_path, source, template_id):
    return {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "id": new_workflow_id(),
        "source": source,
        "template_id": template_id,
        "model": _canonical_model(model),
        "input": {"kind": input_kind, "path": input_path or ""},
        "nodes": _core_nodes(),
        "plugins": [],
        "execution": {"device_id": None, "save_output": True},
    }


def build_quick_start_workflow(selection, models, assets, template_id=None):
    """Build a canonical Quick Start manifest from a verified registry model."""
    model = resolve_runnable_model(selection, models)
    input_kind = (
        WORKFLOW_TEMPLATES.get(template_id, {}).get("input_kind")
        if template_id else None
    ) or _input_kind_for_category((model or selection or {}).get("category"))
    asset = _compatible_asset(assets, input_kind)
    workflow = _workflow(model, input_kind, asset, "quick_start", template_id)

    blockers = []
    if not model:
        blockers.append({"node_id": "model", "code": "runnable_model_not_found"})
    if not asset:
        blockers.append({"node_id": "input", "code": "compatible_input_not_found"})
    workflow["validation"] = (
        {"status": "blocked", "blockers": blockers, "warnings": []}
        if blockers else validate_workflow(workflow)
    )
    return workflow


def build_template_workflow(template_id, models, images, videos):
    """Build a template workflow using the first compatible runnable registry model."""
    template = WORKFLOW_TEMPLATES.get(template_id)
    if template is None:
        workflow = _workflow(None, "unknown", "", "template", template_id)
        workflow["validation"] = {
            "status": "blocked",
            "blockers": [{"node_id": "template", "code": "template_not_found"}],
            "warnings": [],
        }
        return workflow

    category = template.get("category")
    input_kind = template["input_kind"]
    candidate = next(
        (model for model in (models or ())
         if _is_runnable(model) and (not category or model.get("category") == category)),
        None,
    )
    if input_kind == "camera":
        workflow = _workflow(candidate, input_kind, "", "template", template_id)
        workflow["validation"] = validate_workflow(workflow)
        return workflow

    selection = {"model_file": candidate.get("model_file", "")} if candidate else {
        "category": category,
    }
    assets = images if input_kind == "image" else videos
    return build_quick_start_workflow(selection, models, assets, template_id=template_id)


def _add(blockers, node_id, code):
    item = {"node_id": node_id, "code": code}
    if item not in blockers:
        blockers.append(item)


def _safe_plugin_file(entrypoint, stage, plugin_root):
    """Return a safely resolved plugin source, or a validation error code."""
    raw = Path(str(entrypoint or ""))
    parts = raw.parts
    if (
        not entrypoint or raw.is_absolute() or ".." in parts
        or len(parts) < 3 or parts[0] != "plugins" or parts[1] != stage
    ):
        return None, "plugin_path_unsafe"
    if plugin_root is None:
        return None, "plugin_root_unavailable"
    root = Path(plugin_root).resolve()
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None, "plugin_path_unsafe"
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None, "plugin_path_unsafe"
    if not resolved.exists() or not resolved.is_file() or resolved.is_symlink():
        return None, "plugin_not_found"
    return resolved, None


def _python_plugin_complete(source, stage):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    expected = "preprocess" if stage == "preprocess" else "postprocess"
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == expected:
            args = [arg.arg for arg in node.args.args]
            if args[:2] == (["image", "context"] if expected == "preprocess" else ["outputs", "context"]):
                return True
    return False


def _plugin_complete(path, language, stage):
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lowered = source.lower()
    if any(marker in lowered for marker in _SCAFFOLD_MARKERS):
        return False
    expected = "preprocess" if stage == "preprocess" else "postprocess"
    if language == "python":
        return _python_plugin_complete(source, stage)
    return (
        all(marker in source for marker in _CPP_PLUGIN_MARKERS)
        and bool(_CPP_PLUGIN_SIGNATURES[expected].search(source))
    )


def _cpp_plugin_registered(path, plugin_root):
    """Return whether the generated CMake source list includes the plugin file."""
    root = Path(plugin_root).resolve()
    cmake = root / "CMakeLists.txt"
    if cmake.is_symlink() or not cmake.is_file():
        return False
    try:
        return path.relative_to(root).as_posix() in cmake.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return False


def validate_workflow(workflow, plugin_root=None):
    """Validate manifest structure and plugin sources without executing them."""
    blockers = []
    warnings = []
    if not isinstance(workflow, dict):
        return {"status": "blocked", "blockers": [{"node_id": "workflow", "code": "workflow_invalid"}], "warnings": warnings}
    if workflow.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
        _add(blockers, "workflow", "schema_version_unsupported")

    model = workflow.get("model")
    if not isinstance(model, dict) or not all(model.get(key) for key in ("name", "category", "model_file")):
        _add(blockers, "model", "model_invalid")
    elif model.get("language") not in ("cpp", "python") or model.get("variant") != "sync":
        _add(blockers, "model", "model_variant_invalid")

    input_data = workflow.get("input")
    if not isinstance(input_data, dict) or input_data.get("kind") not in ("image", "video", "camera"):
        _add(blockers, "input", "input_invalid")
    elif input_data.get("kind") == "camera" and not input_data.get("path"):
        _add(blockers, "input", "camera_input_not_available")
    elif input_data.get("kind") in ("image", "video") and not input_data.get("path"):
        _add(blockers, "input", "input_invalid")

    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        _add(blockers, "nodes", "nodes_invalid")
        nodes = []
    enabled = [node for node in nodes if isinstance(node, dict) and node.get("enabled")]
    for node in enabled:
        if node.get("kind") not in SUPPORTED_NODE_KINDS:
            _add(blockers, node.get("id", "node"), "unknown_node_kind")

    enabled_kinds = [node.get("kind") for node in enabled]
    inference_count = enabled_kinds.count("inference")
    if inference_count == 0:
        _add(blockers, "inference", "inference_required")
    elif inference_count != 1:
        _add(blockers, "inference", "inference_count_invalid")
    for kind in CORE_STAGES:
        matching = [node for node in nodes if isinstance(node, dict) and node.get("kind") == kind]
        enabled_matching = [node for node in matching if node.get("enabled")]
        if kind != "inference" and len(enabled_matching) != 1:
            _add(
                blockers,
                (enabled_matching or matching)[0].get("id", kind) if (enabled_matching or matching) else kind,
                "core_stage_required",
            )
        elif len(enabled_matching) > 1:
            _add(blockers, kind, "core_stage_count_invalid")
    ordered_core = [kind for kind in enabled_kinds if kind in CORE_STAGES]
    if ordered_core != list(CORE_STAGES):
        expected_index = 0
        for node in enabled:
            kind = node.get("kind")
            if kind not in CORE_STAGES:
                continue
            if expected_index >= len(CORE_STAGES) or kind != CORE_STAGES[expected_index]:
                expected_kind = CORE_STAGES[expected_index] if expected_index < len(CORE_STAGES) else kind
                expected_nodes = [item for item in nodes if isinstance(item, dict) and item.get("kind") == expected_kind]
                _add(
                    blockers,
                    expected_nodes[0].get("id", expected_kind) if expected_nodes else node.get("id", kind),
                    "core_stage_order_invalid",
                )
                break
            expected_index += 1

    plugins = workflow.get("plugins", [])
    if not isinstance(plugins, list):
        _add(blockers, "plugins", "plugins_invalid")
        plugins = []
    for plugin in plugins:
        if not isinstance(plugin, dict) or not plugin.get("enabled"):
            continue
        plugin_id = plugin.get("id", "plugin")
        stage = plugin.get("stage")
        language = plugin.get("language")
        if stage not in PLUGIN_STAGES:
            _add(blockers, plugin_id, "plugin_stage_invalid")
            continue
        if language not in PLUGIN_LANGUAGES or plugin.get("interface_version") != PLUGIN_INTERFACE_VERSION:
            _add(blockers, plugin_id, "plugin_interface_invalid")
            continue
        path, error = _safe_plugin_file(plugin.get("entrypoint"), stage, plugin_root)
        if error:
            _add(blockers, plugin_id, error)
        elif not _plugin_complete(path, language, stage):
            _add(blockers, plugin_id, "plugin_incomplete")
        elif language == "cpp" and not _cpp_plugin_registered(path, plugin_root):
            _add(blockers, plugin_id, "plugin_cmake_source_missing")

    return {"status": "blocked" if blockers else "ready", "blockers": blockers, "warnings": warnings}