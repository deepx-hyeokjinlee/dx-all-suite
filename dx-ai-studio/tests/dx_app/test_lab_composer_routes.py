"""RED route contracts for session-protected Lab Composer APIs."""

import pytest


COMPOSER_ROUTES = (
    "/api/lab/composer/quick_start",
    "/api/lab/composer/template",
    "/api/lab/composer/run",
    "/api/lab/composer/recipe/export",
    "/api/lab/composer/recipe/import",
)


def _ready_workflow():
    return {
        "schema_version": 1,
        "id": "workflow_route_test",
        "source": "quick_start",
        "template_id": None,
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
        "execution": {"device_id": None, "save_output": True},
        "validation": {"status": "ready", "blockers": [], "warnings": []},
    }

def _post_route(path, payload, headers=None):
    import server

    captured = {}
    handler = object.__new__(server.Handler)
    handler.command = "POST"
    handler.url_path = path
    handler.query = {}
    handler.headers = headers or {}
    handler.handle_chat_routes = lambda _engine: False
    handler.read_json_body = lambda: payload
    handler.send_json = lambda data, code=200: captured.update({"data": data, "code": code})
    handler.send_error = lambda code, *args, **kwargs: captured.update({"code": code})
    handler.route()
    return captured


@pytest.mark.parametrize("path", COMPOSER_ROUTES)
def test_composer_routes_require_x_lab_token(path):
    captured = _post_route(path, {}, headers={"Origin": "http://localhost:8080"})
    assert captured["code"] == 403
    assert captured["data"]["error"] == "Lab session required"


@pytest.mark.parametrize("path", COMPOSER_ROUTES)
def test_composer_routes_reject_hostile_origin_even_with_valid_token(path):
    from developer import lab_session

    token = lab_session()["token"]
    captured = _post_route(
        path,
        {},
        headers={"X-Lab-Token": token, "Origin": "https://evil.example.com"},
    )
    assert captured["code"] == 403
    assert captured["data"]["error"] == "Cross-origin access denied"


def test_plugin_scaffold_preview_route_requires_local_lab_session():
    from developer import lab_session

    missing_token = _post_route(
        "/api/lab/composer/plugin/dry_run",
        {},
        headers={"Origin": "http://localhost:8080"},
    )
    hostile_origin = _post_route(
        "/api/lab/composer/plugin/dry_run",
        {},
        headers={"X-Lab-Token": lab_session()["token"], "Origin": "https://evil.example.com"},
    )

    assert missing_token["code"] == 403
    assert missing_token["data"]["error"] == "Lab session required"
    assert hostile_origin["code"] == 403
    assert hostile_origin["data"]["error"] == "Cross-origin access denied"


def test_composer_run_rejects_expired_workflow_without_invoking_inference(monkeypatch):
    import lab_portal
    from developer import lab_session

    manifest = lab_portal.create_manifest(
        "composer_workflow",
        workflow={"validation": {"status": "ready"}},
    )
    with lab_portal._manifests_lock:
        lab_portal._manifests[manifest["id"]]["created_at"] = 0
    monkeypatch.setattr(
        lab_portal,
        "run_inference",
        lambda **kwargs: pytest.fail("Expired workflow must not invoke inference"),
        raising=False,
    )

    captured = _post_route(
        "/api/lab/composer/run",
        {"manifest_id": manifest["id"]},
        headers={"X-Lab-Token": lab_session()["token"], "Origin": "http://localhost:8080"},
    )

    assert captured["code"] == 404
    assert captured["data"]["error_code"] == "manifest_expired"


def test_composer_manifest_is_bound_to_its_creator_session():
    import lab_portal
    from developer import lab_session

    creator_token = lab_session()["token"]
    manifest = lab_portal.create_manifest(
        "composer_workflow",
        workflow={"validation": {"status": "ready"}},
        creator_token=creator_token,
    )

    assert manifest["creator_token"] == creator_token
    assert lab_portal.resolve_manifest(manifest["id"], token=creator_token)["id"] == manifest["id"]
    with pytest.raises(PermissionError, match="session|creator|owner"):
        lab_portal.resolve_manifest(manifest["id"], token="different-lab-session")


def test_composer_planners_issue_owner_bound_manifests_from_current_registry(monkeypatch):
    import lab_portal
    from developer import lab_session

    model = {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }
    monkeypatch.setattr(lab_portal, "get_models", lambda: [model], raising=False)
    monkeypatch.setattr(
        lab_portal, "get_images", lambda category: ["sample/img/sample_dog.jpg"], raising=False
    )
    monkeypatch.setattr(lab_portal, "get_videos", lambda: ["sample/video/sample.mp4"], raising=False)
    token = lab_session()["token"]

    quick, quick_code = lab_portal.plan_composer_quick_start(
        token, {"selection": {"name": "resnet18", "category": "classification"}}
    )
    template, template_code = lab_portal.plan_composer_template(
        token, {"template_id": "classification_image"}
    )

    assert quick_code == template_code == 200
    assert quick["manifest_id"]
    assert quick["workflow"]["model"]["model_file"] == model["model_file"]
    assert template["workflow"]["template_id"] == "classification_image"
    assert lab_portal.resolve_manifest(quick["manifest_id"], token=token)["creator_token"] == token
    with pytest.raises(PermissionError, match="session|creator|owner"):
        lab_portal.resolve_manifest(quick["manifest_id"], token="another-valid-lab-token")


