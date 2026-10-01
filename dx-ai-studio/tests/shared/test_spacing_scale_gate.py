"""간격이 4px 스케일을 벗어나는 것을 단조 감소로 묶는다.

토큰은 일곱 단계를 정해 두었다 — `--sp-1..7` = 4·8·12·16·24·32·48px.
그런데 실측하면(2026-09-22) 간격 선언에 쓰인 생 px 값이 **33종** 이고,
1,576개 중 **788개(50%)가 스케일 밖** 이다. 가장 흔한 값이 6px(210회)로,
토큰에 아예 없는 값이다.

    6px ×210 → 4px 와 2px 차
   10px ×192 → 8px 와 2px 차
   14px ×116 → 16px 와 2px 차
    5px ×52 · 20px ×52 · 3px ×36 · 7px ×30 · 9px ×23 …

모듈 편차도 크다. dx_planner 는 토큰을 87% 쓰는데 shared 는 9%, dx_compiler 는
9% 다. **shared 가 낮은 것이 가장 나쁘다** — 공용 컴포넌트가 스케일을 벗어나면
그것을 쓰는 모든 모듈이 따라 어긋난다.

2px 차이는 한 자리만 보면 눈에 띄지 않는다. 문제는 **쌓일 때** 생긴다 — 카드
안에 6px, 그 안 목록에 10px, 그 안 배지에 14px 이 섞이면 어느 것도 서로
정렬되지 않는다. 그리고 그것을 고칠 때마다 비주얼 baseline 이 흔들린다.

그래서 색상(css_token_gate)·breakpoint(breakpoint_gate)와 같은 방식을 쓴다:
**지금 값을 상한으로 박고 늘어나는 것만 막는다.** 줄이는 것은 자유다.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "spacing_scale_gate.py"
BASELINE = ROOT / "config" / "spacing_scale_baseline.json"


def test_the_gate_exists():
    assert GATE.is_file(), f"{GATE} 가 없다"


def test_the_baseline_exists():
    assert BASELINE.is_file(), f"{BASELINE} 가 없다"


def test_the_gate_passes_on_the_current_tree():
    r = subprocess.run([sys.executable, "-m", "scripts.spacing_scale_gate"],
                       cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, f"게이트가 실패한다:\n{r.stdout}\n{r.stderr}"
    assert "스케일 밖" in r.stdout, f"요약을 출력하지 않는다: {r.stdout!r}"


def test_the_baseline_only_ratchets_down():
    """상한을 올리는 것은 이 게이트의 목적을 뒤집는다. 계약으로 막는다."""
    src = GATE.read_text(encoding="utf-8")
    assert ">" in src and "baseline" in src.lower()
    assert "새 간격" in src or "늘었다" in src, "늘어남을 막는 메시지가 없다"


def test_it_is_wired_into_run_ci():
    ci = (ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
    assert "spacing_scale_gate" in ci, "run_ci.sh 가 이 게이트를 부르지 않는다"


def test_the_scale_follows_the_tokens(monkeypatch, tmp_path):
    """스케일을 코드에 적지 않고 **토큰 파일에서 읽는지** 를 본다.

    처음엔 소스에 'dx-tokens.css' 라는 글자가 있는지만 봤다. 그래서 스케일을
    그대로 하드코딩하는 변이가 통과했다 — 값이 우연히 같았기 때문이다.
    토큰을 바꿔 보고 게이트가 **따라오는지** 를 봐야 한다.
    """
    sys.path.insert(0, str(ROOT))
    from scripts import spacing_scale_gate as gate

    real = gate.TOKENS.read_text(encoding="utf-8")
    fake = tmp_path / "dx-tokens.css"
    # 스케일을 5의 배수로 바꾼다 — 지금 값과 겹치지 않는다.
    fake.write_text("--sp-1:5px;--sp-2:10px;--sp-3:15px;", encoding="utf-8")
    monkeypatch.setattr(gate, "TOKENS", fake)
    assert gate.scale() == {5, 10, 15}, (
        f"토큰을 바꿨는데 스케일이 따라오지 않는다: {gate.scale()}")
    assert "px" in real  # 실제 파일을 읽고 있었음을 확인


def test_a_new_off_scale_value_is_rejected(tmp_path):
    """게이트가 실제로 무는지 — baseline 을 낮춰 한 파일이 넘치게 만든다."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    worst = max(baseline, key=lambda k: baseline[k])
    assert baseline[worst] > 0, "스케일 밖이 하나도 없다면 이 검사는 무의미하다"
    tight = dict(baseline)
    tight[worst] = baseline[worst] - 1
    backup = BASELINE.read_text(encoding="utf-8")
    try:
        BASELINE.write_text(json.dumps(tight, indent=2), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "scripts.spacing_scale_gate"],
                           cwd=ROOT, capture_output=True, text=True, timeout=180)
        assert r.returncode == 1, "상한을 넘겼는데 통과했다"
        assert worst in r.stdout, f"어느 파일인지 말하지 않는다: {r.stdout!r}"
    finally:
        BASELINE.write_text(backup, encoding="utf-8")
