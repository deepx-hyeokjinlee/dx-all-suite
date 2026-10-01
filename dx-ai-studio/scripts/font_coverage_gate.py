"""번역 사전의 한중일 글자가 그 언어의 글꼴 subset 에 모두 있는지 확인한다.

없는 글자는 화면에서 다른 글꼴로 넘어가 한 문장 안에서 자형이 섞인다.
실패하면: .venv/bin/python -m scripts.build_font_subsets
"""
from __future__ import annotations

import json
import sys

try:
    from fontTools.ttLib import TTFont
except ImportError:  # run_ci.sh 는 pip install 을 하지 않는다 (air-gapped). 같은 안내를 준다.
    sys.exit("fonttools not found — install test deps first: "
             "<python> -m pip install -r requirements-ci.txt")

from scripts.font_glyphs import ROOT, dictionary_glyphs

SOURCES = ROOT / "config" / "font_sources.json"
FONTS = ROOT / "shared" / "static" / "fonts"

# dx-tokens.css 의 :root:lang(...) --font-cjk 와 같은 순서. 앞 글꼴에 없는 글자는 뒤 글꼴이
# 그리므로, gate 도 이 사슬 전체로 검사한다 (한 글꼴만 보면 멀쩡히 그려지는 글자로 실패한다).
CHAIN = {"ko": ("ko", "zh-CN"), "ja": ("ja", "zh-CN"), "zh-CN": ("zh-CN",), "zh-TW": ("zh-TW", "zh-CN")}


def missing_glyphs() -> dict[str, list[str]]:
    specs = json.loads(SOURCES.read_text(encoding="utf-8"))
    cmaps = {s["lang"]: TTFont(FONTS / s["output"]).getBestCmap()
             for s in specs.values() if s["lang"] != "latin"}
    missing: dict[str, list[str]] = {}
    for lang, cps in dictionary_glyphs().items():
        lacking = sorted(chr(cp) for cp in cps
                         if not any(cp in cmaps[f] for f in CHAIN[lang]))
        if lacking:
            missing[lang] = lacking
    return missing


def main() -> int:
    missing = missing_glyphs()
    if not missing:
        print("font coverage: 사전의 한중일 글자가 모두 subset 에 있다")
        return 0
    for lang, chars in missing.items():
        print(f"font coverage: {lang} 글꼴에 없는 글자 {len(chars)}개: {''.join(chars[:40])}")
    print("→ .venv/bin/python -m scripts.build_font_subsets")
    return 1


if __name__ == "__main__":
    sys.exit(main())
