"""task 아이콘 한 표 (spec 2026-09-29 아이콘 체계 단계 3).

예전: task 마다 이모지가 다섯 군데에 따로 있었다 — Model Zoo (config.py · model_catalog.json), Planner 버튼,
Planner 의 읽히지 않는 _TASKS, dx_app 결과 안내 (VIS_HINTS). 같은 task 가 곳에 따라 🖌️/🎨/🖼️/🧩 였고, 📐 는
OBB 이기도 embedding 이기도 했다. 이제 원본은 config.py CATEGORIES 의 `icon` = sprite symbol `task-<key>` 하나다.
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPRITE = (ROOT / "shared" / "static" / "dx-icons.svg").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")
config = importlib.import_module("dx_modelzoo.core.config")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _symbol(name: str) -> str | None:
    m = re.search(r'<symbol id="' + re.escape(name) + r'"[^>]*>.*?</symbol>', SPRITE, re.S)
    return m.group(0) if m else None


def test_every_task_has_its_own_two_layer_symbol():
    for key, info in config.CATEGORIES.items():
        assert info["icon"] == f"task-{key}", (key, info["icon"])
        sym = _symbol(info["icon"])
        assert sym, f"sprite 에 {info['icon']} 이 없다"
        assert 'viewBox="0 0 24 24"' in sym and '<g class="f"' in sym and '<g class="l"' in sym, key


def test_the_bundled_catalog_carries_the_same_table():
    catalog = json.loads(_read("dx_modelzoo/data/model_catalog.json"))
    icons = {k: v.get("icon") for k, v in catalog["categories"].items()}
    assert icons == {k: v["icon"] for k, v in config.CATEGORIES.items()}


def test_the_sprite_is_built_by_the_script():
    """sprite 는 scripts/build_icon_sprite.py 의 결과다 — 손으로 고친 sprite 는 다음 빌드에 사라진다."""
    src = _read("scripts/build_icon_sprite.py")
    for key in config.CATEGORIES:
        assert f"S['task-{key}']" in src, key


def test_model_zoo_draws_task_icons_from_the_sprite():
    for rel in ("dx_modelzoo/static/js/catalog.js", "dx_modelzoo/static/js/detail.js"):
        src = _read(rel)
        assert "_escapeAttr(catInfo.icon" not in src and "escapeHtml(catInfo.icon" not in src, rel
        assert "info.icon || ''" not in src and "'🤖'" not in src, rel
        assert "_taskIcon(" in src, rel
    helper = _read("dx_modelzoo/static/js/app.js")
    assert "function _taskIcon(" in helper and "window.DXIcon(name" in helper


def test_planner_task_buttons_use_the_same_symbols():
    html = _read("dx_planner/templates/index.html")
    grid = html[html.index('<div class="task-grid">'):]
    grid = grid[:grid.index("</div>\n        </div>")]
    want = {"object_detection": "task-object_detection", "pose_estimation": "task-pose_estimation",
            "segmentation": "task-semantic_segmentation", "oriented_bbox": "task-obb_detection",
            "classification": "task-classification"}
    for task, symbol in want.items():
        btn = grid[grid.index(f'data-task="{task}"'):]
        btn = btn[:btn.index("</button>")]
        assert f"dx-icons.svg#{symbol}" in btn, task
    assert gate.count(grid) == 0
    assert "_TASKS" not in _read("dx_planner/static/js/wizard.js"), "읽히지 않는 task 표가 남아 있다"


def test_dx_app_result_hints_are_words_with_a_task_icon():
    src = _read("dx_app/static/js/inference.js")
    body = src[src.index("var VIS_HINTS={"):]
    body = body[:body.index("};")]
    assert gate.count(body) == 0, sorted({c for c in body if gate.count(c)})
    tail = src[src.index("if(VIS_HINTS[cat]){"):]
    assert "DXIcon('task-'+cat" in tail[:600]
    i18n = _read("dx_app/static/js/i18n.js")
    for key in re.findall(r"T\('([^']+)'\)", body):
        assert f"'{key}':" in i18n, key
        entry = i18n[i18n.index(f"'{key}':"):]
        entry = entry[:entry.index("},")]
        assert gate.count(entry) == 0, key
