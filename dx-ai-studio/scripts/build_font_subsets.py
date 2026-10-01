"""가변 글꼴 원본을 받아, 스튜디오가 실제로 쓰는 글자만 남긴 woff2 를 만든다.

    .venv/bin/python -m scripts.build_font_subsets

원본은 config/font_sources.json 에 URL 과 sha256 으로 고정하고 var/font-src/ 에
캐시한다 (git 무시). 커밋하는 것은 결과물과 라이선스뿐이다. 번역에 새 글자가
생겨 scripts/font_coverage_gate.py 가 실패하면 이것을 다시 돌린다.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

from scripts.font_glyphs import ROOT, all_glyphs

SOURCES = ROOT / "config" / "font_sources.json"
CACHE = ROOT / "var" / "font-src"
OUT = ROOT / "shared" / "static" / "fonts"
LAUNCHER_OUT = ROOT / "launcher" / "static" / "fonts"

# 라틴 글꼴에 남길 범위: 기본 라틴 + 확장 (es 포함), 결합 부호, 일반 문장부호, 통화,
# 문자형 기호(™), 화살표(→ ↗), 수학 기호, 도형(▶ ●), 체크(✓ ✕).
LATIN = [
    *range(0x20, 0x7F), *range(0xA0, 0x250), *range(0x300, 0x370),
    *range(0x2000, 0x2070), *range(0x20A0, 0x20D0), *range(0x2100, 0x2150),
    *range(0x2190, 0x2200), *range(0x2200, 0x2300), *range(0x25A0, 0x2600),
    0x2713, 0x2715,
]


def _fetch(label: str, file: str, url: str, sha256: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / file
    if not dest.exists():
        print(f"  받는 중 {label}: {url}")
        with urllib.request.urlopen(url, timeout=300) as resp:
            dest.write_bytes(resp.read())
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != sha256:
        raise SystemExit(f"{label}: sha256 {digest} != {sha256} — 원본이 바뀌었다. "
                         f"config/font_sources.json 을 확인하라")
    return dest


def _read(path: Path, member: str | None) -> bytes:
    if member is None:
        return path.read_bytes()
    with zipfile.ZipFile(path) as zf:
        return zf.read(member)


def _subset(font_bytes: bytes, unicodes, out: Path) -> None:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]   # tnum (카운트업 숫자 폭 고정), kern, liga …
    opts.name_IDs = ["*"]
    opts.hinting = False
    opts.notdef_outline = True
    # recalcTimestamp=False: 원본의 head.modified 를 그대로 둔다. 켜 두면 저장 시각이 들어가
    # 같은 입력에서도 매번 다른 파일이 나온다 (tests/shared/test_font_subsets.py).
    font = TTFont(io.BytesIO(font_bytes), recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=sorted(unicodes))
    sub.subset(font)
    font.flavor = "woff2"
    font.save(out)


def main() -> int:
    specs = json.loads(SOURCES.read_text(encoding="utf-8"))
    glyphs = all_glyphs()
    for name, spec in specs.items():
        src = _fetch(name, spec["file"], spec["url"], spec["sha256"])
        unicodes = LATIN if spec["lang"] == "latin" else glyphs[spec["lang"]]
        out = OUT / spec["output"]
        _subset(_read(src, spec["member"]), unicodes, out)

        lic = spec["license"]
        lic_src = (_fetch(f"{name} license", lic["file"], lic["url"], lic["sha256"])
                   if "url" in lic else src)
        (OUT / spec["license_output"]).write_bytes(_read(lic_src, lic["member"]))
        print(f"  {spec['output']:34} {len(unicodes):5} 글자  {out.stat().st_size // 1024:4} KB")

    inter = specs["inter"]["output"]
    shutil.copyfile(OUT / inter, LAUNCHER_OUT / inter)
    return 0


if __name__ == "__main__":
    sys.exit(main())
