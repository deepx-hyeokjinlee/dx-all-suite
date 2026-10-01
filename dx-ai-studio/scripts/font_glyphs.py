"""스튜디오가 화면에 그리는 한중일 글자를 언어별로 모은다.

build_font_subsets.py 와 font_coverage_gate.py 가 이 함수를 같이 쓴다 — 만드는 쪽과
검사하는 쪽이 다른 글자를 보면 gate 가 의미를 잃는다.
"""
from __future__ import annotations

from pathlib import Path

from tools.i18n_audit.extractors import extract_inventory, iter_source_files

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ko", "ja", "zh-CN", "zh-TW")
# 화면에 나가는 파일만 본다. .py 에는 한국어 주석이 많아 subset 이 불어난다.
RENDERED_SUFFIXES = {".js", ".html", ".json"}


def is_hangul(cp: int) -> bool:
    return 0xAC00 <= cp <= 0xD7A3 or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F


def is_kana(cp: int) -> bool:
    return 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF


def is_han(cp: int) -> bool:
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF


def is_cjk_punct(cp: int) -> bool:
    return 0x3000 <= cp <= 0x303F or 0xFF00 <= cp <= 0xFFEF


def is_cjk(cp: int) -> bool:
    return is_hangul(cp) or is_kana(cp) or is_han(cp) or is_cjk_punct(cp)


def dictionary_glyphs(root: Path = ROOT) -> dict[str, set[int]]:
    """번역 사전에서 언어별로 뽑은 CJK 글자. gate 는 이것만 검사한다."""
    per: dict[str, set[int]] = {lang: set() for lang in LANGS}
    for rec in extract_inventory(root):
        for lang in LANGS:
            per[lang].update(cp for cp in map(ord, rec.texts.get(lang, "")) if is_cjk(cp))
    return per


def _is_rendered(path: Path, root: Path) -> bool:
    rel = "/" + path.relative_to(root).as_posix()
    return path.suffix in RENDERED_SUFFIXES and ("/static/" in rel or "/templates/" in rel)


def all_glyphs(root: Path = ROOT) -> dict[str, set[int]]:
    """사전 + 사전 밖에 직접 적힌 글자. subset 은 이것으로 만든다.

    사전 밖의 글자는 어느 언어의 것인지 모르므로 문자 종류로 나눈다: 한글은 ko,
    가나는 ja, 한자는 한자를 쓰는 세 언어 모두, 문장부호는 네 언어 모두.
    사전에서 이미 주인이 밝혀진 글자는 다시 나누지 않는다 — 정적 파일에는 사전
    문자열 자체도 적혀 있어서, 그대로 나누면 zh 사전의 한자가 ja 글꼴로 샌다.
    """
    per = dictionary_glyphs(root)
    known = set().union(*per.values())
    for path in iter_source_files(root):
        if not _is_rendered(path, root):
            continue
        for cp in map(ord, path.read_text(encoding="utf-8", errors="replace")):
            if cp in known:
                continue
            if is_hangul(cp):
                per["ko"].add(cp)
            elif is_kana(cp):
                per["ja"].add(cp)
            elif is_han(cp):
                for lang in ("ja", "zh-CN", "zh-TW"):
                    per[lang].add(cp)
            elif is_cjk_punct(cp):
                for lang in LANGS:
                    per[lang].add(cp)
    return per
