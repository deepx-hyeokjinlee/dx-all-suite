"""The home runs the agent without leaving the page — on the module's API.

The home gets its own agent surface and dx_agent_dev keeps its own. That is two
UIs, and it must not become two implementations: the launcher already reverse
proxies the module at `/agent/`, so the home calls the same endpoints the module
calls. Nothing about running an agent is reimplemented here.

What is genuinely new is only the rendering. The stream is already typed —
`message` / `command` / `log` / `status` / `session` / `done` / `error` — and it
splits cleanly: prose on the left, terminal on the right.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "launcher" / "static"
CONSOLE = STATIC / "home-console.js"
INDEX = STATIC / "index.html"
STYLE = STATIC / "style.css"


def console() -> str:
    assert CONSOLE.is_file(), "launcher/static/home-console.js is missing"
    return CONSOLE.read_text(encoding="utf-8")


def rule(selector: str) -> str:
    """The rule whose selector is exactly this — not one that merely ends with it.

    `.work-term` and `.work-split.is-collapsed .work-term` both end in the same
    token, and matching the wrong one reads a display:none as the pane's own
    overflow behaviour.
    """
    css = STYLE.read_text(encoding="utf-8")
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"{selector} rule missing"
    return re.sub(r"\s+", "", m.group(1))


# ── one backend ─────────────────────────────────────────────────


def test_the_home_calls_the_modules_endpoints_through_the_proxy():
    src = console()
    for path in ("/agent/api/agent/run", "/agent/api/agent/cancel"):
        assert path in src, f"the home must reach the module at {path}"


def test_no_new_server_route_was_added_for_this():
    """If the home needed its own agent endpoint, there would be two of them.

    The launcher already proxies dx_agent_dev; adding a route here would mean
    the module's API and the home's could drift apart.
    """
    launcher = (ROOT / "launcher" / "launcher.py").read_text(encoding="utf-8")
    assert '"/api/agent' not in launcher, (
        "the home must consume the module's agent API, not republish it"
    )


def test_the_module_is_untouched_by_this_feature():
    """dx_agent_dev keeps its own console. This branch does not edit it."""
    src = console()
    assert "dx_agent_dev/" not in src


# ── the split ───────────────────────────────────────────────────


def test_working_view_splits_narration_from_terminal():
    html = INDEX.read_text(encoding="utf-8")
    for element_id in ("homeWork", "workNarration", "workTerminal", "workTerminalOut"):
        assert f'id="{element_id}"' in html, f"missing #{element_id}"


def test_the_split_is_fixed_and_the_terminal_collapses():
    body = rule(".work-split")
    assert "grid-template-columns" in body
    assert "38fr" in body and "62fr" in body, (
        "the transcript is where code and logs land, so it takes the larger half"
    )
    assert "grid-template-columns:1fr" in rule(".work-split.is-collapsed")


def test_terminal_scrolls_inside_its_own_pane():
    """Wide output must never make the page scroll sideways."""
    assert "overflow-x:auto" in rule(".work-term")


# ── event routing ───────────────────────────────────────────────


def test_events_go_to_the_side_that_can_show_them():
    src = console()
    routing = src[src.index("function renderEvent") :]
    for event in ("message", "command", "log", "status", "done", "error"):
        assert f"'{event}'" in routing, f"the stream's {event!r} event is unhandled"
    assert "'ping'" in src, "keepalives must be dropped, not rendered"


def test_activity_summary_counts_by_the_adapters_own_prefixes():
    """The adapter formats shell lines as `$ cmd` and file tools as `✓ action: path`.

    We control both ends, so counting by prefix is a contract rather than a
    guess — and an unrecognised prefix falls back to a plain total instead of
    inventing a category.
    """
    src = console()
    assert "'$ '" in src or '"$ "' in src, "no command prefix in the summary"
    assert "✓" in src, "no file-operation prefix in the summary"


def test_the_terminal_pins_when_the_user_scrolls_up():
    """A log that yanks itself to the bottom while you read is a log nobody reads."""
    src = console()
    assert "addEventListener('scroll'" in src, "the terminal never notices you scrolled"
    assert "follow" in src.lower()


def test_setup_controls_collapse_once_a_run_starts():
    """Agent, model and effort are setup, not operation.

    A form sitting on top while the agent works spends exactly the width this
    view exists to win.
    """
    src = console()
    assert "is-running" in src, "nothing marks the view as busy"
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="workSetupEdit"' in html, "collapsed setup must be reopenable"


def test_a_finished_run_ends_on_the_artefact():
    """The point of the minutes just spent is a thing you can execute."""
    src = console()
    assert "session_dir" in src, "the session folder is the payoff and must be shown"
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="workRunIt"' in html
    assert 'id="workOpenModule"' in html, (
        "the deeper flow lives in the module — the home must offer the door"
    )
