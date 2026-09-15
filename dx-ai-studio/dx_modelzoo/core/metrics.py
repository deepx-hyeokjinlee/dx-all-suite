"""지표의 방향과 양자화 델타.

정확도 숫자만 보여주면 비교할 수 없다. 공개 카탈로그의 `metric` 은 18종이고
방향이 섞여 있어서 — Top1 은 클수록, RMSE 는 작을수록 좋다 — 델타에 색을
칠하려면 어느 쪽인지 알아야 한다.

방향은 데이터에서 추론하지 않는다. 양자화 전후 평균 변화로 판정해 봤더니
표본이 작은 지표(`Accuracy`, n=4)에서 부호가 뒤집혔다. 통계가 아니라 지표
이름의 도메인 지식이므로 명시 표로 둔다.

표에 없는 지표는 **중립**이다. 부호는 보여주되 좋다/나쁘다로 칠하지 않는다.
모르는 것을 아는 척하는 쪽이 색을 안 칠하는 것보다 나쁘다. (공개 카탈로그에
새 지표가 추가될 수 있으므로 이 경로는 실제로 쓰인다.)
"""
from __future__ import annotations

# 실측: 354개 모델에 18종. 아래 두 집합이 그중 350건 이상을 덮는다.
HIGHER_IS_BETTER = frozenset({
    "Top1", "Top5", "Accuracy", "Average Accuracy",
    "mAP", "mAP50", "mAP_BEV@0.5", "det_mAP50",
    "AP", "AP(Easy)", "AP(Medium)", "AP(Hard)", "AP@0.5", "AR10",
    "mIoU", "PSNR", "Recall@1", "HEA",
})
LOWER_IS_BETTER = frozenset({"RMSE", "NME", "MNAE", "ADD"})


def direction_of(metric):
    """'higher' | 'lower' | None(모름)."""
    if not metric:
        return None
    name = str(metric).strip()
    if name in HIGHER_IS_BETTER:
        return "higher"
    if name in LOWER_IS_BETTER:
        return "lower"
    return None


def format_delta(metric, baseline, value):
    """(델타, 판정) — 판정은 'better' | 'worse' | None(모름).

    델타는 저장하지 않고 그릴 때마다 계산한다. baseline 기준의 파생값이라
    저장하면 둘이 어긋날 수 있다.
    """
    if baseline is None or value is None:
        return (None, None)
    delta = round(float(value) - float(baseline), 6)
    direction = direction_of(metric)
    if direction is None or delta == 0:
        return (delta, None)
    improved = delta > 0 if direction == "higher" else delta < 0
    return (delta, "better" if improved else "worse")
