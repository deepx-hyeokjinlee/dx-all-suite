"""task key 의 두 이름 — dx_app per-model layout 의 key 와 main (legacy) 의 key (spec 2026-10-01 결정 3).

teammate branch (``8d0b748``) 는 task 폴더 이름을 dx-modelzoo 에 맞췄다 (22 → 28). 같은 task 를 다른 이름으로
부른 것이 7 개, 새 task 가 7 개. studio 의 task 표 (label · icon · 기본 입력 · image-only · 결과 안내) 는 key 로
찾으니, 한쪽 이름으로 적힌 값을 다른 쪽 이름으로도 찾게 여기서 묶는다. 표의 원본은 그대로
``dx_modelzoo/core/config.py`` 의 CATEGORIES.

``ppu`` 는 task 가 아니라 model 묶음이었다 — per-model layout 에서는 ``object_detection/yolo_ppu`` 등으로
흩어졌으므로 새 key 가 없다.

계약: tests/shared/test_tasks.py
"""
from __future__ import annotations

LEGACY_TO_TASK = {
    "classification": "image_classification",
    "obb_detection": "oriented_object_detection",
    "face_alignment": "face_landmark",
    "embedding": "face_recognition",
    "attribute_recognition": "person_attribute",
    "image_enhancement": "low_light_enhancement",
    "reid": "person_reid",
}
TASK_TO_LEGACY = {v: k for k, v in LEGACY_TO_TASK.items()}

NEW_TASKS = (
    "anomaly_detection",
    "zero_shot_image_classification",
    "zero_shot_instance_segmentation",
    "image_matting",
    "image_retrieval",
    "visual_place_recognition",
    "face_attribute",
)


def canonical(key: str) -> str:
    """legacy key → per-model key (이미 새 key 거나 모르는 key 는 그대로)."""
    return LEGACY_TO_TASK.get(key, key)


def legacy(key: str) -> str:
    """per-model key → legacy key (짝이 없으면 그대로)."""
    return TASK_TO_LEGACY.get(key, key)


def lookup(table: dict, key: str, default=None):
    """key 로, 없으면 짝 이름으로 table 을 찾는다."""
    if key in table:
        return table[key]
    for alt in (LEGACY_TO_TASK.get(key), TASK_TO_LEGACY.get(key)):
        if alt and alt in table:
            return table[alt]
    return default


class TaskTable(dict):
    """task key → 값 표. 한쪽 이름으로 적어 두면 짝 이름으로도 찾는다 (``get`` · ``[]`` · ``in``).

    기존 표 (SAMPLE_IMAGES · EXAMPLE_TYPES · CAT_IMAGE …) 를 이것으로 감싸면 호출부를 고치지 않고도 새 key 가 옛
    값을 찾는다. 같은 task 의 값이 두 이름에 다르게 적히는 일이 없게 한 곳에만 적는다."""

    def _alt(self, key):
        for alt in (LEGACY_TO_TASK.get(key), TASK_TO_LEGACY.get(key)):
            if alt is not None and dict.__contains__(self, alt):
                return alt
        return None

    def __missing__(self, key):
        alt = self._alt(key)
        if alt is None:
            raise KeyError(key)
        return dict.__getitem__(self, alt)

    def get(self, key, default=None):
        if dict.__contains__(self, key):
            return dict.__getitem__(self, key)
        alt = self._alt(key)
        return dict.__getitem__(self, alt) if alt is not None else default

    def __contains__(self, key):
        return dict.__contains__(self, key) or self._alt(key) is not None


class TaskSet(frozenset):
    """task key 집합 — 짝 이름도 속한 것으로 본다 (IMAGE_ONLY_CATEGORIES 등)."""

    def __contains__(self, key):
        return (frozenset.__contains__(self, key) or frozenset.__contains__(self, LEGACY_TO_TASK.get(key, key))
                or frozenset.__contains__(self, TASK_TO_LEGACY.get(key, key)))
