from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent


def read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _js_block(source: str, name: str) -> str:
    match = re.search(rf"{name}\s*=\s*(\{{.*?\}}|\[.*?\]);", source, re.DOTALL)
    assert match, f"{name} block not found"
    return match.group(1)


def test_launcher_runtime_does_not_register_sandbox():
    src = read("launcher/launcher.py")
    assert "SANDBOX_PORT" not in src
    assert "SANDBOX_DIR" not in src
    assert 'start_sub_server("DX Sandbox"' not in src
    assert "start_sub_server('DX Sandbox'" not in src
    assert '"DX Sandbox":' not in src
    assert "'DX Sandbox':" not in src
    referer_targets = re.search(r"_SUBAPP_REFERER_TARGETS\s*=\s*[\(\[](.*?)[\)\]]", src, re.DOTALL)
    assert referer_targets
    assert "/sandbox" not in referer_targets.group(1)
    assert "SANDBOX_PORT" not in referer_targets.group(1)
    route_body = re.search(r"def route\(self\):(?P<body>.*?)(?=\n    def |\nclass |\Z)", src, re.DOTALL)
    assert route_body
    assert "/sandbox" not in route_body.group("body")


def test_launcher_state_registers_exact_eight_release_modules():
    """Eight modules, no sandbox — checked where the app actually routes.

    This used to check APP_PATHS and then check the same eight names again in
    _SPLASH_MODULES, a second list the intro kept for itself. The intro no
    longer names modules and that list is gone, so there is one register now.
    The names themselves are asserted where they are shown: the home's list.
    """
    src = read("launcher/static/launcher-state.js")
    app_paths = _js_block(src, "window.DXLauncher.APP_PATHS")
    assert "sandbox" not in app_paths
    assert app_paths.count(":") == 8

    html = read("launcher/static/index.html")
    for name in ("App", "Stream", "Model Zoo", "Compiler",
                 "EdgeGuide", "Benchmark", "Monitor", "Agent Dev"):
        assert ">" + name + "<" in html, f"{name} is missing from the home's list"
    assert "DX Sandbox" not in html


def test_launcher_navigation_shortcuts_are_compact_eight_modules():
    src = read("launcher/static/launcher.js")
    assert "launch('sandbox')" not in src
    expected = {
        "1": "app",
        "2": "stream",
        "3": "zoo",
        "4": "compiler",
        "5": "planner",
        "6": "benchmark",
        "7": "dx_monitor",
        "8": "agent",
    }
    for key, app in expected.items():
        pattern = rf"e\.altKey\s*&&\s*e\.key\s*===\s*['\"]{key}['\"][\s\S]{{0,220}}?ns\.launch\(['\"]{app}['\"]\)"
        assert re.search(pattern, src), f"Alt+{key} should launch {app}"
    # Shortcuts are compact/contiguous: Alt+1..Alt+8, no gap and no 9th key.
    assert "e.key === '9'" not in src


def test_launcher_app_frame_has_no_sandbox_nav_or_health_binding():
    src = read("launcher/static/launcher-app-frame.js")
    assert "launch('sandbox')" not in src
    assert "active-sandbox" not in src
    assert "dotSandbox" not in src
    assert "orbStatusSandbox" not in src
    assert "DX Sandbox" not in src
    nav = re.search(r"NAV_TAB_CONFIG\s*=\s*\[(.*?)\];", src, re.DOTALL)
    assert nav
    assert "sandbox" not in nav.group(1)


def test_launcher_home_copy_and_cards_are_eight_module_release():
    html = read("launcher/static/index.html")
    assert 'data-app="sandbox"' not in html
    assert "pm-dx-sandbox" not in html
    assert "dotSandbox" not in html
    assert "DX Sandbox" not in html
    assert "7 Modules" not in html
    assert "7개 모듈" not in html
    assert "8 Modules" in html
    assert "8개 모듈" in html
    assert "8 specialized modules" in html
    assert "8 モジュール" in html
    assert "8 módulos" in html
    assert "8 个模块" in html
    assert "8 個模組" in html
    # The cards used to carry data-angle because the home laid them out on a
    # ring at eight fixed bearings. The portal home lays them out in a grid, so
    # the angle is gone — the ring survives only in the splash, which computes
    # its own bearings from the module count. What this test is for is unchanged:
    # eight modules, in order, with no ninth and no sandbox.
    # 2026-09-23: 무대의 5×2 칸 순서 (spec §4.1). 책 두 권 (SDK Library, About) 은
    # 모듈이 아니므로 여기 세지 않는다. 지키는 것은 그대로 — 여덟 개, 아홉 번째 없음,
    # sandbox 없음. 칸 순서를 바꾸면 여기도 같이 고친다.
    cards = re.findall(r'class="orbital-card"[^>]*\sdata-app="([^"]+)"', html)
    assert cards == [
        "app", "stream", "zoo", "compiler",
        "benchmark", "planner", "dx_monitor", "agent",
    ]


def test_the_intro_carries_no_module_list():
    """The intro stopped naming the modules, so the data it needed is gone too.

    It listed all eight — first on a ring with per-module bearings, then as a
    stagger of pills. The Gargantua sequence has one subject and it is not a
    menu. _SPLASH_MODULES and the icon table it fed were left behind by that
    change, and unread data is how a ninth module ends up with an invented
    bearing for a ring that no longer exists.
    """
    state = read("launcher/static/launcher-state.js")
    splash = read("launcher/static/launcher-splash.js")
    assert "_SPLASH_MODULES" not in state, "the intro's module list outlived its only reader"
    assert "_SPLASH_MODULES" not in splash
    assert "_MODULE_ICONS" not in splash, "the intro's icon table has no consumer"
    # The home's own list is where the eight modules are named, and it stays.
    html = read("launcher/static/index.html")
    assert html.count('class="orbital-card"') == 8
