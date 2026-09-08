"""Contracts for the launcher home as a platform portal.

The home used to signal "advanced" with ornament — an orbital ring, a HUD frame,
a neon halo, a logo that decoded on load. That is a deliberate brand surface and
it is being kept, but it was written as 52 loose hex literals scattered through
the same stylesheet as the toolbar and the settings dialog. A literal is
invisible to the theme switch, so the chrome could never follow light mode while
its colours sat next to the splash's.

The split this file enforces: **brand colour is named and scoped, chrome colour
comes from the shared semantic tokens.** An intentionally dark hero is not a
light-theme bug — but it needs a name before it can be one.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STYLE = ROOT / "launcher" / "static" / "style.css"
INDEX = ROOT / "launcher" / "static" / "index.html"

# `--x: #hex` is a definition, not a use. The css_token_gate ignores those for the
# same reason: naming a colour is the fix, spraying it is the problem.
_VAR_DEF = re.compile(r"--[\w-]+\s*:[^;}]*")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# The palette the intro is built from. These may be *defined*, never *used* raw.
BRAND_LITERALS = (
    "#00D4FF", "#00d4ff",   # scanline, beams, gauge
    "#00FF88",              # module status
    "#FFD000", "#FFD700",   # core text, charge dot
    "#ff0040",              # decode glitch
    "#0A1628",              # splash ground
)

# Surfaces a user operates. These follow the theme, so they may name no literal.
CHROME_SELECTORS = (
    ".top-bar",
    ".launch-card",
    ".buy-topbar-btn",
    ".replay-btn",
    ".deepx-link",
    ".eco-link",
    ".route-recovery-notice",
    ".pu-tags > span",
    ".platform-info-close",
    ".studio-beta-badge",
)


def style() -> str:
    return STYLE.read_text(encoding="utf-8")


def uses_of(css: str) -> str:
    """The stylesheet with variable definitions removed — what is left is usage."""
    return _VAR_DEF.sub("", css)


def rule_body(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"{selector} rule missing from launcher/static/style.css"
    return m.group(1)


def test_brand_palette_is_defined_once_and_scoped():
    """The neon lives in one named block, not sprayed across the file."""
    css = style()
    assert "--brand-" in css, (
        "the intro palette has no name — define --brand-* tokens so the "
        "deliberately-dark surface is a decision instead of 52 stray literals"
    )
    defs = re.findall(r"--brand-[\w-]+\s*:", css)
    assert len(defs) >= 5, f"expected the intro palette as tokens, found {len(defs)}"


def test_brand_literals_are_never_used_raw():
    """A brand colour may be defined once; using it raw puts it beyond reach."""
    used = uses_of(style())
    leaked = sorted({lit for lit in BRAND_LITERALS if lit in used})
    assert not leaked, (
        f"brand colours used as literals instead of var(--brand-*): {leaked}"
    )


def test_chrome_selectors_carry_no_literal_colour():
    """Chrome follows the theme, so it may not name a colour of its own."""
    css = style()
    offenders = {}
    for selector in CHROME_SELECTORS:
        body = _VAR_DEF.sub("", rule_body(css, selector))
        hits = _HEX.findall(body)
        if hits:
            offenders[selector] = sorted(set(hits))
    assert not offenders, (
        "chrome must take colour from the shared semantic tokens "
        f"(--surface-*, --text-*, --status-*): {offenders}"
    )


# ── the portal nav ──────────────────────────────────────────────
# The home used to navigate twice to the same eight places: a dot strip across
# the top bar and a ring of tiles below it. Every other surface in the studio
# navigates from one place; the home was the exception.

NAV_SECTIONS = ("Home", "Models", "Studio", "Solutions", "Resources")


def index() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_portal_nav_exists_with_the_agreed_sections():
    html = index()
    assert 'class="portal-nav"' in html, "the home has no horizontal nav"
    for section in NAV_SECTIONS:
        assert f'data-nav="{section.lower()}"' in html, f"nav is missing {section}"


def test_the_duplicate_dot_strip_is_gone():
    """Eight dots and eight tiles pointed at the same eight modules."""
    html = index()
    assert 'class="status-dots"' not in html, (
        "the dot strip duplicates the module cards — module state belongs on "
        "the card it describes"
    )


def test_the_ring_left_the_resting_home():
    """The orbital survives as the intro, not as the layout.

    Eight tiles pinned to a circle can only scale, never rewrap: at 650px the
    cards clipped and the link column floated over the copy. Most of the
    launcher's breakpoints existed to prop that up.
    """
    css = style()
    assert "min-width: 769px" not in css and "min-width:769px" not in css, (
        "the orbital range query outlived the orbital layout"
    )
    html = index()
    ring_at_top = html.index('class="orbital-card"') if 'class="orbital-card"' in html else -1
    if ring_at_top >= 0:
        intro = html.index('id="splashOverlay"')
        assert ring_at_top > intro, (
            "orbital markup must live inside the intro overlay, not the resting home"
        )


# ── the hero ────────────────────────────────────────────────────
# The centre of the ring said "DEEPX / AI Studio / 8 Modules" in dimmed text
# behind a marketing collage. Two focal points at the same depth, so neither
# read. The hero says one thing and offers one input.


def test_hero_leads_with_a_prompt():
    html = index()
    assert 'class="home-hero"' in html, "the home has no hero"
    assert 'id="homeAsk"' in html, (
        "the hero must offer the input — a launcher whose front door is a menu "
        "makes you find the door first"
    )


def test_hero_never_shows_an_empty_box():
    """A blank prompt on a landing page is a blank stare.

    The example chips are the feature, not decoration: they teach the syntax
    and they are one click to run. They are also the contract the router in the
    next task has to satisfy.
    """
    html = index()
    chips = html.count('class="ask-chip"')
    assert chips >= 4, f"expected at least four example chips, found {chips}"


def test_hero_says_whether_the_hardware_is_there():
    """A website cannot say "DX-M1 connected". That line is why this is not one."""
    html = index()
    assert 'id="heroDeviceChip"' in html


def test_workflow_strip_is_drawable_in_both_themes():
    """The path from ONNX to silicon is the product, so it should be legible.

    It exists today as two raster diagrams authored on a dark ground. A PNG
    cannot follow the theme, and shipping a second one per theme is the
    duplication this redesign is removing — so the strip is inline SVG that
    inherits currentColor.
    """
    html = index()
    assert 'class="flow-strip"' in html, "no workflow strip on the home"
    strip = html[html.index('class="flow-strip"'):]
    strip = strip[: strip.index("</section>")] if "</section>" in strip else strip
    assert "<svg" in strip, "the strip must be drawn, not photographed"
    assert ".png" not in strip and ".jpg" not in strip, (
        "a raster diagram cannot follow the theme"
    )
    assert "currentColor" in strip, "the strip must inherit the text colour"


# ── the answered state ──────────────────────────────────────────


def test_answer_surface_exists_and_starts_hidden():
    html = index()
    assert 'id="homeAnswer"' in html, "the prompt has nowhere to answer"
    answer = html[html.index('id="homeAnswer"'):][:400]
    assert "hidden" in answer, "the answer surface must not occupy the resting home"


def test_the_agent_is_an_escalation_not_a_fourth_route():
    """Offering "build it from scratch" beside a preset we just found reads as
    if the studio does not trust its own answer.

    When we matched, the agent is one quiet line under the routes. When we did
    not, it is the whole answer — and it shows a plan before it spends minutes.
    """
    html = index()
    assert 'id="answerEscalate"' in html, "no quiet agent line under the routes"
    assert 'id="answerAgentPlan"' in html, "no agent plan for the unmatched case"
    css = style()
    escalate = rule_body(css, ".answer-escalate")
    assert "border-top" in escalate, (
        "the escalation sits below the routes as an aside, not among them"
    )


def test_the_plan_is_shown_before_the_agent_runs():
    """Escalating straight into a running agent is the jarring part.

    A few lines of "here is what I will do", with a time estimate, turns a leap
    into a decision — and gives the minutes an honest place to be declared.
    """
    html = index()
    plan = html[html.index('id="answerAgentPlan"'):]
    plan = plan[: plan.index("</section>")] if "</section>" in plan else plan[:1200]
    assert 'class="plan-steps"' in plan, "the agent must say what it will do first"
    assert 'id="answerAgentGo"' in plan, "and wait to be told to start"


# ── the sections ────────────────────────────────────────────────


def test_models_are_on_the_front_door():
    """133 models is the thing with pictures, and it sat one click in.

    The reference hub puts its catalogue directly under the hero. Ours had it
    behind a tile that said nothing about what was inside.
    """
    html = index()
    assert 'id="models"' in html, "no models section on the home"
    assert 'id="homeModelRow"' in html, "the model row has nowhere to render"


def test_module_cards_say_what_they_are():
    """A tile with a name and `--:—` is a launcher icon with extra steps."""
    html = index()
    grid = html[html.index('id="studioGrid"'):]
    grid = grid[: grid.index("</section>")] if "</section>" in grid else grid[:9000]
    assert grid.count('class="card-desc"') >= 8, (
        "every module card needs a sentence saying what it is for"
    )
    assert ":—" not in grid, "a placeholder port is not module state"
    assert grid.count('data-role="state"') >= 8, "each card must have a state line"


def test_ecosystem_and_solutions_surface_on_the_home():
    """Both exist today — one behind the ring, one buried in About DEEPX."""
    html = index()
    assert 'id="solutions"' in html
    assert 'id="resources"' in html
    assert 'class="eco-row"' in html


def test_module_state_comes_from_the_existing_poll():
    """One health poll, not two. The cards read what checkHealth already knows."""
    js = (ROOT / "launcher" / "static" / "launcher-app-frame.js").read_text(encoding="utf-8")
    assert js.count("setInterval(checkHealth") == 1, (
        "module state must not get a second poller"
    )
