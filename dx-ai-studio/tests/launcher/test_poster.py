from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _platform_info_left(html: str) -> str:
    match = re.search(
        r'<div class="platform-info-left">(?P<body>.*?)</div>\s*<div class="platform-info-right">',
        html,
        re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def _platform_usecases(html: str) -> str:
    match = re.search(
        r'<div class="platform-usecases">(?P<body>.*?)</div>\s*</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def _platform_values(html: str) -> str:
    match = re.search(
        r'<div class="platform-values">(?P<body>.*?)</div>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return match.group("body")


def test_landing_poster_uses_m1_m2_product_card():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    image_rel = "img/about/marketing/m1_m2.webp"
    image_path = ROOT / "launcher/static" / image_rel
    poster = re.search(
        r'<div class="landing-poster"[^>]*>.*?</div>',
        html,
        re.DOTALL,
    )

    assert poster is not None
    assert f'src="/static/{image_rel}"' in poster.group(0)
    assert "DX-M1 and DX-M2 NPU lineup" in poster.group(0)
    assert "representative-1.jpg" not in poster.group(0)
    assert "DEEPX representative" not in poster.group(0)
    assert 'src="/static/img/about/marketing/intelligented.png"' not in poster.group(0)
    assert "dxnn-sdk-fullstack-architecture-diagram" not in poster.group(0)
    assert image_path.exists()


def test_landing_poster_cannot_stack_above_anything():
    """The poster used to be absolutely positioned and it covered the page.

    It sat at right:10%, top:50%, z-index 4, 400px wide, with pointer-events
    juggled so clicks could reach the module cards behind it — and it was
    display:none below 1200px, so on a laptop it simply was not there. The
    stack was the bug; the fix is that there is no stack. It is a card in
    Resources, in flow, and the assertion is that it stays that way.
    """
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    poster = re.search(r"(?m)^\.landing-poster\s*\{(?P<body>[^}]*)\}", css)
    assert poster is not None
    body = poster.group("body")
    assert "position: absolute" not in body
    assert "position: fixed" not in body
    assert "z-index" not in body
    assert "pointer-events" not in body, "nothing to pass through any more"

    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    resources = re.search(
        r'<section class="home-section" id="resources">(?P<body>.*?)</section>',
        html,
        re.DOTALL,
    )
    assert resources is not None
    assert 'id="landingPoster"' in resources.group("body")
    assert 'id="ecosystemPoster"' in resources.group("body")


def test_module_cards_need_no_javascript_to_be_placed():
    """The cards must not flash stacked before a script positions them.

    The ring solved this by hiding every card until initOrbital() had written
    --orbit-x/--orbit-y onto each one — a JS layout pass the page had to wait
    for. A grid has no such window: CSS places the cards on first paint, so the
    guard, the ready class and the debounced resize handler are all gone with it.
    """
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    grid = re.search(r"\.studio-grid\s*\{(?P<body>[^}]*)\}", css)
    assert grid, ".studio-grid rule missing"
    assert "grid-template-columns" in grid.group("body")
    assert "--orbit-x" not in css, "cards must not be positioned by script"
    js = (ROOT / "launcher/static/launcher-app-frame.js").read_text(encoding="utf-8")
    assert "orbital-ready" not in js, "the JS layout pass should be gone"
    assert "ensureStudioReady" in js
    assert "_initLauncherCore" in js


def test_landing_poster_hint_sits_below_image():
    """The caption reads under the image, not over it.

    It was once absolutely positioned on top of the artwork, which is why the
    old rule had to say position:static to pull it back out. The poster is a
    flex column now, so the caption's place comes from the flow — assert the
    column, and that nothing has lifted the caption out of it again.
    """
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    poster = re.search(r"(?m)^\.landing-poster\s*\{(?P<body>[^}]*)\}", css)
    hint = re.search(r"(?m)^\.poster-hint\s*\{(?P<body>[^}]*)\}", css)

    assert poster is not None
    assert hint is not None
    assert "flex-direction: column" in poster.group("body")
    assert "position: absolute" not in hint.group("body")


def test_top_nav_tabs_scroll_instead_of_clipping_under_status_dots():
    """11 module tabs must scroll in .top-bar-center — right tabs were unclickable."""
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    frame = (ROOT / "launcher/static/launcher-app-frame.js").read_text(encoding="utf-8")
    center = re.search(r"\.top-bar-center\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
    nav = re.search(r"\.nav-tab\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)
    right = re.search(r"\.top-bar-right\s*\{(?P<body>[^}]*)\}", css, re.DOTALL)

    assert center is not None
    assert nav is not None
    assert right is not None
    assert "flex: 1" in center.group("body")
    assert "min-width: 0" in center.group("body")
    assert "overflow-x: auto" in center.group("body")
    assert "flex-shrink: 0" in nav.group("body")
    assert "flex-shrink: 0" in right.group("body")
    assert "scrollIntoView" in frame


def test_platform_info_left_uses_requested_five_image_sequence():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    left = _platform_info_left(html)
    image_sources = re.findall(r'<img\s+src="([^"]+)"', left)

    assert image_sources == [
        "/static/img/about/marketing/intelligented.png",
        "/static/img/about/marketing/ces.jpg",
        "/static/img/about/marketing/m1_m2.webp",
        "/static/img/about/marketing/products.jpg",
        "/static/img/about/marketing/dxnn-sdk-fullstack-architecture-diagram.png",
    ]
    for source in image_sources[1:]:
        assert (ROOT / "launcher/static" / (source[8:] if source.startswith("/static/") else source)).exists()


def test_platform_info_panel_uses_flex_layout():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    assert 'data-help-id="pm-agent-dev"' in html
    assert "Agent Dev" in html
    assert "8개의 전문 모듈" in html
    assert "8 specialized modules" in html
    assert 'class="platform-info-gallery"' not in html
    assert 'class="platform-info-body"' not in html

    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    panel = re.search(r"\.platform-info-panel\s*\{(?P<body>[^}]*)\}", css)
    left = re.search(r"\.platform-info-left\s*\{(?P<body>[^}]*)\}", css)
    right = re.search(r"\.platform-info-right\s*\{(?P<body>[^}]*)\}", css)

    assert panel is not None
    assert left is not None
    assert right is not None
    assert "display: flex" in panel.group("body")
    assert "max-width: 1440px" in panel.group("body")
    assert "overflow-y: auto" in panel.group("body")
    assert "max-height: 720px" in left.group("body")
    assert "overflow-y: auto" in left.group("body")
    assert "flex: 1" in right.group("body")
    assert ".platform-info-gallery" not in css
    assert ".platform-info-body" not in css


def test_home_cards_use_delegated_routing_not_inline_onclick():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    frame = (ROOT / "launcher/static/launcher-app-frame.js").read_text(encoding="utf-8")
    assert 'onclick="launch(' not in html
    assert 'onclick="showAboutView()' not in html
    assert 'onclick="showSdkLibrary()' not in html
    assert "initHomeClickRouting" in frame
    js = (ROOT / "launcher/static/platform-info.js").read_text(encoding="utf-8")
    assert "syncPlatformGalleryHeight" not in js
    assert "openPlatformInfo" in js
    assert "closePlatformInfo" in js
    assert "PM_LAUNCH_MAP" in js
    assert "pm-agent-dev" in js
    assert "launchFromPlatformItem" in js


def test_platform_usecases_show_five_wide_images():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    usecases = _platform_usecases(html)
    image_sources = re.findall(r'<img\s+src="([^"]+)"', usecases)

    assert image_sources == [
        "/static/img/about/use-cases/usecase-smart-factory-agv-robot.jpg",
        "/static/img/about/use-cases/usecase-security-cctv-ip-camera.jpg",
        "/static/img/about/use-cases/usecase-datacenter-hdd-rack.jpg",
        "/static/img/about/solutions/solution-smart-mobility-cover.jpg",
        "/static/img/about/solutions/solution-edge-computing-smart-city-cover.png",
    ]


def test_platform_usecases_sit_close_to_value_badges_and_fill_width():
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    values = re.search(r"\.platform-values\s*\{(?P<body>[^}]*)\}", css)
    usecases = re.search(r"\.platform-usecases\s*\{(?P<body>[^}]*)\}", css)
    images = re.search(r"\.pu-images\s*\{(?P<body>[^}]*)\}", css)
    image_items = re.search(r"\.pu-images img\s*\{(?P<body>[^}]*)\}", css)

    assert values is not None
    assert usecases is not None
    assert images is not None
    assert image_items is not None
    assert "margin-bottom: 5px" in values.group("body")
    assert "margin-top: 8px" in usecases.group("body")
    assert "display: grid" in images.group("body")
    assert "auto-fit" in images.group("body")
    assert "minmax(" in images.group("body")
    assert "height: 212px" in image_items.group("body")
    assert "height: 112px" not in css


def test_platform_value_badges_cover_core_studio_capabilities():
    html = (ROOT / "launcher/static/index.html").read_text(encoding="utf-8")
    values = _platform_values(html)

    assert values.count('class="pv-badge"') == 7
    for label in [
        "🚀 Zero-Code Deploy",
        "📦 End-to-End Solution",
        "⚡ 25~100+ TOPS",
        "🧠 On-Device AI",
        "🔧 ONNX→DXNN Compile",
        "🎛️ Simulation Ready",
        "📊 Real-Time Monitor",
    ]:
        assert label in values
    assert "🌐 Multi-App Studio" not in values


def test_platform_info_right_column_is_compact_enough_for_bottom_gallery():
    css = (ROOT / "launcher/static/style.css").read_text(encoding="utf-8")
    modules = re.search(r"\.platform-modules\s*\{(?P<body>[^}]*)\}", css)
    item = re.search(r"\.pm-item\s*\{(?P<body>[^}]*)\}", css)
    icon = re.search(r"\.pm-icon\s*\{(?P<body>[^}]*)\}", css)
    name = re.search(r"\.pm-name\s*\{(?P<body>[^}]*)\}", css)
    desc = re.search(r"\.pm-desc\s*\{(?P<body>[^}]*)\}", css)
    tagline = re.search(r"\.platform-tagline\s*\{(?P<body>[^}]*)\}", css)
    intro = re.search(r"\.platform-desc\s*\{(?P<body>[^}]*)\}", css)
    badge = re.search(r"\.pv-badge\s*\{(?P<body>[^}]*)\}", css)
    values = re.search(r"\.platform-values\s*\{(?P<body>[^}]*)\}", css)

    assert modules is not None
    assert item is not None
    assert icon is not None
    assert name is not None
    assert desc is not None
    assert tagline is not None
    assert intro is not None
    assert badge is not None
    assert values is not None
    title = re.search(r"\.platform-info-right h2\s*\{(?P<body>[^}]*)\}", css)
    usecase_title = re.search(r"\.pu-title\s*\{(?P<body>[^}]*)\}", css)
    usecase_tag = re.search(r"\.pu-tags > span\s*\{(?P<body>[^}]*)\}", css)

    assert title is not None
    assert usecase_title is not None
    assert usecase_tag is not None
    assert "font-size: 26px" in title.group("body")
    assert "gap: 6px" in modules.group("body")
    assert "margin-bottom: 8px" in modules.group("body")
    assert "padding: 4px 8px" in item.group("body")
    assert "font-size: var(--fs-sm)" in item.group("body")
    assert "font-size: var(--fs-lg)" in icon.group("body")
    assert "font-size: var(--fs-sm)" in name.group("body")
    assert "min-width: 78px" in name.group("body")
    assert "font-size: var(--fs-xs)" in desc.group("body")
    assert "line-height: 1.2" in desc.group("body")
    assert "font-size: var(--fs-lg)" in tagline.group("body")
    assert "margin-bottom: 7px" in tagline.group("body")
    assert "font-size: var(--fs-md)" in intro.group("body")
    assert "line-height: 1.4" in intro.group("body")
    assert "margin-bottom: 8px" in intro.group("body")
    assert "padding: 2px 5px" in badge.group("body")
    assert "font-size: 10px" in badge.group("body")
    assert "grid-template-columns: repeat(auto-fit" in values.group("body")
    assert "font-size: var(--fs-lg)" in usecase_title.group("body")
    assert "font-size: var(--fs-sm)" in usecase_tag.group("body")
