"""새 카탈로그 데이터가 화면에 닿는 방식.

정적 계약이다 — 브라우저 없이 소스를 읽어 확인한다. 값이 맞게 계산되는지는
test_metric_polarity.py 가, 파싱은 test_public_payload_parser.py 가 본다.
여기서 지키는 것은 "그 데이터가 실제로 화면 코드에 배선됐는가" 다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_JS = ROOT / "dx_modelzoo" / "static" / "js" / "catalog.js"
DETAIL_JS = ROOT / "dx_modelzoo" / "static" / "js" / "detail.js"


def _catalog():
    return CATALOG_JS.read_text(encoding="utf-8")


def test_table_gains_params_and_fps_per_watt_columns():
    """FPS/W 는 데이터가 341/348 있는데 표시되지 않고 있었다. params 는 신규다."""
    src = _catalog()
    headers = re.search(r"const headers = \[(.*?)\];", src, re.S)
    assert headers, "테이블 헤더 정의를 찾을 수 없다"
    block = headers.group(1)
    for key in ("'params'", "'fps_per_watt'"):
        assert key in block, f"헤더에 {key} 가 없다"


def test_accuracy_is_shown_with_its_metric_name():
    """`3.499`(NME) 와 `98.667`(Top-1) 이 한 칸에 섞여 있었다.

    지표명이 없으면 두 값이 비교 가능해 보이지만 아니다. 값 옆에 지표를 적는다.
    """
    src = _catalog()
    assert "_accuracyWithMetric" in src, "지표명을 붙이는 경로가 없다"


def test_sorting_never_compares_across_metrics():
    """다른 지표끼리는 순서를 만들지 않는다.

    정렬 비교자가 지표를 확인하지 않으면 NME 3.5 가 Top-1 98.6 보다 '작다'는
    무의미한 순서가 나온다.
    """
    src = _catalog()
    assert "_compareAccuracy" in src, "정확도 전용 비교자가 없다"
    body = re.search(r"function _compareAccuracy\((.*?)\n}", src, re.S)
    assert body, "_compareAccuracy 본문을 찾을 수 없다"
    assert "metric" in body.group(1), "비교자가 지표를 보지 않는다"


def test_card_shows_accuracy_next_to_fps():
    src = _catalog()
    card = re.search(r"renderCardItem\(m\)\s*\{(.*?)\n  \},", src, re.S)
    assert card, "renderCard 를 찾을 수 없다"
    assert "_accuracyWithMetric" in card.group(1), "카드에 정확도가 없다"


def test_detail_has_a_tier_comparison():
    """ONNX → Q-Lite → Q-Pro → Q-Master 를 한 줄에 놓아 양자화 비용을 보여준다."""
    src = DETAIL_JS.read_text(encoding="utf-8")
    assert "sectionTiers" in src, "tier 비교 섹션이 없다"
    for tier in ("qlite", "qpro", "qmaster"):
        assert tier in src, f"{tier} 가 상세에 없다"


def test_qmaster_chip_only_when_present():
    """Q-Master 는 354개 중 15개뿐이다.

    항상 칩을 그리면 대부분이 '없음' 이 되어 칩이 정보를 잃는다.
    """
    src = _catalog()
    assert "qmaster" in src, "Q-Master 를 아는 코드가 없다"
