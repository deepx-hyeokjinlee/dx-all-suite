"""무대의 hero (spec 2026-09-23 §5.2, §8.1) — 문구와 실제 프롬프트의 계약."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "launcher" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
SHOWCASE = ROOT.parent / "dx-agent-dev-showcase"

TITLE = "Describe anything. Run it on DX-M1."
SUBTITLE = ("Say what you need. The agent picks the model, compiles it, "
            "builds the app and measures it on this NPU.")
# (showcase, chip 라벨, placeholder 로 쓰는 첫 문장). 처음 4개가 보이는 chip.
CHIPS = [
    ("mini-game-squat-fitness", "Squat game",
     "Build a squat-counting fitness mini-game using yolo26n-pose on DEEPX NPU"),
    ("paddleocr-video-ocr", "Video OCR",
     "Build an OCR inference app whose text detection + recognition runs on the DEEPX DX-M1 NPU."),
    ("ultralytics-retrain-eval-deepx-export-braintumor", "Brain MRI",
     "Using the Ultralytics Python package, adapt the base yolo26n model for a medical edge device "
     "that screens MRI/CT brain scans for tumors."),
    ("ultralytics-yolo-deepx-export", "YOLO → DeepX",
     "Export the Ultralytics YOLO26n detection model to DeepX NPU format using the one-shot "
     "format=deepx export path, then run inference on the Ultralytics bus sample image."),
    ("mini-game-stretching-coach", "Stretching coach",
     "Using the yolo26n-pose model on the DEEPX NPU, build a simple arcade-style stretching mini-game."),
    ("rapiddoc-pdf2md", "PDF → Markdown",
     "Build a PDF-to-Markdown app whose document-parsing pipeline (layout analysis + OCR + "
     "table/formula recognition) runs on the DEEPX DX-M1 NPU."),
    ("ultralytics-retrain-eval-deepx-export-pills", "Pill counter",
     "Using the Ultralytics Python package, adapt the base yolo26n model for a pharmaceutical pill "
     "identification/counting station."),
    ("ultralytics-retrain-eval-deepx-export-ppe", "Site-safety PPE",
     "Using the Ultralytics Python package, adapt the base yolo26n model for a construction/factory "
     "site-safety camera that checks PPE (personal protective equipment) compliance."),
    ("ultralytics-retrain-eval-deepx-export-wildlife", "Safari camera",
     "Using the Ultralytics Python package, adapt the base yolo26n model for a wildlife-monitoring / "
     "safari camera scenario."),
]
LANGS = ("ko", "ja", "es", "'zh-CN'", "'zh-TW'")


def _prompts() -> dict:
    src = (STATIC / "home-prompts.js").read_text(encoding="utf-8")
    return json.loads(src[src.index("{"):src.rindex("}") + 1])


def _readme_prompt(name: str) -> str:
    text = (SHOWCASE / name / "README.md").read_text(encoding="utf-8")
    section = text[text.index("## The prompt"):]
    return re.search(r"```[^\n]*\n(.*?)\n```", section, re.S).group(1)


def _dict_entry(key: str) -> str:
    m = re.search(r"'" + re.escape(key.replace("'", "\\'")) + r"':\s*\{([^}]*)\}", HTML)
    assert m, f"사전에 {key!r} 가 없다"
    return m.group(1)


def test_title_and_subtitle_are_the_new_copy():
    stage = HTML[HTML.index('id="homeStage"'):HTML.index('id="homeAskForm"')]
    assert f'data-i18n="{TITLE}"' in stage
    assert f'data-i18n="{SUBTITLE}"' in stage


@pytest.mark.parametrize("key", [TITLE, SUBTITLE] + [c[1] for c in CHIPS] + [c[2] for c in CHIPS])
def test_every_new_line_speaks_six_languages(key):
    entry = _dict_entry(key)
    for lang in LANGS:
        assert re.search(r"(?:^|[\s,{])" + re.escape(lang) + r"\s*:", entry), (key, lang)


@pytest.mark.skipif(not SHOWCASE.is_dir(), reason="dx-agent-dev-showcase 가 없다 (suite 밖)")
@pytest.mark.parametrize("name", [c[0] for c in CHIPS])
def test_each_prompt_is_the_showcase_prompt_verbatim(name):
    """검증된 것은 그 showcase 를 실제로 만든 문장이다 — 다듬으면 검증이 사라진다."""
    assert _prompts()[name] == _readme_prompt(name)


@pytest.mark.parametrize("name,label,first", CHIPS)
def test_the_placeholder_sentence_opens_that_prompt(name, label, first):
    """placeholder 는 원문의 첫 문장이다 — 지어낸 예시가 아니다.

    README 는 원문을 코드 블록 안에서 줄바꿈해 적기도 한다 (rapiddoc-pdf2md) — 원문은
    그대로 두고, 비교할 때만 공백을 하나로 편다."""
    flat = " ".join(_prompts()[name].split())
    assert flat.startswith(first.rstrip(".")), name


def test_nine_chips_in_order_and_four_showing():
    chips = re.findall(r'<button type="button" class="ask-chip"([^>]*)>', HTML)
    names = [re.search(r'data-prompt="([^"]+)"', c).group(1) for c in chips]
    assert names == [c[0] for c in CHIPS]
    hidden = ["hidden" in c for c in chips]
    assert hidden == [False] * 4 + [True] * 5
    assert 'id="homeAskMore"' in HTML


def test_the_placeholder_is_the_first_prompt():
    box = re.search(r'<textarea[^>]*id="homeAsk"[^>]*>', HTML, re.S).group(0)
    assert f'data-i18n-placeholder="{CHIPS[0][2]}"' in box


def test_the_film_pills_carry_thumbnails():
    for pid in ("landingPoster", "ecosystemPoster"):
        pill = re.search(r'<a [^>]*id="' + pid + r'"[^>]*>(.*?)</a>', HTML, re.S).group(1)
        img = re.search(r'<img [^>]*>', pill)
        assert img, f"#{pid} 에 썸네일이 없다"
        assert 'alt=""' in img.group(0), "제목이 옆에 있으니 썸네일은 장식이다"


def test_the_prompts_file_is_served_and_loaded():
    launcher = (ROOT / "launcher" / "launcher.py").read_text(encoding="utf-8")
    assert 'path == "/home-prompts.js"' in launcher
    assert HTML.index('src="/home-prompts.js"') < HTML.index('src="/home-answer.js"')


def test_a_chip_fills_the_prompt_instead_of_running_it():
    """긴 원문을 읽거나 고칠 틈 없이 답이 뜨고 무대가 Dock 으로 바뀌던 것을 막는다."""
    src = (STATIC / "home-answer.js").read_text(encoding="utf-8")
    handler = src[src.index("var chips = $('homeAskChips');"):]
    handler = handler[:handler.index("var routes")]
    assert "DXHomePrompts" in handler
    assert "ask(" not in handler, "chip 이 곧바로 실행한다"


# 모듈이 바로 받는 짧은 요청 — intro 의 "작업 장면" 이 타이핑하는 바로 그 세 문장이다
# (launcher-splash.js _WORK). chip 이 showcase 원문으로 바뀌면서 home 에서 사라졌는데,
# 입력창은 모듈로 바로 보내는 일 (home-router) 도 하므로 그 쪽 예시를 placeholder 순환에
# 남긴다 (2026-09-28 사용자 결정 A).
ROUTED = ["4-channel CCTV object detection", "segment a video file", "compile yolo26n to DXNN"]


def _placeholders() -> list:
    src = (STATIC / "home-prompts.js").read_text(encoding="utf-8")
    body = src[src.index("window.DXHomePlaceholders"):]
    return json.loads(body[body.index("["):body.index("];") + 1])


def test_the_placeholder_cycle_offers_both_kinds_of_request():
    cycle = _placeholders()
    for _, _, first in CHIPS:
        assert first in cycle, first
    for routed in ROUTED:
        assert routed in cycle, routed
    assert len(cycle) == len(set(cycle)) == len(CHIPS) + len(ROUTED)


@pytest.mark.parametrize("key", ROUTED)
def test_routed_examples_still_speak_six_languages(key):
    entry = _dict_entry(key)
    for lang in LANGS:
        assert re.search(r"(?:^|[\s,{])" + re.escape(lang) + r"\s*:", entry), (key, lang)
