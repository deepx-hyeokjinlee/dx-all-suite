"""run 요청의 category 는 legacy · per-model 어느 이름이든 받는다 (2026-10-01).

dx_app 을 teammate per-model layout 으로 바꾸면 CATEGORIES 에는 oriented_object_detection 만 있고
obb_detection 은 없다. 예전에 저장된 recent run · 링크 · 외부 client 가 obb_detection 으로 보내면
"Unknown category" 400 이었다. 짝 이름이 있으면 그 이름으로 바꿔 받는다 (main checkout 에서는 반대로).
"""
from unittest.mock import patch


def _server():
    import server   # conftest 가 dx_app 을 sys.path 에 둔 뒤에 (test_security_paths 와 같은 방식)
    return server


def test_a_legacy_category_is_taken_as_its_per_model_pair():
    server = _server()
    with patch.object(server, "CATEGORIES", ["object_detection", "oriented_object_detection"]):
        assert server._require_category("obb_detection") == "oriented_object_detection"
        assert server._require_category("oriented_object_detection") == "oriented_object_detection"


def test_a_per_model_category_is_taken_as_its_legacy_pair_on_main():
    server = _server()
    with patch.object(server, "CATEGORIES", ["object_detection", "obb_detection"]):
        assert server._require_category("oriented_object_detection") == "obb_detection"


def test_unknown_and_traversal_are_still_refused():
    server = _server()
    with patch.object(server, "CATEGORIES", ["object_detection"]):
        for bad in ("nope", "../x", "obb_detection"):
            try:
                server._require_category(bad)
            except ValueError:
                continue
            raise AssertionError(f"{bad!r} accepted")


def test_the_payload_carries_the_resolved_name():
    server = _server()
    data = {"category": "obb_detection", "model_name": "yolo26-n-obb_1024x1024",
            "model_file": "assets/models/yolo26-n-obb_1024x1024.dxnn"}
    with patch.object(server, "CATEGORIES", ["oriented_object_detection"]), \
         patch.object(server, "_require_model_file", lambda _f: None):
        err, _code = server._validate_inference_payload(data)
    assert err is None, err
    assert data["category"] == "oriented_object_detection"
