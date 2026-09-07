"""Visual Shell Header Contract Tests.

모든 surface의 shell header가 공유 토큰 계약을 준수하는지 검증한다.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parent.parent

SURFACES = {
    "launcher": ("launcher/static/index.html", "launcher/static/style.css"),
    # dx_app 은 통합 App Shell(Option A)로 이관되어 헤더를 dx-shell.css가 소유한다.
    "dx_app": ("dx_app/templates/index.html", "shared/static/dx-shell.css"),
    "dx_stream": ("dx_stream/templates/index.html", "shared/static/dx-shell.css"),
    "dx_compiler": ("dx_compiler/templates/base.html", "shared/static/dx-shell.css"),
    "dx_monitor": ("dx_monitor/templates/index.html", "shared/static/dx-shell.css"),
    "dx_planner": ("dx_planner/templates/index.html", "shared/static/dx-shell.css"),
    "dx_benchmark": ("dx_benchmark/templates/index.html", "shared/static/dx-shell.css"),
    "dx_modelzoo": ("dx_modelzoo/templates/index.html", "shared/static/dx-shell.css"),
}

# 모듈별 topbar 셀렉터
HEADER_SELECTORS = {
    "launcher": ".top-bar",
    "dx_app": ".dx-shell-header",
    "dx_stream": ".dx-shell-header",
    "dx_compiler": ".dx-shell-header",
    "dx_monitor": ".dx-shell-header",
    "dx_planner": ".dx-shell-header",
    "dx_benchmark": ".dx-shell-header",
    "dx_modelzoo": ".dx-shell-header",
}

# DXBrand.mount를 사용하는 모듈 (launcher는 커스텀 .logo 허용)
BRAND_MODULES = [
    "dx_app", "dx_stream", "dx_compiler",
    "dx_monitor", "dx_planner", "dx_benchmark", "dx_modelzoo",
]

SHARED_CSS_ORDER = [
    "/static/shared/module-chrome.css",
    "/static/shared/brand.css",
    "/static/shared/toolbar.css",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# 통합 App Shell(Option A)로 이관된 모듈 — 헤더/브랜드/툴바가 서버 렌더
# 시점에 주입되므로 템플릿 파일만 읽으면 보이지 않는다. 이관할 때 한 줄 추가한다.
MIGRATED_SHELL_MODULES = {
    "dx_app": ("dx_app.server", "DX_APP_SHELL"),
    "dx_stream": ("dx_stream.server", "DX_STREAM_SHELL"),
    "dx_benchmark": ("dx_benchmark.server", "DX_BENCHMARK_SHELL"),
    "dx_monitor": ("dx_monitor.server", "DX_MONITOR_SHELL"),
    "dx_agent_dev": ("dx_agent_dev.server", "DX_AGENT_DEV_SHELL"),
    "dx_modelzoo": ("dx_modelzoo.server", "DX_MODELZOO_SHELL"),
    "dx_planner": ("dx_planner.server", "DX_PLANNER_SHELL"),
    "dx_compiler": ("dx_compiler.server", "DX_COMPILER_SHELL"),
}


def surface_html(name: str) -> str:
    """서버가 실제로 내보내는 HTML."""
    template_rel, _ = SURFACES[name]
    html = read_text(ROOT / template_rel)
    if name not in MIGRATED_SHELL_MODULES:
        return html

    import importlib

    mod_path, spec_name = MIGRATED_SHELL_MODULES[name]
    from shared.shell import apply as apply_shell

    return apply_shell(html, getattr(importlib.import_module(mod_path), spec_name))


def _css_rule(css: str, selector: str) -> str:
    """selector에 해당하는 CSS 규칙 본문을 추출한다."""
    escaped = re.escape(selector)
    # 중첩되지 않은 단순 셀렉터 매칭
    pattern = escaped + r"\s*\{([^}]+)\}"
    matches = list(re.finditer(pattern, css))
    assert matches, f"selector {selector!r} not found in CSS"
    return matches[0].group(1)



class TestSharedCSSLoadOrder:
    """모든 템플릿이 module-chrome.css, brand.css, toolbar.css를 로컬 CSS보다 먼저 로드한다."""

    @pytest.mark.parametrize("name", SURFACES.keys())
    def test_shared_css_before_local(self, name):
        template_rel, css_rel = SURFACES[name]
        html = read_text(ROOT / template_rel)

        # 공유 CSS 파일들이 존재하는지 확인
        for href in SHARED_CSS_ORDER:
            base = href.split("?")[0]
            assert base in html, f"{name}: {href} missing from template"

        # 로컬 CSS href 패턴 (모듈별 로컬 경로로 정확히 매칭)
        LOCAL_CSS_TOKENS = {
            "launcher": '/style.css',
            "dx_app": '/static/css/style.css',
            "dx_stream": '/static/css/stream.css',
            "dx_compiler": '/static/css/style.css',
            "dx_monitor": '/static/css/style.css',
            "dx_planner": '/static/css/style.css',
            "dx_benchmark": '/static/css/style.css',
            "dx_modelzoo": '/static/css/style.css',
        }
        local_token = LOCAL_CSS_TOKENS[name]

        # 공유 CSS가 로컬 CSS보다 먼저 등장하는지 확인
        toolbar_base = "/static/shared/toolbar.css"
        toolbar_pos = html.find(toolbar_base)
        assert toolbar_pos >= 0, f"{name}: toolbar.css not found"

        # href="<local_token>" 형태로 정확히 찾기
        local_href = f'href="{local_token}'
        local_pos = html.find(local_href)
        if local_pos >= 0:
            assert toolbar_pos < local_pos, (
                f"{name}: shared toolbar.css must load before local {local_token}"
            )


class TestDXBrandSlot:
    """DXBrand.mount를 사용하는 모든 모듈이 id='dxBrand'를 가진다."""

    @pytest.mark.parametrize("name", BRAND_MODULES)
    def test_brand_slot_has_id(self, name):
        html = surface_html(name)

        assert 'id="dxBrand"' in html, (
            f"{name}: id='dxBrand' 슬롯이 반드시 존재해야 한다"
        )

    @pytest.mark.parametrize("name", BRAND_MODULES)
    def test_brand_subtitle_has_spanish_locale(self, name):
        template_rel, _ = SURFACES[name]
        html = read_text(ROOT / template_rel)

        subtitle_match = re.search(r"subtitle:\s*\{(?P<body>.*?)\n\s*\}", html, re.S)
        assert subtitle_match, f"{name}: DXBrand subtitle map missing"
        subtitle_body = subtitle_match.group("body")

        assert re.search(r"(?:^|[\s,])(?:'es'|\"es\"|es)\s*:", subtitle_body), (
            f"{name}: DXBrand subtitle map must define es to avoid English fallback"
        )


class TestShellHeightUsesSharedToken:
    """모든 모듈의 shell height가 --dx-module-header-h 또는 문서화된 반응형 별칭을 사용한다."""

    # 허용되는 height 값 패턴
    ALLOWED_HEIGHT_TOKENS = [
        "var(--dx-module-header-h)",
    ]

    # 각 모듈의 허용되는 로컬 별칭 (값이 --dx-module-header-h를 참조해야 함)
    ALLOWED_LOCAL_ALIASES = {
        "launcher": "--launcher-topbar-h",
        "dx_benchmark": "--benchmark-topbar-h",
        "dx_planner": "--topbar-h",
    }

    @pytest.mark.parametrize("name", SURFACES.keys())
    def test_header_height_token(self, name):
        _, css_rel = SURFACES[name]
        css = read_text(ROOT / css_rel)
        selector = HEADER_SELECTORS[name]

        body = _css_rule(css, selector)

        # height 또는 min-height 속성을 찾는다
        height_match = re.search(
            r"(?:min-)?height\s*:\s*([^;]+)", body
        )
        if not height_match:
            pytest.skip(f"{name}: no height property on {selector}")

        height_val = height_match.group(1).strip()

        # 직접 --dx-module-header-h 사용은 항상 허용
        if "var(--dx-module-header-h)" in height_val:
            return

        # 로컬 별칭 사용 시, 별칭이 --dx-module-header-h를 참조하는지 확인
        if name in self.ALLOWED_LOCAL_ALIASES:
            alias = self.ALLOWED_LOCAL_ALIASES[name]
            if f"var({alias})" in height_val:
                # 별칭 정의에서 --dx-module-header-h 참조 확인
                alias_pattern = re.escape(alias) + r"\s*:\s*([^;]+)"
                alias_match = re.search(alias_pattern, css)
                assert alias_match, f"{name}: alias {alias} not defined"
                alias_def = alias_match.group(1).strip()
                assert "var(--dx-module-header-h)" in alias_def, (
                    f"{name}: alias {alias} must reference --dx-module-header-h, "
                    f"got: {alias_def}"
                )
                return

        pytest.fail(
            f"{name}: {selector} height uses {height_val!r}, "
            f"must use var(--dx-module-header-h) or an allowed alias"
        )


class TestShellStylesUseSharedTokens:
    """모든 모듈의 shell 스타일이 공유 배경/테두리/엘리베이션 토큰을 사용한다."""

    REQUIRED_TOKENS = [
        ("background", "var(--dx-module-header-bg)"),
        ("border-bottom", "var(--dx-module-header-border)"),
        ("box-shadow", "var(--dx-module-header-elevation)"),
    ]

    @pytest.mark.parametrize("name", SURFACES.keys())
    def test_header_uses_shared_tokens(self, name):
        _, css_rel = SURFACES[name]
        css = read_text(ROOT / css_rel)
        selector = HEADER_SELECTORS[name]

        body = _css_rule(css, selector)

        for prop_hint, token in self.REQUIRED_TOKENS:
            assert token in body, (
                f"{name}: {selector} missing {token}"
            )


class TestBackdropFilterOnShellHeaders:
    """compiler를 제외한 모듈 shell header에 backdrop-filter가 존재한다.

    compiler의 #header는 별도 TestKnownExceptions에서 검증하므로 여기서 제외한다.
    """

    MODULES_REQUIRING_BACKDROP = [
        "dx_app", "dx_stream",
        "launcher", "dx_monitor", "dx_planner", "dx_benchmark", "dx_modelzoo",
    ]

    @pytest.mark.parametrize("name", MODULES_REQUIRING_BACKDROP)
    def test_backdrop_filter_present(self, name):
        _, css_rel = SURFACES[name]
        css = read_text(ROOT / css_rel)
        selector = HEADER_SELECTORS[name]

        body = _css_rule(css, selector)
        assert "backdrop-filter" in body, (
            f"{name}: {selector} missing backdrop-filter: var(--glass-blur)"
        )


class TestLanguageDropdownStacking:
    """app/stream의 공유 언어 드롭다운이 콘텐츠 카드 위에 표시된다."""

    CONTENT_LAYER_MAX = 100
    POPUP_LAYER_MIN = 300

    @pytest.mark.parametrize("name", ["dx_app", "dx_stream"])
    def test_topbar_stacks_language_menu_between_content_and_popups(self, name):
        _, css_rel = SURFACES[name]
        css = read_text(ROOT / css_rel)
        header_sel = HEADER_SELECTORS[name]
        host_sel = (
            ".dx-shell-header-right" if header_sel == ".dx-shell-header" else ".topbar-right"
        )
        topbar = _css_rule(css, header_sel)
        toolbar_host = _css_rule(css, host_sel)

        normalized_topbar = topbar.replace(" ", "")
        topbar_z = re.search(r"z-index\s*:\s*(\d+)\s*;", topbar)
        assert "position:relative" in normalized_topbar, (
            f"{name}: {header_sel} must be positioned so z-index lifts "
            "the language dropdown above page cards"
        )
        assert topbar_z, f"{name}: {header_sel} must declare explicit z-index"
        topbar_z_value = int(topbar_z.group(1))
        assert topbar_z_value > self.CONTENT_LAYER_MAX, (
            f"{name}: {header_sel} must stack above page content layers"
        )
        assert topbar_z_value < self.POPUP_LAYER_MIN, (
            f"{name}: {header_sel} must stay below popup/modal layers"
        )
        assert "overflow:visible" in normalized_topbar, (
            f"{name}: {header_sel} must not clip the language dropdown menu"
        )

        normalized_host = toolbar_host.replace(" ", "")
        toolbar_z = re.search(r"z-index\s*:\s*(\d+)\s*;", toolbar_host)
        assert "position:relative" in normalized_host, (
            f"{name}: .topbar-right must create a positioned host for "
            "the shared language dropdown"
        )
        assert toolbar_z, f"{name}: .topbar-right must declare explicit z-index"
        assert int(toolbar_z.group(1)) >= 1



class TestShellHeaderZIndexLayerLadder:
    """공유 shell 헤더가 페이지 콘텐츠 위, 팝업/모달 아래에 놓인다.

    구 버전은 모듈마다 z-index 사다리를 따로 세웠다(dx_monitor 는 .top-bar 를
    1000 이상으로). 이제 헤더가 하나뿐이므로 사다리도 한 곳에서 검증한다.
    """

    SHARED_POPUP_Z = 10000  # shared toolbar.css .dx-lang-menu
    CONTENT_LAYER_MAX = 100

    def _shell_header_z(self) -> int:
        css = read_text(ROOT / "shared/static/dx-shell.css")
        body = _css_rule(css, ".dx-shell-header")
        z = re.search(r"z-index\s*:\s*(\d+)", body)
        assert z, ".dx-shell-header must declare z-index"
        return int(z.group(1))

    def test_shell_header_sits_above_page_content(self):
        assert self._shell_header_z() > self.CONTENT_LAYER_MAX

    def test_shell_header_sits_below_the_shared_popup_layer(self):
        """헤더가 팝업보다 높으면 언어 드롭다운이 헤더 뒤로 숨는다."""
        assert self._shell_header_z() < self.SHARED_POPUP_Z

    def test_shell_rail_sits_below_the_header(self):
        """레일이 헤더보다 높으면 헤더의 드롭다운이 레일에 잘린다."""
        css = read_text(ROOT / "shared/static/dx-shell.css")
        rail = _css_rule(css, ".dx-shell-rail")
        z = re.search(r"z-index\s*:\s*(\d+)", rail)
        assert z, ".dx-shell-rail must declare z-index"
        assert int(z.group(1)) < self._shell_header_z()

    @pytest.mark.parametrize("name", sorted(MIGRATED_SHELL_MODULES))
    def test_migrated_module_content_stays_below_the_shell_header(self, name):
        """모듈 콘텐츠가 헤더보다 높으면 헤더를 덮는다.

        오버레이(toast, modal, chat picker)는 헤더 위가 맞으므로 제외한다 —
        본문 레이어만 본다.
        """
        module_css_rel = {
            "dx_app": "dx_app/static/css/style.css",
            "dx_stream": "dx_stream/static/css/stream.css",
            "dx_benchmark": "dx_benchmark/static/css/style.css",
            "dx_monitor": "dx_monitor/static/css/style.css",
            "dx_agent_dev": "dx_agent_dev/static/css/console.css",
            "dx_modelzoo": "dx_modelzoo/static/css/style.css",
            "dx_planner": "dx_planner/static/css/style.css",
            "dx_compiler": "dx_compiler/static/css/style.css",
        }[name]
        css = read_text(ROOT / module_css_rel)
        header_z = self._shell_header_z()
        # 헤더 위에 떠도 되는 것들: 팝업/모달류와, 화면 위를 떠다니는 위젯
        # (채팅 FAB, NPU 모니터 float). 이들은 헤더를 "덮는" 게 의도된 동작이다.
        overlay = re.compile(
            r"toast|modal|overlay|picker|menu|dropdown|lightbox|tooltip|drawer|popup"
            r"|chat|fab|float|widget|banner|spotlight|backdrop"
        )
        for m in re.finditer(r"([^{}]+)\{([^}]*z-index\s*:\s*(\d+)[^}]*)\}", css):
            selector, _body, z = m.group(1).strip().splitlines()[-1], m.group(2), int(m.group(3))
            if z <= header_z or overlay.search(selector.lower()):
                continue
            raise AssertionError(
                f"{name}: {selector!r} has z-index {z} above the shell header "
                f"({header_z}) but is not an overlay — it would cover the header"
            )


class TestKnownExceptions:
    """문서화된 예외가 올바르게 유지되는지 확인한다."""

    def test_launcher_custom_logo_allowed_but_topbar_h_references_shared(self):
        """launcher의 커스텀 .logo는 허용되나 --launcher-topbar-h는 --dx-module-header-h를 참조해야 한다."""
        css = read_text(ROOT / "launcher/static/style.css")
        # --launcher-topbar-h가 --dx-module-header-h를 참조하는지 확인
        match = re.search(r"--launcher-topbar-h\s*:\s*([^;]+)", css)
        assert match, "--launcher-topbar-h not defined"
        val = match.group(1).strip()
        assert "var(--dx-module-header-h)" in val, (
            f"--launcher-topbar-h must reference --dx-module-header-h, got: {val}"
        )

    def test_compiler_no_longer_needs_the_hash_header_exception(self):
        """compiler 의 #header 예외는 shell 이관으로 해소됐다.

        예외 목록은 남겨두면 다음 사람이 그대로 답습한다 — 근거가 사라지면 지운다.
        """
        css = read_text(ROOT / "dx_compiler/static/css/style.css")
        assert not re.search(r"^\s*#header\s*\{", css, re.M), (
            "#header 가 다시 생겼다 — 헤더는 shared/static/dx-shell.css 가 소유한다"
        )

    def test_benchmark_responsive_88px_via_named_alias(self):
        """benchmark의 반응형 88px 동작은 명명된 로컬 별칭 또는 명시적 미디어 규칙을 통해서만 허용된다."""
        css = read_text(ROOT / "dx_benchmark/static/css/style.css")

        # 88px가 존재한다면, @media 규칙 안에서만 허용
        if "88px" in css:
            # 88px가 @media 규칙 내부에 있는지 확인
            media_blocks = re.findall(r"@media[^{]*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", css)
            found_in_media = any("88px" in block for block in media_blocks)
            assert found_in_media, (
                "benchmark 88px must appear only inside @media rule"
            )

            # 88px는 명명된 별칭 변수에 할당되어야 함
            alias_pattern = r"--(?:benchmark-topbar-h|topbar-h)\s*:\s*88px"
            assert re.search(alias_pattern, css), (
                "benchmark 88px must be assigned to a named alias variable"
            )
