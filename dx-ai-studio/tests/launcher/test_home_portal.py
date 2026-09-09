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

def index() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_every_nav_item_points_at_something_that_exists():
    """The nav named five sections; the workspace has three surfaces.

    Asserting a fixed list is how a nav ends up pointing at anchors that were
    deleted — which is exactly what happened when Models, Solutions and
    Ecosystem left the home. Assert the link instead: whatever the nav offers
    must resolve to an id in this document.
    """
    html = index()
    assert 'class="portal-nav"' in html, "the home has no horizontal nav"
    targets = re.findall(r'class="portal-nav-item[^"]*"[^>]*href="#([\w-]+)"', html)
    assert targets, "the nav has no items"
    for target in targets:
        assert f'id="{target}"' in html, f"nav points at #{target}, which is not on the page"


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


def test_the_prompt_is_the_first_thing_in_the_work_column():
    """The hero is gone; the command line took its job.

    A 38px headline and a two-line subtitle were spending the top of a local
    app's work surface on a pitch. The placeholder says the same thing in the
    place you would type it.
    """
    html = index()
    assert 'class="home-hero"' not in html, "the marketing hero is back"
    main = html[html.index('class="ws-main"'):]
    assert main.index('id="homeAsk"') < main.index('id="studioGrid"'), (
        "the prompt must come before the module grid"
    )
    ask = main[main.index('id="homeAsk"'):][:400]
    assert "placeholder" in ask, "an empty box with no example is a blank stare"


def test_the_modules_are_above_the_fold():
    """The only reason to open a launcher is to launch something.

    The previous home stacked seven full-width sections and put the eight
    module cards fourth, two scrolls down. In the workspace they sit directly
    under the command line, and everything that is not a tool is below both
    columns.
    """
    html = index()
    ws = html.index('class="workspace"')
    grid = html.index('id="studioGrid"')
    foot = html.index('class="ws-foot"')
    assert ws < grid < foot
    for gone in ('id="models"', 'id="ecosystem"', 'id="solutions"'):
        assert gone not in html, f"{gone} is a page section, not a work surface"


def test_the_state_column_yields_while_the_agent_runs():
    """The working view was asked for at full width, and it gets it."""
    css = style()
    assert "grid-template-columns" in rule_body(css, ".workspace.is-working")
    assert "display: none" in rule_body(css, ".workspace.is-working .ws-side")
    js = (ROOT / "launcher" / "static" / "home-console.js").read_text(encoding="utf-8")
    assert "is-working" in js, "nothing tells the workspace a run has started"


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
    assert 'class="ws-flow"' in html, "no workflow strip on the home"
    strip = html[html.index('class="ws-flow"'):]
    strip = strip[: strip.index("</nav>")]
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


def test_the_catalogue_size_lands_on_the_card_that_opens_it():
    """A five-across model row on the front door was a second Model Zoo.

    348 models belong in the module built to browse them; what the front door
    owes you is the number, on the card that goes there — and only when the zoo
    is actually up to be counted.
    """
    js = (ROOT / "launcher" / "static" / "home-sections.js").read_text(encoding="utf-8")
    assert "/zoo/api/catalog" in js, "the count must come from the zoo, not a constant"
    assert 'data-app="zoo"' in js, "the count has to land on the Model Zoo card"
    html = index()
    assert 'id="homeModelRow"' not in html, "the duplicate model row is back"


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


def test_what_leaves_the_app_sits_below_the_work_surface():
    """Ecosystem and Solutions were a partner list and four invented one-liners.

    Neither is state and neither is a tool, so on a workspace they were filler
    with the same visual weight as the modules. The links that do lead
    somewhere real survive in one quiet band under both columns.
    """
    html = index()
    foot = html[html.index('class="ws-foot"'):]
    assert 'class="deepx-links"' in foot, "the DEEPX links lost their home"
    assert 'id="replayBtn"' in foot, "the replay control was viewport-fixed; it is not now"
    side = html[html.index('class="ws-side"'):html.index('class="ws-foot"')]
    assert 'class="deepx-links"' not in side, (
        "a state column that also carries a link directory is not a state column"
    )


def test_module_state_comes_from_the_existing_poll():
    """One health poll, not two. The cards read what checkHealth already knows."""
    js = (ROOT / "launcher" / "static" / "launcher-app-frame.js").read_text(encoding="utf-8")
    assert js.count("setInterval(checkHealth") == 1, (
        "module state must not get a second poller"
    )

# ── the intro ───────────────────────────────────────────────────
# Three intros have shipped here. A 17.5-second neon cinematic, then a plain
# 1.2s fade that had no idea at all, and now four beats. The beats are the
# design, so they are the thing worth pinning — not the durations, which are
# tuning, and not the copy.


def test_the_intro_has_its_four_beats():
    """One point, then eight, then the light crosses the name, then no cut."""
    src = (ROOT / "launcher" / "static" / "launcher-splash.js").read_text(encoding="utf-8")
    for beat in ("_B1", "_B2", "_B3", "_B4"):
        assert beat in src, f"beat {beat} is gone"
    assert "is-seeded" in src, "beat 1: nothing shows the single point"
    assert "is-spread" in src, "beat 2: nothing spreads it into the eight"
    assert "is-revealed" in src, "beat 3: the wordmark is not being revealed"
    assert "is-landing" in src, "beat 4: the points never land"

    css = style()
    logo = rule_body(css, ".splash-logo")
    assert "clip-path" in logo, (
        "the wordmark must be revealed by the light crossing it, not faded in"
    )


def test_the_intro_ends_by_becoming_the_app():
    """The last frame of the intro is the first frame of the app.

    The points fly to where the real module tiles are and dissolve on them, so
    there is no cut between the intro and the UI — and the eight module colours
    are introduced by the thing that hands them over.
    """
    src = (ROOT / "launcher" / "static" / "launcher-splash.js").read_text(encoding="utf-8")
    assert ".orbital-card[data-app] .mod-tile" in src, (
        "the intro must read the real landing spots, not invent positions"
    )
    assert "completeLauncherBoot" in src, (
        "the app has to be visible before the curtain goes transparent, or there "
        "is nothing underneath to cut to"
    )
    assert "backgroundColor" in src, "the points must take the tiles' own colours"
    # A short window puts the last rows below the fold. Dropping those targets
    # made the counts disagree and the whole sequence fell back to a fade.
    assert "r.top > window.innerHeight" not in src, (
        "landing spots below the fold are still landing spots"
    )


def test_the_intro_yields_to_reduced_motion():
    src = (ROOT / "launcher" / "static" / "launcher-splash.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in src
    head = src[: src.index("var n = ns._SPLASH_MODULES.length")]
    assert "prefers-reduced-motion" in head, (
        "the reduced-motion exit must come before the sequence starts, not after"
    )
