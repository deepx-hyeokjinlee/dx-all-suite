"""test_models.conf 가 쓰는 카테고리는 전부 CATEGORIES 에 있어야 한다.

이 불변식만 지금 지켜지지 않고 있다. 변이로 확인한 현재 상태(2026-09-21):

    conf 에 모델 추가, 메타데이터 없음       → 3개 테스트가 모델 id 를 찍고 실패 (시끄러움)
    CATEGORIES 에서 카테고리 제거           → test_config.py 실패 (시끄러움)
    conf 에 새 카테고리, CATEGORIES 엔 미추가 → **아무것도 울지 않음**

마지막 경우가 조용한 이유는 `CATEGORIES` 쪽 계약이 **고정 집합** 을 보기 때문이다.
`CATEGORIES` 를 건드리지 않으면 그 테스트들은 통과하고, conf 쪽에서 새 이름이
들어온 것은 아무도 보지 않는다. 그 모델은 UI 의 `__unknown__` 버킷으로 빠지고,
카테고리 필터에서 이름조차 갖지 못한다.

왜 지금 필요한가: 릴리즈에 모델 142개가 추가되고 그중 `Visual Place Recognition`
은 `CATEGORIES` 에 없는 태스크다. conf 에 넣고 CATEGORIES 를 잊으면 조용히 샌다.

세 dict 를 함께 보는 이유: 하나만 채우면 반쪽이다. `CATEGORIES` 는 라벨(6개 언어)
+ 아이콘, `EXAMPLE_TYPES` 는 결과를 어떻게 그릴지, `SAMPLE_IMAGES` 는 어떤 입력으로
돌릴지를 정한다. 셋 중 하나라도 빠지면 그 태스크는 화면 어딘가에서 깨진다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _config():
    sys.path.insert(0, str(ROOT / "dx_modelzoo"))
    from core import config

    return config


def _conf_categories() -> set[str]:
    sys.path.insert(0, str(ROOT))
    from dx_modelzoo.core.catalog import parse_test_models_conf

    return {m["category"] for m in parse_test_models_conf() if m.get("category")}


@pytest.mark.parametrize("table", ["CATEGORIES", "EXAMPLE_TYPES", "SAMPLE_IMAGES"])
def test_every_category_in_the_conf_is_declared(table):
    declared = getattr(_config(), table)
    used = _conf_categories()
    # EXAMPLE_TYPES · SAMPLE_IMAGES 는 TaskTable — per-model conf 의 새 이름 (face_landmark …) 은 옛 이름의 짝으로 찾는다
    missing = sorted(c for c in used if c not in declared)
    assert not missing, (
        f"test_models.conf 가 쓰는 카테고리가 {table} 에 없다: {missing}\n"
        f"  → dx_modelzoo/core/config.py 의 {table} 에 추가해야 한다.\n"
        f"  → 넣지 않으면 그 모델은 UI 의 __unknown__ 으로 빠지고 아무 오류도 나지 않는다."
    )


def test_the_three_tables_agree_with_each_other():
    """셋 중 하나만 채우고 나머지를 잊는 것이 가장 흔한 실수다."""
    cfg = _config()
    # 두 표는 TaskTable 이라 per-model layout 의 새 이름 (image_classification …) 이 옛 이름 (classification) 의
    # 값을 찾는다 (shared/tasks.py) — 같은 task 를 두 번 적지 않는다. 그래서 key 가 아니라 "찾아지는가" 로 본다.
    cats = set(cfg.CATEGORIES)
    no_example = sorted(c for c in cats if c not in cfg.EXAMPLE_TYPES)
    no_sample = sorted(c for c in cats if c not in cfg.SAMPLE_IMAGES)
    assert not no_example, f"EXAMPLE_TYPES 가 모르는 task: {no_example}"
    assert not no_sample, f"SAMPLE_IMAGES 가 모르는 task: {no_sample}"
    for name, table in (("EXAMPLE_TYPES", cfg.EXAMPLE_TYPES), ("SAMPLE_IMAGES", cfg.SAMPLE_IMAGES)):
        extra = sorted(set(table) - cats)
        assert not extra, f"CATEGORIES 에 없는 {name} key: {extra}"


def test_each_sample_image_actually_exists():
    """SAMPLE_IMAGES 는 경로를 담는다. 없는 곳을 가리키면 소비처가 **조용히** 다른
    그림으로 떨어진다 — server.py 의 기본 이미지 선택은 파일명이 목록에 없으면
    `images[0]` 을 쓴다. 오류가 아니라 엉뚱한 그림이 뜬다.

    실제로 dx_app v3.2.0/v3.2.1 이 샘플을 교체한 뒤 이 표가 한 달 넘게 없는 파일을
    가리켰고, 아무도 몰랐다. 이 계약이 그것을 잡는다.

    `is_file()` 이 아니라 `exists()` 로 본다: embedding 과 reid 는 이미지 **쌍**을
    쓰므로 경로가 디렉터리다 (`sample/img/face_pair/` 안에 3장).
    """
    cfg = _config()
    from dx_modelzoo.core.config import DX_APP_ROOT

    from shared import dx_app_layout as layout
    from shared.tasks import NEW_TASKS
    legacy_root = layout.detect(DX_APP_ROOT) == layout.LEGACY

    missing = []
    for category, rel in cfg.SAMPLE_IMAGES.items():
        if not rel:
            continue
        # 새 task 의 sample (sample/vpr/ …) 은 per-model layout 의 dx_app 에만 있다
        if legacy_root and category in NEW_TASKS:
            continue
        if not (Path(DX_APP_ROOT) / rel).exists():
            missing.append(f"{category} -> {rel}")
    assert not missing, "SAMPLE_IMAGES 가 없는 경로를 가리킨다:\n  " + "\n  ".join(missing)


def test_sample_images_agree_with_the_runtime_source_of_truth():
    """`test_models.conf` 헤더가 말한다: "Source of truth: scripts/run_examples.sh".

    studio 의 SAMPLE_IMAGES 는 그 표의 사본이고, 사본은 말없이 어긋난다. 실제로
    dx_app 이 교체한 두 건을 studio 가 따라가지 못했다 — 경로 문자열은 이 저장소에
    있고 파일은 dx_app 저장소에 있어서, 어느 쪽 CI 도 둘을 같이 보지 않는다.
    이 계약이 그 틈을 메운다.
    """
    import re

    from dx_modelzoo.core.config import DX_APP_ROOT

    script = Path(DX_APP_ROOT) / "scripts" / "run_examples.sh"
    if not script.is_file():
        pytest.skip(f"run_examples.sh 없음: {script}")
    block = re.search(r"CATEGORY_IMAGE=\((.*?)\)", script.read_text(encoding="utf-8"), re.S)
    assert block, "run_examples.sh 에서 CATEGORY_IMAGE 표를 찾지 못했다"
    truth = dict(re.findall(r"\[([a-z_0-9]+)\]=\"([^\"]+)\"", block.group(1)))
    assert truth, "CATEGORY_IMAGE 표가 비어 보인다 — 파싱이 틀렸을 수 있다"

    cfg = _config()
    # per-model dx_app 의 표에는 옛 이름 ([reid] = 쌍 폴더) 과 새 이름 ([person_reid] = query 한 장) 이 같이 있다.
    # studio 는 짝을 한 칸으로 보므로, 둘 다 있으면 이 checkout 의 이름 쪽만 본다.
    from shared import dx_app_layout as layout
    from shared.tasks import canonical, legacy
    per_model = layout.detect(DX_APP_ROOT) == layout.PER_MODEL
    drift = []
    for category, path in truth.items():
        current = canonical(category) if per_model else legacy(category)
        if current != category and current in truth:
            continue
        mine = cfg.SAMPLE_IMAGES.get(category)
        if mine is None:
            continue  # 선언 누락은 위의 다른 계약이 잡는다
        if mine.rstrip("/") != path.rstrip("/"):
            drift.append(f"{category}: studio={mine!r} != run_examples.sh={path!r}")
    assert not drift, "SAMPLE_IMAGES 가 진짜 출처와 어긋난다:\n  " + "\n  ".join(drift)
