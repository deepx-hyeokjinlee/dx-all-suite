"""무대 양옆의 위젯 두 개 (spec 2026-09-23 §5.5–5.6) — 데이터 경로와 선택의 계약."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "launcher" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
FRAME = (STATIC / "launcher-app-frame.js").read_text(encoding="utf-8")


def _widgets() -> str:
    path = STATIC / "home-widgets.js"
    assert path.is_file(), "launcher/static/home-widgets.js 가 없다"
    return path.read_text(encoding="utf-8")


def test_the_widget_script_is_served_and_loaded_after_the_sections():
    launcher = (ROOT / "launcher" / "launcher.py").read_text(encoding="utf-8")
    assert 'path == "/home-widgets.js"' in launcher
    assert HTML.index('src="/home-sections.js"') < HTML.index('src="/home-widgets.js"')


def test_the_device_widget_rides_the_shared_stream_not_a_new_poll():
    """장치 값은 이미 startSharedHwStream 이 SSE (없으면 3초 poll) 로 뿌린다. 위젯이 자기
    주기 poll 을 가지면 같은 장치를 두 번 묻는다."""
    js = _widgets()
    assert "dx-hw-data" in js
    assert not re.search(r"setInterval\([^)]*\n?[^)]*hw_status", js), "위젯이 hw_status 를 주기로 묻는다"


def test_one_owner_paints_the_device():
    """15초 poll 과 스트림이 같은 칩을 번갈아 덮어쓰지 않게, 옛 painter 는 없어진다."""
    assert "function refreshHeroDevice" not in FRAME
    assert "_paintDeviceFacts" not in FRAME
    assert "refreshHeroDevice" not in FRAME


def test_the_headline_is_the_nano_model_of_each_task_named_by_id():
    """가장 빠른 모델을 뽑으면 task 가 달라 비교할 수 없는 숫자가 된다 (spec §5.6).
    이름 패턴으로 추측하지 않고 id 로 적는다 — 무엇이 뽑히는지 읽으면 보인다."""
    js = _widgets()
    pairs = re.findall(r"\['(\w+)',\s*'(\w+)'\]", js[js.index("HEADLINE"):js.index("];", js.index("HEADLINE"))])
    assert pairs == [
        ("object_detection", "yolo26n"),
        ("instance_segmentation", "yolo26n_seg"),
        ("pose_estimation", "yolo26n_pose"),
        ("classification", "yolo26n_cls"),
        ("obb_detection", "yolo26n_obb"),
        ("depth_estimation", "yolo26_depth_n"),
    ]


def test_the_sections_hand_the_catalogue_over_instead_of_a_second_fetch():
    sections = (STATIC / "home-sections.js").read_text(encoding="utf-8")
    assert "dx-home-catalog" in sections
    assert "/zoo/api/catalog" not in _widgets(), "위젯이 카탈로그를 다시 받는다"


def test_the_widgets_open_their_modules_without_inline_handlers():
    """카드와 같은 규칙: 위임된 리스너로 연다 (test_home_cards_use_delegated_routing_not_inline_onclick)."""
    device = HTML[HTML.index('id="homeDevice"'):HTML.index('id="studioGrid"')]
    assert "onclick" not in device
    js = _widgets()
    assert "'dx_monitor'" in js and "'benchmark'" in js


_KEYS = ["No DX-M1 connected", "Object Detection", "Instance Segmentation", "Pose Estimation",
         "Classification", "OBB Detection", "Depth Estimation"]


@pytest.mark.parametrize("key", _KEYS)
def test_new_words_speak_all_six_languages(key):
    m = re.search(r"'" + re.escape(key) + r"':\s*\{([^}]*)\}", HTML)
    assert m, f"사전에 {key!r} 가 없다"
    for lang in ("ko", "ja", "es", "'zh-CN'", "'zh-TW'"):
        assert re.search(r"(?:^|[\s,{])" + re.escape(lang) + r"\s*:", m.group(1)), (key, lang)


def test_task_words_are_the_ones_the_model_zoo_already_uses():
    """용어가 모듈마다 갈라지지 않게 — Model Zoo 사전의 번역을 그대로 쓴다."""
    zoo = (ROOT / "dx_modelzoo" / "static" / "js" / "i18n-dict-shared.js").read_text(encoding="utf-8")
    for key in _KEYS[1:]:
        ours = re.search(r"'" + re.escape(key) + r"':\s*\{([^}]*)\}", HTML).group(1)
        theirs = re.search(r"['\"]" + re.escape(key) + r"['\"]\s*:\s*\{([^}]*)\}", zoo).group(1)
        ko_ours = re.search(r"ko:\s*'([^']*)'", ours).group(1)
        ko_theirs = re.search(r"ko['\"]?\s*:\s*['\"]([^'\"]*)['\"]", theirs).group(1)
        assert ko_ours == ko_theirs, (key, ko_ours, ko_theirs)
