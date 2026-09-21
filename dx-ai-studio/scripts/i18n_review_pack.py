#!/usr/bin/env python3
"""원어민 검토용 목록을 만든다.

왜 필요한가 — 여섯 언어 감사는 **칸이 채워졌는지** 만 판정한다(빈 칸, 영어 그대로).
문법이 맞는지, 어투가 자연스러운지, 그 나라에서 실제로 쓰는 말인지는 기계가
판정할 수 없다. 흉내 내면 "통과했지만 실제로는 어색한" 가짜 안전감이 생기고,
그것은 지금의 0건보다 나쁘다.

그래서 여기서는 판정하지 않는다. **사람이 볼 목록을 우선순위대로 정리**한다.
기계가 확실히 아는 것(같은 영어가 갈렸다 / 번역이 너무 길다 / 자리표시자가
사라졌다)을 근거로 순서를 매기고, 판단은 원어민에게 맡긴다.

사용 (`-m` 으로 부른다 — i18n_span_gate / breakpoint_gate 와 같은 방식이다.
경로를 직접 주면 저장소 루트가 sys.path 에 들어오지 않아 tools 를 못 찾고,
sys.path 를 손으로 건드리는 것은 tests/test_packaging_contract.py 가 막는다):

    .venv/bin/python -m scripts.i18n_review_pack --lang ko --out /tmp/review-ko.md
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from tools.i18n_audit.classify import (
    classify_length_overflow,
    classify_placeholder_mismatch,
    classify_terminology_drift,
)
from tools.i18n_audit.extractors import extract_inventory
from tools.i18n_audit.tutorial_copy import extract_tutorial_records

# 위가 급하다. 자리표시자가 사라지면 값이 안 보이고, 용어가 갈리면 제품이
# 조잡해 보이며, 길이는 넘칠 "위험" 일 뿐이다.
_ORDER = ["placeholder-mismatch", "terminology-drift", "length-overflow"]
_TITLE = {
    "placeholder-mismatch": "자리표시자가 사라졌거나 바뀜 — 값이 화면에 안 나옵니다",
    "terminology-drift": "같은 말이 화면마다 다르게 번역됨 — 하나로 통일이 필요합니다",
    "length-overflow": "번역이 영어보다 훨씬 김 — 버튼/라벨을 넘칠 수 있습니다",
}


def build(lang: str) -> str:
    records = extract_inventory(ROOT) + extract_tutorial_records(ROOT)
    findings = (classify_placeholder_mismatch(records)
                + classify_terminology_drift(records)
                + classify_length_overflow(records))
    mine = [f for f in findings if f"::{lang}::" in f.record_id]

    grouped: dict[str, list] = defaultdict(list)
    for f in mine:
        grouped[f.issue_type].append(f)

    out = [f"# 번역 검토 요청 — {lang}", ""]
    out += [
        "기계가 **확실히 아는 것만** 모았습니다. 문법이나 어투가 자연스러운지는",
        "판정하지 않았습니다 — 그 판단을 부탁드립니다.", "",
        f"- 대상 문자열: {len(records):,}건 중 {lang} 관련 지적 {len(mine)}건", "",
    ]
    for kind in _ORDER:
        items = grouped.get(kind, [])
        if not items:
            continue
        out += [f"## {_TITLE[kind]} ({len(items)}건)", ""]
        for f in items:
            out.append(f"- {f.message}")
            if f.suggested_fix:
                out.append(f"  - 참고: {f.suggested_fix}")
        out.append("")
    if not mine:
        out += ["기계가 잡을 수 있는 지적은 없습니다.", ""]
    out += [
        "## 이 목록에 **없는** 것", "",
        "아래는 기계가 못 봅니다. 눈에 띄면 알려주세요.", "",
        "- 오역 (뜻이 다름)",
        "- 어색한 말투 / 번역투",
        "- 존댓말·반말이 화면마다 섞임",
        "- 그 분야에서 실제로 쓰지 않는 용어", "",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", required=True, help="ko / ja / es / zh-CN / zh-TW")
    ap.add_argument("--out", help="쓸 파일 (없으면 표준출력)")
    args = ap.parse_args()
    text = build(args.lang)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
