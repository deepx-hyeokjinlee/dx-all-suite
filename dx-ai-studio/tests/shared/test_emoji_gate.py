"""UI 에 남은 이모지 아이콘을 단조 감소로 묶는다 (spec 2026-09-29 아이콘 체계 §3).

이모지는 OS · 글꼴마다 다르게 그려지고 (headless 캡처에서 ◒ 이 "-" 로 나왔다), 색과 굵기를 테마가
정할 수 없다. 수백 곳이라 한 번에 걷지 않는다 — css_token_gate · spacing_scale_gate 와 같이 지금 수를
파일별 상한으로 박고, 단계마다 내린다. 늘어나는 것만 막는다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "emoji_gate.py"
BASELINE = ROOT / "config" / "emoji_baseline.json"


def test_the_gate_and_its_baseline_exist():
    assert GATE.is_file(), f"{GATE} 가 없다"
    assert BASELINE.is_file(), f"{BASELINE} 가 없다"


def test_the_gate_passes_on_the_current_tree():
    r = subprocess.run([sys.executable, "-m", "scripts.emoji_gate"], cwd=ROOT,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, f"게이트가 실패한다:\n{r.stdout}\n{r.stderr}"
    assert "이모지" in r.stdout, r.stdout


def test_a_new_emoji_fails_the_gate(tmp_path, monkeypatch):
    import importlib
    gate = importlib.import_module("scripts.emoji_gate")
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    probe = "shared/static/__probe__.js"
    counts = dict(base)
    counts[probe] = 1
    assert gate.regressions(counts, base) == [probe]
    lower = {k: max(0, v - 1) for k, v in base.items()}
    assert gate.regressions(lower, base) == [], "줄어드는 것은 자유다"


def test_it_counts_pictographs_not_arrows():
    import importlib
    gate = importlib.import_module("scripts.emoji_gate")
    assert gate.count("✅ ⚠️ 🌏 ◒ ① ⏳") == 6
    assert gate.count("→ ← ↗ › — ·") == 0, "화살표 · 문장 부호는 이모지가 아니다"


def test_it_is_wired_into_run_ci():
    ci = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert "scripts.emoji_gate" in ci


def test_it_sees_emoji_written_as_escapes():
    """tutorial-engine.js 는 🎓 을 '\\uD83C\\uDF93' 로, hw_widget 은 ▾ 를 '&#9662;' 로 쓴다 — 글자만 세면
    가장 널리 쓰이는 공용 아이콘을 놓친다."""
    import importlib
    gate = importlib.import_module("scripts.emoji_gate")
    assert gate.count(r"'🎓 ' + t") == 1
    assert gate.count(r"'✅' '○' '→'") == 2, "→ (2192) 는 세지 않는다"
    assert gate.count("&#9662; &#x2705; &#8594;") == 2
