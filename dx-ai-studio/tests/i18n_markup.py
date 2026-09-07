""""이 컨트롤의 라벨은 6개 언어로 다 나오는가" 를 한 곳에서 판정한다.

예전에는 마크업이 언어마다 span 을 하나씩 들고 있어서, 계약 테스트도
`class="ko"` 가 있는지만 보면 됐다. 지금 라벨은 `data-i18n="English key"`
한 줄이고 번역은 모듈 사전에 산다. 확인할 것이 "span 6개"에서 "key 가
사전에서 5개 언어로 풀리는가"로 바뀌었을 뿐, 계약의 뜻은 그대로다.
"""
from __future__ import annotations

import html as _html
import re

from scripts.migrate_i18n_spans import _load_dict

LANGS = ("ko", "ja", "zh-CN", "zh-TW", "es")

_ATTR = re.compile(r'data-i18n(?:-html)?="([^"]*)"')
_SPAN = re.compile(r'class="(ko|ja|zh-CN|zh-TW|en|es)"')


def i18n_keys(fragment: str) -> list[str]:
    """조각 안에서 번역을 요구하는 key 들."""
    return [_html.unescape(k) for k in _ATTR.findall(fragment)]


def assert_translatable(fragment: str, dict_rel: str, label: str) -> None:
    """조각의 라벨이 6개 언어로 다 나오는지 확인한다.

    아직 언어별 span 을 쓰는 자리는 그 방식대로 인정한다 — key 하나에 문구가
    둘이라 옮기지 못하고 남은 뭉치들이 있다.
    """
    keys = i18n_keys(fragment)
    if not keys:
        found = set(_SPAN.findall(fragment))
        assert found >= {"en", *LANGS}, (
            f"{label}: 번역 경로가 없다 — data-i18n 도, 언어 span 도 없음 "
            f"(span: {sorted(found)})"
        )
        return

    dictionary = _load_dict(dict_rel)
    incomplete = {}
    for key in keys:
        entry = dictionary.get(key)
        if not isinstance(entry, dict):
            incomplete[key] = list(LANGS)
            continue
        gaps = [lang for lang in LANGS if not entry.get(lang)]
        if gaps:
            incomplete[key] = gaps
    assert not incomplete, f"{label}: 사전이 못 채우는 언어가 있다 — {incomplete}"
