import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    paren = source.index("(", start)
    depth = 0
    close_paren = None
    for pos in range(paren, len(source)):
        if source[pos] == "(":
            depth += 1
        elif source[pos] == ")":
            depth -= 1
            if depth == 0:
                close_paren = pos
                break
    assert close_paren is not None
    brace = source.index("{", close_paren)
    depth = 0
    for pos in range(brace, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:pos]
    raise AssertionError(f"Could not parse function body for {signature}")


def test_monitor_dashboard_skips_hidden_polling_and_unchanged_status_render():
    source = _read(ROOT / "dx_monitor/static/js/dashboard.js")
    apply_body = _function_body(source, "function _applyHWData(")
    poll_body = _function_body(source, "function _startHWPoll(")
    events_body = _function_body(source, "function pollEvents(")

    assert "function _isMonitorVisible(" in source
    assert "function _hwStatusSignature(" in source
    assert "if (statusSig !== S._lastStatusSig)" in apply_body
    assert "if (!_isMonitorVisible()) return;" in poll_body
    assert "if (!_isMonitorVisible()) return;" in events_body


def test_benchmark_hover_hit_testing_is_raf_throttled():
    source = _read(ROOT / "dx_benchmark/static/js/dashboard.js")

    assert "function scheduleBenchmarkHover(chart, event)" in source
    assert "chart._hoverRaf = requestAnimationFrame(function()" in source
    assert "_handleHover: function(e){scheduleBenchmarkHover(this,e);}" in source
    assert "chart._handleHover=function(e){scheduleBenchmarkHover(this,e);};" in source


def test_benchmark_canvas_resize_writes_only_on_dimension_changes():
    source = _read(ROOT / "dx_benchmark/static/js/dashboard.js")

    assert "function setBenchmarkCanvasSize(" in source
    assert "if (canvas.width !== nextW) canvas.width = nextW;" in source
    assert "if (canvas.height !== nextH) canvas.height = nextH;" in source
    assert "this._canvas.width=w*dpr" not in source
    assert "this._canvas.height=h*dpr" not in source
    assert "canvas.width=w*dpr" not in source
    assert "canvas.height=h*dpr" not in source


def test_safe_transition_contracts_avoid_transition_all_on_hot_controls():
    """These controls must name the properties they animate, not use `all`.

    The check used to pin the exact declaration text, easing curve and
    duration included. That is a value assertion wearing a contract's clothes:
    the day the studio's motion moved to the measured Apple curve, five of
    these went red and the obvious "fix" would have been to paste the old
    curve back in. What actually matters is the shape — named properties, no
    `all`, on the controls that are hot enough for it to cost something.
    """
    checks = [
        # .dot 이었다. 그 요소는 상단 바의 상태 점 묶음과 함께 사라졌고, 스타일만
        # 남아 이 계약을 통과시키고 있었다 — 죽은 규칙을 지키는 계약이었다는 뜻이다.
        # 상태 표시는 이제 모듈 카드의 .orbital-status 가 맡으므로 그쪽을 본다.
        (ROOT / "launcher/static/style.css", ".orbital-status", ("background",)),
        (ROOT / "launcher/static/style.css", ".launch-card", ("background", "transform")),
        (ROOT / "dx_app/static/css/style.css", ".chat-model-btn",
         ("background-color", "color", "border-color", "box-shadow")),
        (ROOT / "dx_stream/static/css/stream.css", ".palette-item", ("background-color", "color")),
        (ROOT / "dx_benchmark/static/css/style.css", ".edgeguide-link", ("box-shadow", "transform")),
    ]
    for path, selector, props in checks:
        source = _read(path)
        # 규칙의 시작을 찾는다. 예전에는 source.index(selector) 로 첫 등장을 썼는데,
        # 그러면 선택자를 언급한 주석이 먼저 걸려 엉뚱한 블록을 검사한다 —
        # 실제로 그 선택자를 설명하는 주석 한 줄 때문에 이 계약이 붉어졌다.
        m = re.search(rf"(?m)^\s*{re.escape(selector)}\s*(?:,[^{{]*)?\{{", source)
        assert m, f"{selector} has no rule in {path.name}"
        start = m.start()
        block = source[start:source.index("}", start)]
        assert "transition:" in block, f"{selector} lost its transition"
        assert "transition: all" not in block, f"{selector} animates everything"
        line = block[block.index("transition:"):]
        line = line[:line.index(";")]
        for prop in props:
            assert prop in line, f"{selector} no longer names {prop}"
