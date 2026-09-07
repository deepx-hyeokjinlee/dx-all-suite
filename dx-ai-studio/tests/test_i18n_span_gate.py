"""언어별 형제 span 뭉치가 다시 늘지 않도록 묶는 ratchet.

한 문구를 `<span class="ko">…</span><span class="en">…</span>…` 6벌로 적는
마크업은 번역을 사전과 마크업 두 곳에 살게 만든다. 두 벌이 어긋나기 시작하면
어느 쪽이 맞는지 아무도 모른다 — 실제로 마이그레이션 때 125개 key 가
어긋나 있었다. 남은 뭉치는 key 하나에 문구가 둘이라 사람이 정해야 하는
것들뿐이고, 새로 생기는 것만 막으면 된다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.i18n_span_gate import BASELINE_PATH, count_groups, scan
from scripts.migrate_i18n_spans import MODULES, _load_dict, _markup_files

ROOT = Path(__file__).resolve().parent.parent


def test_count_groups_needs_two_adjacent_language_spans():
    assert count_groups('<span class="ko">가</span>') == 0
    assert count_groups('<span class="ko">가</span><span class="en">a</span>') == 1


def test_no_file_exceeds_its_lang_span_baseline():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    counts = scan()
    over = {
        rel: (n, baseline.get(rel, 0))
        for rel, n in counts.items()
        if n > baseline.get(rel, 0)
    }
    assert not over, (
        "언어별 span 뭉치가 늘었다 — data-i18n=\"English key\" 를 쓰고 번역은 "
        f"모듈 사전에 넣으세요: {over}"
    )


def test_lang_span_baseline_has_no_stale_headroom():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    counts = scan()
    stale = {
        rel: (counts.get(rel, 0), allowed)
        for rel, allowed in baseline.items()
        if counts.get(rel, 0) < allowed
    }
    assert not stale, (
        "baseline 에 여유분이 남았다. `python scripts/i18n_span_gate.py --write` 로 "
        f"조인다: {stale}"
    )


_KEY = re.compile(r'data-i18n(?:-html)?="([^"]*)"')
GAP_BASELINE = ROOT / "config" / "i18n_key_gaps.json"
WANTED = ("ko", "ja", "zh-CN", "zh-TW", "es")


def _key_gaps() -> dict[str, dict[str, list[str]]]:
    """마크업이 부르는데 사전이 못 채우는 key → 빠진 언어."""
    import html as _html

    out: dict[str, dict[str, list[str]]] = {}
    for name, (root, dict_rel) in MODULES.items():
        dictionary = _load_dict(dict_rel)
        for path in _markup_files(root):
            for raw in _KEY.findall(path.read_text()):
                key = _html.unescape(raw)
                entry = dictionary.get(key)
                if entry is None:
                    out.setdefault(name, {})[key] = list(WANTED)
                elif isinstance(entry, dict):
                    gaps = [lang for lang in WANTED if not entry.get(lang)]
                    if gaps:
                        out.setdefault(name, {})[key] = gaps
    return out


def test_no_new_untranslated_data_i18n_key():
    """사전이 못 채우는 key 는 화면에 영어가 그대로 남는다 — 늘리지 않는다.

    남아 있는 것들은 원래 `<span class="ko">`/`<span class="en">` 두 벌만 있던
    자리라 마이그레이션 전에도 ja/zh/es 는 영어로 떨어지고 있었다. 동작은
    그대로 두고, 새로 생기는 것만 막는다. launcher 의 about* 키는 사전이
    아니라 about-deepx.js 의 ABOUT_NAV_LABELS 가 채운다.
    """
    baseline = json.loads(GAP_BASELINE.read_text(encoding="utf-8"))
    gaps = _key_gaps()
    new: dict[str, dict[str, list[str]]] = {}
    for module, keys in gaps.items():
        known = baseline.get(module, {})
        for key, langs in keys.items():
            grew = [lang for lang in langs if lang not in known.get(key, [])]
            if grew:
                new.setdefault(module, {})[key] = grew
    assert not new, (
        "번역이 없는 data-i18n key 가 늘었다 — 모듈 사전에 번역을 넣으세요: "
        f"{new}"
    )


def test_key_gap_baseline_has_no_stale_entries():
    baseline = json.loads(GAP_BASELINE.read_text(encoding="utf-8"))
    gaps = _key_gaps()
    stale = {
        module: [k for k in keys if k not in gaps.get(module, {})]
        for module, keys in baseline.items()
    }
    stale = {m: k for m, k in stale.items() if k}
    assert not stale, f"채워진 key 가 baseline 에 남아 있다: {stale}"
