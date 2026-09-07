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
    "dx_modelzoo": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_benchmark": {"settle_ms": _DEFAULT_SETTLE_MS},
    "dx_planner": {"settle_ms": _DEFAULT_SETTLE_MS},
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