def test_composer_quick_start_accepts_documented_selection_payload(monkeypatch):
    import lab_portal
    from developer import lab_session

    model = {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }
    monkeypatch.setattr(lab_portal, "get_models", lambda: [model], raising=False)
    monkeypatch.setattr(
        lab_portal, "get_images", lambda category: ["sample/img/sample_dog.jpg"], raising=False
    )

    result, code = lab_portal.plan_composer_quick_start(
        lab_session()["token"],
        {"selection": {"name": "resnet18", "category": "classification"}},
    )

    assert code == 200
    assert result["status"] == "ready"
    assert result["workflow"]["model"] == {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "language": "cpp",
        "variant": "sync",
    }


def test_composer_template_honors_requested_compatible_model_without_fallback(monkeypatch):
    import lab_portal
    from developer import lab_session

    first_detection = {
        "name": "first_detection",
        "category": "object_detection",
        "model_file": "assets/models/first_detection.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }
    requested_detection = {
        "name": "requested_detection",
        "category": "object_detection",
        "model_file": "assets/models/requested_detection.dxnn",
        "model_exists": True,
        "py_sync": True,
    }
    classification = {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }
    monkeypatch.setattr(
        lab_portal,
        "get_models",
        lambda: [first_detection, requested_detection, classification],
        raising=False,
    )
    monkeypatch.setattr(
        lab_portal, "get_images", lambda category: ["sample/img/sample_dog.jpg"], raising=False
    )
    monkeypatch.setattr(lab_portal, "get_videos", lambda: [], raising=False)
    token = lab_session()["token"]

    selected, selected_code = lab_portal.plan_composer_template(
        token,
        {"template_id": "detection_image", "model_name": "requested_detection"},
    )
    incompatible, incompatible_code = lab_portal.plan_composer_template(
        token,
        {"template_id": "detection_image", "model_name": "resnet18"},
    )

    assert selected_code == incompatible_code == 200
    assert selected["status"] == "ready"
    assert selected["workflow"]["model"]["name"] == "requested_detection"
    assert incompatible["status"] == "blocked"
    assert incompatible["workflow"]["model"] == {}
    assert {"node_id": "model", "code": "runnable_model_not_found"} in incompatible["validation"]["blockers"]


def test_composer_route_rejects_cross_token_manifest_owner(monkeypatch):
    import lab_portal
    from developer import lab_session

    token = lab_session()["token"]
    other_token = lab_session()["token"]
    manifest = lab_portal.create_manifest(
        "composer_workflow", workflow=_ready_workflow(), creator_token=token
    )
    monkeypatch.setattr(
        lab_portal,
        "run_inference",
        lambda **kwargs: pytest.fail("Wrong owner must not invoke inference"),
        raising=False,
    )

    captured = _post_route(
        "/api/lab/composer/run",
        {"manifest_id": manifest["id"]},
        headers={"X-Lab-Token": other_token, "Origin": "http://localhost:8080"},
    )

    assert captured["code"] == 403
    assert captured["data"]["error_code"] == "manifest_owner_forbidden"


def test_composer_run_rejects_blocked_workflow_without_invoking_inference(monkeypatch):
    import lab_portal
    from developer import lab_session

    token = lab_session()["token"]
    manifest = lab_portal.create_manifest(
        "composer_workflow",
        workflow={"validation": {"status": "blocked", "blockers": [{"node_id": "inference", "code": "inference_required"}]}},
        status="blocked",
        creator_token=token,
    )
    monkeypatch.setattr(
        lab_portal,
        "run_inference",
        lambda **kwargs: pytest.fail("Blocked workflow must not invoke inference"),
        raising=False,
    )

    captured = _post_route(
        "/api/lab/composer/run",
        {"manifest_id": manifest["id"]},
        headers={"X-Lab-Token": token, "Origin": "http://localhost:8080"},
    )

    assert captured["code"] == 400
    assert captured["data"]["error_code"] == "workflow_blocked"


def test_recipe_export_returns_portable_recipe_and_enforces_workflow_ownership():
    import lab_portal
    from developer import lab_session

    owner_token = lab_session()["token"]
    other_token = lab_session()["token"]
    ready_manifest = lab_portal.create_manifest(
        "composer_workflow", workflow=_ready_workflow(), creator_token=owner_token
    )

    exported = _post_route(
        "/api/lab/composer/recipe/export",
        {"manifest_id": ready_manifest["id"]},
        headers={"X-Lab-Token": owner_token, "Origin": "http://localhost:8080"},
    )

    assert exported["code"] == 200
    recipe = exported["data"]["recipe"]
    assert recipe["schema_version"] == 1
    assert "model_file" not in recipe["model"]
    assert recipe["input"] == {"kind": "image"}

    blocked_workflow = _ready_workflow()
    blocked_workflow["nodes"] = [
        node for node in blocked_workflow["nodes"] if node["id"] != "inference"
    ]
    blocked_manifest = lab_portal.create_manifest(
        "composer_workflow", workflow=blocked_workflow, status="blocked", creator_token=owner_token
    )
    blocked = _post_route(
        "/api/lab/composer/recipe/export",
        {"manifest_id": blocked_manifest["id"]},
        headers={"X-Lab-Token": owner_token, "Origin": "http://localhost:8080"},
    )

    assert blocked["code"] == 400
    assert blocked["data"]["error_code"] == "workflow_blocked"

    forbidden = _post_route(
        "/api/lab/composer/recipe/export",
        {"manifest_id": ready_manifest["id"]},
        headers={"X-Lab-Token": other_token, "Origin": "http://localhost:8080"},
    )

    assert forbidden["code"] == 403
    assert forbidden["data"]["error_code"] == "manifest_owner_forbidden"


def test_composer_run_converts_server_manifest_to_precise_inference_values(monkeypatch):
    import lab_portal
    from developer import lab_session

    workflow = _ready_workflow()
    workflow["model"]["model_file"] = "browser-supplied-stale.dxnn"
    token = lab_session()["token"]
    manifest = lab_portal.create_manifest(
        "composer_workflow", workflow=workflow, creator_token=token
    )
    invoked = {}

    def record_inference(**kwargs):
        invoked.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(lab_portal, "run_inference", record_inference, raising=False)
    monkeypatch.setattr(
        lab_portal,
        "get_models",
        lambda: [{
            "name": "resnet18",
            "category": "classification",
            "model_file": "assets/models/current_resnet18.dxnn",
            "model_exists": True,
            "cpp_sync": True,
        }],
        raising=False,
    )

    captured = _post_route(
        "/api/lab/composer/run",
        {"manifest_id": manifest["id"]},
        headers={"X-Lab-Token": token, "Origin": "http://localhost:8080"},
    )

    assert captured["code"] == 200
    assert invoked == {
        "model_name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/current_resnet18.dxnn",
        "lang": "cpp",
        "variant": "sync",
        "input_type": "image",
        "image_path": "sample/img/sample_dog.jpg",
        "video_path": None,
        "device_id": None,
        "save_output": True,
    }


@pytest.mark.parametrize(
    "recipe",
    [
        {"schema_version": 2},
        {
            "schema_version": 1,
            "plugins": [{"id": "unsafe", "entrypoint": "../../outside.py"}],
        },
        {
            "schema_version": 1,
            "model": {"name": "download_only", "category": "classification"},
        },
    ],
)
def test_recipe_import_rejects_nonportable_or_unrunnable_content(recipe):
    from developer import lab_session

    captured = _post_route(
        "/api/lab/composer/recipe/import",
        {"recipe": recipe},
        headers={"X-Lab-Token": lab_session()["token"], "Origin": "http://localhost:8080"},
    )

    assert captured["code"] == 400
    assert captured["data"]["error_code"] in {
        "recipe_schema_unsupported",
        "plugin_path_unsafe",
        "runnable_model_not_found",
    }


def test_recipe_import_accepts_schema_one_safe_plugins_and_reresolves_model():
    import lab_portal

    registry_model = {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp": True,
        "cpp_sync": True,
    }
    recipe = {
        "schema_version": 1,
        "model": {
            "name": "resnet18",
            "category": "classification",
            "language": "cpp",
            "variant": "sync",
        },
        "input": {"kind": "image"},
        "plugins": [{
            "id": "custom_postprocess",
            "stage": "postprocess",
            "language": "python",
            "entrypoint": "plugins/postprocess/clean.py",
            "interface_version": 1,
            "enabled": True,
        }],
    }

    workflow = lab_portal.import_recipe(recipe, models=[registry_model])

    assert workflow["schema_version"] == 1
    assert workflow["model"]["model_file"] == registry_model["model_file"]
    assert workflow["plugins"][0]["entrypoint"] == "plugins/postprocess/clean.py"


def test_recipe_import_resolves_a_real_video_asset_for_video_input():
    import lab_portal

    registry_model = {
        "name": "resnet18",
        "category": "classification",
        "model_file": "assets/models/resnet18_224x224.dxnn",
        "model_exists": True,
        "cpp_sync": True,
    }
    workflow = lab_portal.import_recipe(
        {
            "schema_version": 1,
            "model": {"name": "resnet18", "category": "classification"},
            "input": {"kind": "video"},
            "plugins": [],
        },
        models=[registry_model],
        images=["sample/img/sample_dog.jpg"],
        videos=["assets/videos/sample.mp4"],
    )

    assert workflow["input"] == {"kind": "video", "path": "assets/videos/sample.mp4"}
    assert workflow["validation"]["status"] == "ready"