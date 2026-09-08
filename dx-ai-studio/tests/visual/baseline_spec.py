"""What the visual-regression suite captures, and why each knob is there.

`settle_ms` and `mask` are not guesses — each was measured by screenshotting the
same commit twice and requiring 0 changed pixels (see the module docstring in
test_visual_regression.py).
"""
from __future__ import annotations

VIEWPORT = {"width": 1280, "height": 800}

_DEFAULT_SETTLE_MS = 6000

SPECS: dict[str, dict] = {
    "launcher": {"settle_ms": 8000},        # hub boots every module server first
    "dx_app": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_stream": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_compiler": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_modelzoo": {
        "settle_ms": _DEFAULT_SETTLE_MS,
        # 두 요소가 실행마다 미세하게 다르게 그려져 0.0205-0.0274% 를 오갔다 —
        # 임계 0.02% 바로 위라 게이트가 무작위로 붉어졌다. 임계를 올리면 진짜
        # 회귀까지 통과시키게 되므로, 불안정한 요소만 가린다.
        #   #sortSelect       네이티브 <select> 의 값 렌더가 호스트마다/실행마다 흔들린다
        #   .mz-dx-app-status dx_app 연결 상태 점 — 폴링 결과에 따라 색이 바뀐다
        "mask": ("#sortSelect", ".mz-dx-app-status"),
    },
    "dx_benchmark": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_planner": {
        "settle_ms": _DEFAULT_SETTLE_MS,
        # Same failure as dx_modelzoo's #sortSelect, found on the 1320-wide axis
        # where TARGET FPS finally comes into frame: Chromium draws a native
        # <select>'s value through the host font stack, and the resolution wobbles
        # between runs of one commit. Measured — five captures of the same commit
        # gave four at 0 px and one at 278 px in a 45×10 box holding the string
        # "30 FPS", against a 237 px budget. Waiting on document.fonts.ready does
        # not close it; the race is below the page. All three .ops-select controls
        # are the same control, so the mask covers the class rather than waiting
        # for each to scroll into a viewport and go red.
        "mask": (".ops-select",),
    },
    "dx_agent_dev": {
        "settle_ms": _DEFAULT_SETTLE_MS,
        # Showcase thumbnails are animated/lazily decoded, so a capture lands on
        # whichever frame happened to be up. Two captures taken back-to-back agree;
        # captures minutes apart drift 0.97-2.16%, which is why this was only
        # visible once the suite ran against a stored baseline.
        "mask": (".example-thumb",),
    },
    "dx_monitor": {
        "settle_ms": _DEFAULT_SETTLE_MS,
        # Live NPU/system telemetry. Unmasked this module drifts 0.0788% between
        # two captures of the same commit; masked it is pixel-identical.
        "mask": (
            "#chart-area",
            "#npu-topo",
            "#sysinfo-table",
            "#event-log",
            "#event-count",
            "#status-bar",
        ),
    },
}


# ── 캡처 축 ────────────────────────────────────────────────────
# 단일 축(1280 · en · dark) baseline은 이 개편의 회귀를 잡지 못한다.
# semantic 토큰/light 테마는 색을, 번역 길이는 레이아웃을 바꾸므로 둘 다 축이어야 한다.
THEMES = ("dark", "light")

# es 는 라벨이 가장 길어(Benchmark -> Evaluación de rendimiento) 탭 오버플로와
# 헤더 폭을 밀어낸다. en 은 기준선.
LOCALES = ("en", "es")


def axes() -> list[tuple[str, str, str]]:
    """(module, theme, locale) 조합. baseline 파일명의 근거."""
    return [
        (module, theme, locale)
        for module in sorted(SPECS)
        for theme in THEMES
        for locale in LOCALES
    ]


def baseline_name(module: str, theme: str, locale: str) -> str:
    return f"{module}__{theme}__{locale}.png"


# ── 반응형 축 ──────────────────────────────────────────────────
# 위 baseline 은 전부 1280 한 폭이라, breakpoint 를 옮기면 무엇이 달라지는지
# 볼 수 없다. 지금 제품은 19개 폭에서 갈리고 (600·640·700·720·768·769·900·
# 960·980·1024·1100·1200·1280·1360·1440·1600·1979) 그 값들을 스케일로 몰려면
# 각 구간이 어떻게 그려지는지 먼저 고정돼 있어야 한다.
#
# 폭은 breakpoint 사이 구간의 한가운데를 고른다 — 경계값을 찍으면 1px 차이로
# 결과가 뒤집혀 게이트가 불안정해진다.
#   650  = 600 과 768 사이   (격자가 1열로 접히는 경계 바로 위)
#   860  = 768 과 900 사이   (모바일→태블릿 구간)
#   1150 = 1100 과 1200 사이 (태블릿→데스크톱 구간)
#   1320 = 1200 과 1440 사이 (데스크톱→와이드 구간)
RESPONSIVE_WIDTHS = (650, 860, 1150, 1320)
RESPONSIVE_HEIGHT = 900

# 색이 아니라 배치를 보는 축이라 테마/언어는 하나면 된다.
RESPONSIVE_THEME = "dark"
RESPONSIVE_LOCALE = "en"


def responsive_axes() -> list[tuple[str, int]]:
    return [(module, width) for module in sorted(SPECS) for width in RESPONSIVE_WIDTHS]


def responsive_baseline_name(module: str, width: int) -> str:
    return f"{module}__w{width}.png"
