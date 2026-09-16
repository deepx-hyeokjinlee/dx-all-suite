"""studio id 와 생성 카탈로그 id 사이의 접미사 매칭 규칙.

생성 카탈로그는 공개 ModelZoo 에서 만들어지고, 그 id 는 studio 가 쓰는 id 와
철자가 다르다. studio id 는 dx_app 예제 디렉토리명(`yolo26_depth_n`)에서 오고,
공개 쪽은 해상도를 달고 있다(`yolo26_depth_n_768x768`).

`_GEN_ID_SUFFIXES` 화이트리스트는 quant/instance 접미사만 접는다. 해상도를 뺀 것은
실수가 아니라 의도다 — `foo` 와 `foo_1280` 은 서로 다른 모델일 수 있으므로 무턱대고
접으면 엉뚱한 모델의 메타데이터가 붙는다.

그래서 규칙은 "해상도 접미사는 후보가 유일할 때만 접는다" 이다. 모호하면 비워 두는
기존 태도를 그대로 지킨다.
"""
from __future__ import annotations


def _match(model_id, gen_map):
    """`core` 는 dx_app 도 쓰는 최상위 이름이라 모듈 레벨 import 가 전체 수집에서
    서로를 덮는다 (tests/server_helpers.py 의 _clear_top_level_core_imports 참조).
    test_legal_enrich.py 와 같은 방식으로 테스트 안에서 늦게 가져온다."""
    from core.catalog import _match_generated

    return _match_generated(model_id, gen_map)


def _g(*ids):
    return {i: {"id": i} for i in ids}


def test_exact_id_wins():
    gm = _g("alexnet", "alexnet_q_pro")
    assert _match("alexnet", gm)["id"] == "alexnet"


def test_known_quant_suffix_still_matches():
    gm = _g("alexnet_q_lite")
    assert _match("alexnet", gm)["id"] == "alexnet_q_lite"


def test_unique_resolution_suffix_matches():
    """yolo26_depth_n -> yolo26_depth_n_768x768 — 이게 안 되어 legal 이 비어 있었다."""
    gm = _g("yolo26_depth_n_768x768", "unrelated_model")
    got = _match("yolo26_depth_n", gm)
    assert got is not None, "유일한 해상도 변종을 찾지 못했다"
    assert got["id"] == "yolo26_depth_n_768x768"


def test_ambiguous_resolution_suffixes_do_not_match():
    """후보가 둘이면 접지 않는다 — 엉뚱한 해상도의 메타데이터가 붙는 것을 막는다."""
    gm = _g("foo_768x768", "foo_1280x1280")
    assert _match("foo", gm) is None


def test_non_resolution_suffix_is_not_collapsed():
    """해상도처럼 보이지 않는 접미사는 여전히 접지 않는다."""
    gm = _g("foo_large", "foo_v2")
    assert _match("foo", gm) is None


def test_no_candidate_returns_none():
    assert _match("missing", _g("other_224x224")) is None


def test_resolution_rule_does_not_shadow_exact_match():
    """정확매칭이 있으면 해상도 후보가 있어도 정확매칭이 이긴다."""
    gm = _g("foo", "foo_768x768")
    assert _match("foo", gm)["id"] == "foo"
