"""공개 ModelZoo 페이지의 __MODEL_ZOO_DATA__ 를 읽는다.

페이지가 리팩토링되면서 서버 렌더 HTML 테이블이 사라지고 구조화된 페이로드가
문서 안에 실리게 됐다. 우리 파서는 테이블을 읽고 있었으므로 더 이상 맞지 않는다.

이름으로 읽는다. 페이로드의 `fields` 배열이 열 이름을 주므로 위치에 기대지 않는다 —
이 저장소는 위치 기반 파싱으로 카탈로그 캐시의 필드가 한 칸씩 밀려(`fps` ←
`fps_per_watt`) 잘못된 성능 수치를 보여준 전례가 있다.

그리고 조용히 실패하지 않는다. 공식 API 가 아니라 페이지 구조에 기대고 있으므로,
모양이 바뀌면 부분 카탈로그를 만드는 대신 예외를 던져야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dx_modelzoo.metadata._public_parser import parse_public_payload

FIXTURE = Path(__file__).parent / "fixtures" / "public_modelzoo_payload.html"


@pytest.fixture(scope="module")
def rows():
    return parse_public_payload(FIXTURE.read_text(encoding="utf-8"))


def test_every_row_is_read(rows):
    assert len(rows) == 8


def test_fields_are_read_by_name_not_position(rows):
    """이름으로 읽으면 열 순서가 바뀌어도 값이 밀리지 않는다."""
    by_name = {r["display"]: r for r in rows}
    d = by_name["DenseNet-121"]
    assert d["task"] == "Image Classification"
    assert d["dataset"] == "ImageNet"
    assert d["metric"] == "Top1"
    assert d["params"] == pytest.approx(8.04)
    assert d["ops"] == pytest.approx(3.18)
    assert d["fps"] == pytest.approx(94)
    assert d["fps_per_watt"] == pytest.approx(213.8)
    assert d["license"] == "BSD-3-Clause"


def test_accuracy_is_read_per_tier(rows):
    by_name = {r["display"]: r for r in rows}
    d = by_name["DenseNet-121"]
    assert d["accuracy"]["raw"] == pytest.approx(74.436)
    assert d["accuracy"]["qlite"] == pytest.approx(73.97)
    assert d["accuracy"]["qpro"] == pytest.approx(74.25)
    assert d["accuracy"]["qmaster"] is None        # 이 모델엔 없다

    r = by_name["RepVGG-A0"]                       # 네 tier 가 모두 있는 행
    assert r["accuracy"]["qmaster"] == pytest.approx(71.238)


def test_artifact_urls_are_absolute(rows):
    """상대경로(~onnx/…)는 페이로드의 base 와 합쳐 완전한 URL 이 돼야 한다."""
    d = next(r for r in rows if r["display"] == "DenseNet-121")
    onnx = d["artifacts"]["onnx"]
    assert onnx.startswith("https://sdk.deepx.ai/modelzoo/"), onnx
    assert "~" not in onnx.removeprefix("https://sdk.deepx.ai/modelzoo/")
    assert onnx.endswith("densenet121_224x224.onnx")


def test_absent_artifacts_are_absent_not_empty_strings(rows):
    d = next(r for r in rows if r["display"] == "YOLOv3 Darknet (640x640)")
    assert d["artifacts"].get("qpro_dxnn") is None


def test_missing_global_raises(recwarn):
    """조용한 부분 성공이 가장 위험하다 — 없으면 큰 소리로 실패한다."""
    with pytest.raises(ValueError, match="__MODEL_ZOO_DATA__"):
        parse_public_payload("<html><body>no payload here</body></html>")


def test_unknown_field_layout_raises():
    """`fields` 에서 필수 열이 사라지면 조용히 비우지 않는다."""
    broken = (
        '<script>window.__MODEL_ZOO_DATA__ = '
        '{"fields":["task","name"],"base":"https://x/","rows":[["a","b"]]};</script>'
    )
    with pytest.raises(ValueError, match="fields"):
        parse_public_payload(broken)


def test_nested_braces_do_not_truncate_the_payload():
    """괄호 균형으로 끝을 찾는다. 정규식으로 첫 `}` 를 잡으면 중첩에서 잘린다."""
    payload = (
        '<script>window.__MODEL_ZOO_DATA__ = '
        '{"fields":["task","name","display","dataset","input","ops","params",'
        '"license","metric","source","rawAcc","onnx","qlAcc","qlDxnn","qlJson",'
        '"qpAcc","qpDxnn","qpJson","qmAcc","qmDxnn","qmJson","fps","fpsw"],'
        '"base":"https://x/","note":{"nested":{"deep":1}},'
        '"rows":[["t","n","D","ds","1x1",1,2,"MIT","Top1","http://s",1.0,'
        '"~a.onnx",2.0,null,null,null,null,null,null,null,null,3,4]]};</script>'
    )
    rows = parse_public_payload(payload)
    assert len(rows) == 1 and rows[0]["display"] == "D"


# ── 어댑터가 쓰는 형태 ────────────────────────────────────────
# 어댑터와 studio_id_map 은 {모델id: {점으로 이어진 leaf 경로: 값}} 을 기대한다.
# 그 leaf 경로들은 예전 HTML 파서가 이미 정의해 둔 것과 같아야 한다 — 스키마는
# specification.dataset / parameters / metric.name / evaluation.qmaster 를 이미
# 갖고 있었고, 채우는 쪽이 없었을 뿐이다.
from dx_modelzoo.metadata._public_parser import parse_public_modelzoo_html  # noqa: E402


@pytest.fixture(scope="module")
def models():
    parsed, _warnings = parse_public_modelzoo_html(FIXTURE.read_text(encoding="utf-8"))
    return parsed


def test_adapter_shape_is_keyed_by_model_id(models):
    assert isinstance(models, dict) and len(models) == 8
    assert all(isinstance(v, dict) for v in models.values())
    # id 는 아티팩트 파일명에서 나온다. 숫자 안의 점을 두 번 깎지 않아야 한다.
    assert "densenet121_224x224" in models


def test_leaf_paths_match_the_established_schema(models):
    f = models["densenet121_224x224"]
    assert f["display.class_name"] == "DenseNet-121"
    assert f["specification.dataset"] == "ImageNet"
    assert f["specification.input_resolution"] == "224x224x3"
    assert f["specification.parameters"] == pytest.approx(8.04)
    assert f["specification.operations"] == pytest.approx(3.18)
    assert f["specification.metric.name"] == "Top1"
    assert f["legal.license"] == "BSD-3-Clause"
    assert f["legal.source_url"].startswith("https://pytorch.org/")
    assert f["evaluation.raw.accuracy"] == pytest.approx(74.436)
    assert f["evaluation.qlite.accuracy"] == pytest.approx(73.97)
    assert f["evaluation.qpro.accuracy"] == pytest.approx(74.25)
    assert f["performance.fps"] == pytest.approx(94)
    assert f["performance.fps_per_watt"] == pytest.approx(213.8)
    assert f["artifacts.onnx.remote_url"].startswith("https://sdk.deepx.ai/modelzoo/")


def test_absent_tiers_do_not_appear_as_keys(models):
    """없는 값은 None 으로 채우지 않고 키를 만들지 않는다.

    merge 가 '값이 있는 소스' 를 고르므로, None 을 넣으면 다른 소스가 채운
    값을 빈 값으로 덮어쓸 수 있다.
    """
    f = models["densenet121_224x224"]
    assert "evaluation.qmaster.accuracy" not in f
    assert "artifacts.qmaster_dxnn.remote_url" not in f


def test_dotted_model_names_are_not_double_stripped(models):
    """숫자 안의 점을 확장자로 오인하면 안 된다.

    `3ddfa-v2_mobilenet-0.5_120x120.dxnn` 에서 확장자를 미리 떼고 정규화하면
    `.5_120x120` 까지 함께 날아가 `3ddfa_v2_mobilenet_0` 이 된다. 전체 파일명을
    넘겨 Path.stem 이 한 번만 깎게 한다.
    """
    assert "3ddfa_v2_mobilenet_0_5_120x120" in models, sorted(models)
