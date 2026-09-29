#!/usr/bin/env python3
"""UI 에 남은 이모지 아이콘을 단조 감소로 묶는 ratchet (spec 2026-09-29 아이콘 체계 §3).

스튜디오의 아이콘은 `shared/static/dx-icons.svg` 한 벌이다. 그런데 화면 곳곳의 아이콘은 아직 이모지다 —
툴바 🌏 ◒◓◑ 🎓, Setup 의 ①–⑥ ✅ ⏳, task 🎯🏷️, 페이지 제목, 튜토리얼 구역. 이모지는 OS · 글꼴마다 다르게
그려지고 (headless 캡처에서 ◒ 이 "-" 로 나왔다) 색 · 굵기를 테마가 정할 수 없다.

수백 곳이라 한 번에 걷지 않는다. css_token_gate · spacing_scale_gate 와 같은 방식: **지금 수를 파일별
상한으로 박고 늘어나는 것만 막는다.** 단계마다 걷어낸 만큼 `--update` 로 내린다.

세는 것: 그림 문자 (U+1F000–1FAFF), 기타 기호 · 딩뱃 (2600–27BF), 기술 기호 (2300–23FF — ⏳ ⌨ ⏹),
원 숫자 (2460–24FF — ①), 도형 (25A0–25FF — ▶ ◒ ■), 기타 기호 · 화살표 (2B00–2BFF — ⬇ ⭐), ℹ.
세지 않는 것: 화살표 (2190–21FF — → ↗), 문장 부호 (— · ›), 변형 선택자 (FE0F).
글자로 쓴 것뿐 아니라 JS 이스케이프 (\\uD83C\\uDF93 · \\u2705) 와 HTML 숫자 엔티티 (&#9662;) 도 센다.

대상: 모듈 · 공용의 `static/` 과 `templates/` (그리고 모든 모듈에 주입되는 shared/hw_widget) 아래 .js · .html · .css · .json. 튜토리얼 · 번역 사전 ·
레퍼런스 · 데이터도 센다 — 그곳의 아이콘도 이 체계로 옮긴다 (본문은 글자로).

계약: tests/shared/test_emoji_gate.py
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "config" / "emoji_baseline.json"

_RANGES = (
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2300, 0x23FF),
    (0x2460, 0x24FF),
    (0x25A0, 0x25FF),
    (0x2B00, 0x2BFF),
    (0x2139, 0x2139),
)
_SUFFIXES = (".js", ".html", ".css", ".json")
_SKIP = (".venv", "node_modules", "/var/", "/tests/", "/docs/", "/outputs/", "/data/models/", ".min.")


_JS_ESCAPE = re.compile(r"\\u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})|\\u([0-9a-fA-F]{4})")
_ENTITY = re.compile(r"&#(?:x([0-9a-fA-F]+)|(\d+));")


def _pictographic(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _RANGES)


def _decoded(text: str):
    """글자 그대로 쓴 것에 더해 JS 이스케이프 ('\\uD83C\\uDF93', '\\u2705') 와 HTML 숫자 엔티티
    ('&#9662;') 로 쓴 것도 센다 — tutorial-engine.js 의 🎓 · ✅ 가 이렇게 적혀 있었다."""
    for ch in text:
        yield ord(ch)
    for m in _JS_ESCAPE.finditer(text):
        if m.group(1):
            hi, lo = int(m.group(1), 16), int(m.group(2), 16)
            yield 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
        else:
            yield int(m.group(3), 16)
    for m in _ENTITY.finditer(text):
        yield int(m.group(1), 16) if m.group(1) else int(m.group(2))


def count(text: str) -> int:
    return sum(1 for cp in _decoded(text) if _pictographic(cp))


def _iter_files():
    for path in sorted(ROOT.rglob("*")):
        if path.suffix not in _SUFFIXES or not path.is_file():
            continue
        rel = "/" + str(path.relative_to(ROOT))
        if any(s in rel for s in _SKIP):
            continue
        parts = path.relative_to(ROOT).parts
        # hw_widget 은 static/ 밖에 있지만 모든 모듈에 주입되는 공용 화면이다.
        if "static" not in parts and "templates" not in parts and "hw_widget" not in parts:
            continue
        yield rel[1:], path


def count_tree() -> dict[str, int]:
    counts: dict[str, int] = {}
    for rel, path in _iter_files():
        n = count(path.read_text(encoding="utf-8", errors="ignore"))
        if n:
            counts[rel] = n
    return counts


def regressions(counts: dict[str, int], baseline: dict[str, int]) -> list[str]:
    """상한을 넘은 파일들 (새 파일은 상한 0)."""
    return [rel for rel, n in sorted(counts.items()) if n > baseline.get(rel, 0)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="현재 값으로 baseline 을 다시 쓴다 (걷어낸 뒤 내릴 때)")
    args = ap.parse_args(argv)

    counts = count_tree()
    total = sum(counts.values())

    if args.update:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(dict(sorted(counts.items())), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline 갱신: 파일 {len(counts)}개 · 이모지 {total}개")
        return 0

    if not BASELINE_PATH.is_file():
        print(f"baseline 이 없다: {BASELINE_PATH} (--update 로 만든다)")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    over = regressions(counts, baseline)
    print(f"UI 이모지 {total}개 · 파일 {len(counts)}개 (상한 합 {sum(baseline.values())})")
    for rel in over:
        print(f"  {rel}: 이모지가 {baseline.get(rel, 0)} → {counts[rel]} 로 늘었다. "
              f"DXIcon('<name>') 과 shared/static/dx-icons.svg 를 쓰세요")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
