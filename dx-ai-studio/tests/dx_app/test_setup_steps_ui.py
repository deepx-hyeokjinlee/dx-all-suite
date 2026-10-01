"""dx_app Setup 이 공용 단계 목록 (DXSteps) 을 쓰는지 (spec 2026-09-29 아이콘 체계 단계 2a).

예전 화면: ①–⑥ 과 이모지가 붙은 카드 여섯 장이 2열로 — 순서가 지그재그로 읽혔고, 끝난 단계에도 파란
Install 이 그대로라 무엇을 누를지 보이지 않았다. 이제 세로 목록 하나: 끝난 단계는 한 줄, 다음 단계만
펼친다. 흐름 (sudo · 로그 · Run All · 데모 · 숨은 inference-venv) 은 그대로다.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "dx_app" / "templates" / "index.html").read_text(encoding="utf-8")
SETUP_JS = (ROOT / "dx_app" / "static" / "js" / "setup.js").read_text(encoding="utf-8")
TUTORIAL = (ROOT / "dx_app" / "static" / "js" / "tutorial.js").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")

STEPS = ["dx-app-deps", "dx-rt-deps", "dx-rt-build", "dx-driver", "dx-app-build", "dx-app-setup"]


def _page() -> str:
    start = HTML.index('<div id="page-setup"')
    return HTML[start:HTML.index("<!-- ═══ PAGE:", start + 10)]


def test_the_page_is_one_step_list():
    page = _page()
    assert page.count('class="dx-steps"') == 1 and "data-steps" in page
    assert re.findall(r'<li class="dx-step" data-step="([^"]+)"', page) == STEPS
    assert "setup-grid" not in page, "옛 2열 카드 격자가 남아 있다"


def test_every_step_keeps_its_ids_and_handler():
    """튜토리얼 대상은 템플릿의 onclick 문자열과 id 로만 풀린다 (tests/dx_app/test_tutorial.py)."""
    page = _page()
    for step in STEPS:
        li = page[page.index(f'data-step="{step}"'):]
        li = li[:li.index("</li>")]
        assert f'id="setup-badge-{step}"' in li and 'class="dx-step-state"' in li, step
        assert f'id="setup-detail-{step}"' in li, step
        assert f"onclick=\"setupRun('{step}')\"" in li, step
    for kept in ('id="setup-run-all"', 'id="setup-quickstart-btn"', 'id="setup-stop-btn"', 'id="setup-log"',
                 'id="diag-run-btn"', 'id="setup-version-card"', 'id="setup-try-demo"'):
        assert kept in page, kept


def test_the_header_counts_and_runs_the_rest():
    page = _page()
    assert "data-steps-count" in page and 'class="dx-steps-bar"' in page
    run = re.search(r'<button[^>]*id="setup-run-all"[^>]*>', page).group(0)
    assert "data-steps-run" in run


def test_no_emoji_left_in_setup():
    assert gate.count(_page()) == 0, sorted({c for c in _page() if gate.count(c)})
    assert gate.count(SETUP_JS) == 0, sorted({c for c in SETUP_JS if gate.count(c)})


def test_setup_js_reports_state_instead_of_painting_badges():
    assert "DXSteps.set(" in SETUP_JS
    assert "comp-status-badge cs-ok" not in SETUP_JS and "comp-status-badge cs-warn" not in SETUP_JS


def test_the_flows_are_untouched():
    """sudo 재질문 · append-only 로그 · 방금 끝낸 단계 기억 · 숨은 inference-venv · demo_only."""
    for needle in ("SETUP_SUDO_STEPS", "setupPromptSudoPassword", "compRenderLogAppend(logEl,r.log,SETUP);",
                   "setupCheckAll().then(function(){setupMarkStepDone(completedStep);});",
                   "'inference-venv'", "demo_only"):
        assert needle in SETUP_JS, needle


def test_the_setup_tutorial_opens_collapsed_steps_before_pointing_at_them():
    """끝난 단계는 접혀 0 크기라, 그 안의 버튼을 가리키면 journey 가 TARGET_HIDDEN 으로 떨어진다."""
    sec = TUTORIAL[re.search(r"id:\s*'setup'", TUTORIAL).start():]
    sec = sec[:sec.index("\n    },", 10)]
    for step in STEPS:
        m = re.search(r"target:\s*'button\[onclick\*=\"" + re.escape(step) + r"\"\]'(.{0,400})", sec, re.S)
        assert m, step
        assert f"DXSteps.open" in m.group(1) or "_openSetupStep('" + step + "')" in m.group(1), step


def test_backend_details_are_words_not_marks():
    src = (ROOT / "dx_app" / "core" / "setup_steps.py").read_text(encoding="utf-8")
    body = src[src.index("def setup_status("):]
    body = body[:body.index("\ndef ", 10)]
    assert gate.count(body) == 0, sorted({c for c in body if gate.count(c)})
