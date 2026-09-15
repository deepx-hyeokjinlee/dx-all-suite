"""지표마다 좋고 나쁨의 방향이 다르다.

공개 카탈로그의 `metric` 은 18종이고 방향이 섞여 있다. Top1 은 클수록 좋고
RMSE 는 작을수록 좋다. 그래서 양자화 델타를 홈페이지처럼 "손실"로 칠하는 것은
**클수록 좋은 지표에만** 맞다 — RMSE 가 내려간 것은 개선이다.

극성을 데이터에서 추론하려는 유혹이 있는데, 해보면 틀린다. 양자화 전후 평균
변화로 판정했더니 표본이 작은 지표(`Accuracy` n=4)에서 부호가 뒤집혔다. 극성은
지표 이름의 도메인 지식이지 통계가 아니다.

모르는 지표는 중립으로 둔다. 모르는 것을 아는 척하는 쪽이 색을 안 칠하는
것보다 나쁘다.
"""
from __future__ import annotations

import pytest

from dx_modelzoo.core.metrics import direction_of, format_delta


@pytest.mark.parametrize("metric", ["Top1", "mAP", "mIoU", "PSNR", "AP(Easy)", "Accuracy"])
def test_higher_is_better_metrics(metric):
    assert direction_of(metric) == "higher"


@pytest.mark.parametrize("metric", ["RMSE", "NME", "MNAE"])
def test_lower_is_better_metrics(metric):
    assert direction_of(metric) == "lower"


def test_unknown_metric_is_neutral_not_guessed():
    assert direction_of("SomeNewScore") is None
    assert direction_of(None) is None


def test_delta_carries_sign_and_verdict_for_known_metrics():
    # Top1: 값이 떨어졌으니 나빠진 것
    assert format_delta("Top1", 74.436, 73.97) == (-0.466, "worse")
    # RMSE: 값이 올라갔으니 나빠진 것
    assert format_delta("RMSE", 0.607, 0.616) == (0.009, "worse")
    # RMSE 가 내려가면 좋아진 것
    assert format_delta("RMSE", 0.616, 0.607) == (-0.009, "better")


def test_delta_for_unknown_metric_has_no_verdict():
    """부호는 보여주되 좋다/나쁘다로 칠하지 않는다."""
    delta, verdict = format_delta("SomeNewScore", 10.0, 9.0)
    assert delta == -1.0
    assert verdict is None


def test_delta_is_none_when_a_side_is_missing():
    assert format_delta("Top1", 74.4, None) == (None, None)
    assert format_delta("Top1", None, 73.9) == (None, None)
