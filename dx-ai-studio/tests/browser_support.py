"""Shared browser selection for DX AI Studio test gates."""
from __future__ import annotations

import os
from pathlib import Path
import shutil


_CHROMIUM_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


def resolve_chromium_executable() -> str | None:
    """Return a usable explicit or system Chromium executable, if available."""
    override = os.environ.get("DX_PLAYWRIGHT_EXECUTABLE")
    candidates = [override] if override else []
    candidates.extend(shutil.which(name) for name in _CHROMIUM_CANDIDATES)

    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None

# --- Multi-engine selection (Phase 2 cross-browser) -------------------------

ENGINES = ("chromium", "firefox", "webkit")
DEFAULT_ENGINE = "chromium"
_ENGINES_ENV = "DX_BROWSER_ENGINES"


def selected_engines() -> tuple[str, ...]:
    """Engines to run browser suites against.

    Defaults to chromium alone so the BLOCKING gate stays fast and single-engine.
    The cross-browser job opts in with ``DX_BROWSER_ENGINES=chromium,firefox``.
    Unknown names are rejected loudly — a typo that silently ran nothing would be
    worse than a failure.
    """
    raw = os.environ.get(_ENGINES_ENV, "").strip()
    if not raw:
        return (DEFAULT_ENGINE,)
    names = tuple(n.strip().lower() for n in raw.split(",") if n.strip())
    unknown = [n for n in names if n not in ENGINES]
    if unknown:
        raise ValueError(f"{_ENGINES_ENV} has unknown engine(s) {unknown}; known: {list(ENGINES)}")
    return names or (DEFAULT_ENGINE,)


def launch_browser(playwright, engine: str, **kwargs):
    """Launch ``engine``, reusing a host Chromium when Playwright has no cache.

    Only chromium gets the system-binary fallback: Playwright ships PATCHED
    Firefox/WebKit builds, so a distro firefox is not a substitute and pointing
    executable_path at one produces confusing protocol errors rather than a clean
    "not installed" message.
    """
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}; known: {list(ENGINES)}")
    if engine == "chromium":
        executable = resolve_chromium_executable()
        if executable:
            kwargs.setdefault("executable_path", executable)
    return getattr(playwright, engine).launch(headless=True, **kwargs)
