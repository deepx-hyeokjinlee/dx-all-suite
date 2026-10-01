#!/usr/bin/env python3
"""언어별 형제 span 뭉치를 data-i18n 한 줄로 바꾼다.

지금 마크업은 한 문구를 6번 쓴다:

    <span class="ko">저장</span><span class="ja">保存</span><span class="zh-CN">保存</span>
    <span class="zh-TW">儲存</span><span class="en">Save</span><span class="es">Guardar</span>

같은 문구가 사전(_DX_I18N_DICT)에도 들어 있어 번역이 두 곳에 산다. i18n.js 는
data-i18n 을 이미 지원하므로 마크업은 영어 한 벌만 남기면 된다:

    <span data-i18n="Save">Save</span>

    python -m scripts.migrate_i18n_spans            # 무엇이 바뀌는지만 출력
    python -m scripts.migrate_i18n_spans --apply    # 실제로 고친다

사전은 절대 덮어쓰지 않는다. 마크업에만 있던 번역은 새 key 로 추가하고,
사전과 값이 다르면 사전 쪽을 남긴 채 불일치로 보고한다 — 어느 쪽이 맞는지는
사람이 판단할 문제다.
"""
from __future__ import annotations

import argparse
import html as _html
import re
from pathlib import Path

from scripts.js_object_literal import object_span, parse_object_after, value_spans

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("ko", "ja", "zh-CN", "zh-TW", "en", "es")

# 모듈 → (마크업 glob, 사전 파일). launcher 는 사전이 HTML 안에 인라인이다.
MODULES = {
    "dx_app": ("dx_app", "dx_app/static/js/i18n.js"),
    "dx_stream": ("dx_stream", "dx_stream/static/js/stream-i18n.js"),
    "dx_compiler": ("dx_compiler", "dx_compiler/static/js/compiler-i18n.js"),
    "dx_planner": ("dx_planner", "dx_planner/static/js/i18n.js"),
    "dx_monitor": ("dx_monitor", "dx_monitor/static/js/i18n.js"),
    "dx_agent_dev": ("dx_agent_dev", "dx_agent_dev/static/js/i18n.js"),
    "launcher": ("launcher", "launcher/static/index.html"),
}

# 언어 클래스는 class 안 어디에 있어도 언어 span 이다.
# class="ko" 만 보던 시절엔 launcher 의 `class="deepx-link-label ko"` 9뭉치가
# 통째로 안 보였다 — 게이트가 0 을 보고하는 동안 54개 span 이 살아 있었다.
_ONE = (
    r'<span class="(?:[^"]*\s)?(ko|ja|zh-CN|zh-TW|en|es)(?:\s[^"]*)?">'
    r'((?:(?!</?span).)*?)</span>'
)
# 첫 span 앞의 공백은 먹지 않는다 — "🎬 <group>" 의 그 한 칸은 화면에 보인다.
# span 사이의 공백은 먹는다 — 보이는 span 은 하나뿐이라 앞뒤 공백으로 접힌다.
_GROUP = re.compile(_ONE + r"(?:\s*" + _ONE + r")+", re.S)
_SINGLE = re.compile(_ONE, re.S)

# JS 안에서 문자열을 이어붙여 만든 span 은 텍스트가 아니라 코드다.
_CONCAT = re.compile(r"""['"]\s*\+|\+\s*['"]""")


def _texts(block: str) -> dict[str, str]:
    """그룹 안의 언어별 원문. 같은 언어가 두 번 나오면 첫 것을 쓴다."""
    out: dict[str, str] = {}
    for lang, value in _SINGLE.findall(block):
        out.setdefault(lang, value.strip())
    return out


def _is_solo(text: str, start: int, end: int) -> bool:
    """그룹이 부모 엘리먼트의 유일한 내용인가."""
    before = text[max(0, start - 400) : start].rstrip()
    after = text[end : end + 200].lstrip()
    return before.endswith(">") and after.startswith("</")


# 자식을 가질 수 없는 태그. 이 뒤에 오는 span 뭉치는 자식이 아니라 형제다.
_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


def _parent_tag(text: str, start: int) -> tuple[int, str] | None:
    """그룹 바로 앞 여는 태그의 (시작 인덱스, 태그 원문)."""
    close = text.rfind(">", 0, start)
    if close < 0:
        return None
    open_at = text.rfind("<", 0, close)
    if open_at < 0:
        return None
    tag = text[open_at : close + 1]
    if tag.startswith("</") or tag.endswith("/>") or "<" in tag[1:]:
        return None
    if tag.count('"') % 2 or tag.count("'") % 2:
        # 속성값 안의 '>' 에서 잘린 조각이다 (onclick="f(a>b)"). 손대지 않는다.
        return None
    name = re.match(r"<([a-zA-Z][a-zA-Z0-9]*)", tag)
    if not name or name.group(1).lower() in _VOID:
        return None
    return open_at, tag


def _attr_escape(value: str) -> str:
    return _html.escape(value, quote=True)


_ENTITY = re.compile(r"&[a-zA-Z#][a-zA-Z0-9]*;")


class Finding:
    __slots__ = (
        "path", "key", "translations", "mode", "start", "end", "replacement",
    )

    def __init__(self, path, key, translations, mode, start, end, replacement):
        self.path = path
        self.key = key
        self.translations = translations
        self.mode = mode
        self.start = start
        self.end = end
        self.replacement = replacement


def _plan_file(path: Path) -> list[Finding]:
    text = path.read_text()
    found: list[Finding] = []
    for m in _GROUP.finditer(text):
        block = m.group(0)
        if _CONCAT.search(block):
            # '<span class="ko">' + t.ko + '</span>' 같은 조립식. 문자열이 아니라
            # 코드라서 key 를 뽑을 수 없다.
            continue
        tr = _texts(block)
        key = tr.get("en")
        if not key:
            # 영어가 없는 뭉치는 key 를 만들 수 없다. 손대지 않는다.
            continue
        has_html = any("<" in v for v in tr.values())
        attr = "data-i18n-html" if has_html else "data-i18n"
        # data-i18n 은 textContent 를 쓴다 — 사전 key 와 화면 문자열 둘 다
        # 엔티티가 풀린 상태여야 한다. data-i18n-html 은 원문 그대로 둔다.
        if has_html:
            key_attr = key
            body = key
        else:
            key_attr = _html.unescape(key)
            body = _html.escape(key_attr, quote=False)
            tr = {lang: _html.unescape(v) for lang, v in tr.items()}
        solo = _is_solo(text, m.start(), m.end())
        parent = _parent_tag(text, m.start()) if solo else None
        if parent and "data-i18n" not in parent[1]:
            open_at, tag = parent
            new_tag = tag[:-1].rstrip() + f' {attr}="{_attr_escape(key_attr)}">'
            found.append(
                Finding(path, key_attr, tr, "hoist", open_at, m.end(), new_tag + body)
            )
        else:
            found.append(
                Finding(
                    path,
                    key_attr,
                    tr,
                    "wrap",
                    m.start(),
                    m.end(),
                    f'<span {attr}="{_attr_escape(key_attr)}">{body}</span>',
                )
            )
    return found


def _markup_files(root: str) -> list[Path]:
    base = ROOT / root
    return sorted(
        p
        for p in list(base.rglob("*.html")) + list(base.rglob("*.js"))
        if "/node_modules/" not in p.as_posix()
    )


def _load_dict(rel: str) -> dict:
    return parse_object_after((ROOT / rel).read_text(), "_DX_I18N_DICT")


def _render_entry(key: str, tr: dict[str, str]) -> str:
    """사전에 이미 쓰이는 여러 줄 형태로 찍는다.

    한 줄로 찍으면 계약 테스트가 항목을 못 읽는다 — dx_compiler 의
    dict_entry() 는 `'key': {` 다음 줄부터 `\n  },` 까지를 본문으로 본다.
    """
    lines = [f"  {_js_str(key)}: {{"]
    for lang in LANGS:
        if lang == "en" or lang not in tr:
            continue
        name = lang if lang.isalpha() else _js_str(lang)
        lines.append(f"    {name}: {_js_str(tr[lang])},")
    lines.append("  },")
    return "\n".join(lines)


def _js_str(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _referenced_outside_spans(files: list[Path], key: str) -> list[str]:
    """key 가 lang-span 뭉치 말고 다른 경로로도 참조되는가.

    참조가 있으면 사전 값을 마크업 쪽으로 맞추는 순간 그 다른 화면들이 같이
    바뀐다. 그런 key 는 기계가 정할 문제가 아니라서 건드리지 않는다.
    """
    pat = re.escape(key)
    probes = (
        re.compile(r'data-i18n(?:-html)?="' + pat + r'"'),
        re.compile(r"T\(\s*['\"]" + pat + r"['\"]"),
    )
    hits = []
    for path in files:
        text = path.read_text()
        for probe in probes:
            m = probe.search(text)
            if m:
                hits.append(f"{path.relative_to(ROOT)}:{text[: m.start()].count(chr(10)) + 1}")
                break
    return hits


def _apply_dict_edits(rel: str, edits: dict[str, dict[str, str]]) -> None:
    """사전의 개별 언어 값만 제자리에서 교체한다."""
    path = ROOT / rel
    src = path.read_text()
    spans = value_spans(src, "_DX_I18N_DICT")
    patches = []
    for key, langs in edits.items():
        for lang, value in langs.items():
            start, end = spans[key][lang]
            patches.append((start, end, _js_str(value)))
    for start, end, text in sorted(patches, reverse=True):
        src = src[:start] + text + src[end:]
    path.write_text(src)


def _plan_module(name: str) -> dict:
    """모듈 하나의 마이그레이션 계획.

    key 하나는 번역 한 벌만 가질 수 있다. 그래서 같은 key 인데 화면마다 다른
    문구를 쓰고 있으면 (마크업끼리 어긋나거나, 사전과 어긋나는데 그 key 를
    다른 화면도 쓰고 있으면) 기계가 고를 수 없다 — 그런 key 는 통째로 남긴다.
    """
    root, dict_rel = MODULES[name]
    dictionary = _load_dict(dict_rel)
    files = _markup_files(root)

    findings: list[Finding] = []
    for path in files:
        findings.extend(_plan_file(path))

    # 1) key 별로 마크업이 주장하는 번역을 모은다.
    claims: dict[str, dict[str, set[str]]] = {}
    for f in findings:
        per_key = claims.setdefault(f.key, {})
        for lang, value in f.translations.items():
            if lang != "en":
                per_key.setdefault(lang, set()).add(value)

    # 2) 손댈 수 없는 key 를 가려낸다.
    blocked: dict[str, str] = {}
    edits: dict[str, dict[str, str]] = {}
    additions: dict[str, dict[str, str]] = {}
    for key, langs in claims.items():
        split = {lang: vs for lang, vs in langs.items() if len(vs) > 1}
        if split:
            lang, values = next(iter(split.items()))
            blocked[key] = (
                f"[{lang}] 마크업끼리 " + " ≠ ".join(sorted(repr(v) for v in values))
            )
            continue
        settled = {lang: next(iter(vs)) for lang, vs in langs.items()}
        existing = dictionary.get(key)
        if existing is None:
            additions[key] = settled
            continue
        if not isinstance(existing, dict):
            blocked[key] = "사전 항목이 문자열 (구형 포맷)"
            continue
        differing = {
            lang: value
            for lang, value in settled.items()
            if lang in existing and existing[lang] != value
        }
        if not differing:
            continue
        refs = _referenced_outside_spans(files, key)
        if refs:
            lang, value = next(iter(differing.items()))
            blocked[key] = (
                f"[{lang}] 사전 {existing[lang]!r} ≠ 마크업 {value!r} — "
                f"{refs[0]} 도 이 key 를 쓴다"
            )
        else:
            edits[key] = differing

    return {
        "dict_rel": dict_rel,
        "findings": [f for f in findings if f.key not in blocked],
        "blocked": blocked,
        "edits": edits,
        "additions": {k: v for k, v in additions.items() if k not in blocked},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="실제로 고친다")
    ap.add_argument("--module", action="append", help="특정 모듈만")
    args = ap.parse_args()

    totals = {"groups": 0, "hoist": 0, "wrap": 0, "add": 0, "fix": 0, "hold": 0}
    holds: list[str] = []

    for name in args.module or list(MODULES):
        try:
            plan = _plan_module(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] 계획 실패: {type(exc).__name__}: {exc}")
            return 2

        findings = plan["findings"]
        per_file: dict[Path, list[Finding]] = {}
        for f in findings:
            per_file.setdefault(f.path, []).append(f)

        totals["groups"] += len(findings)
        totals["hoist"] += sum(1 for f in findings if f.mode == "hoist")
        totals["wrap"] += sum(1 for f in findings if f.mode == "wrap")
        totals["add"] += len(plan["additions"])
        totals["fix"] += len(plan["edits"])
        totals["hold"] += len(plan["blocked"])
        holds += [f"  {name} {k!r} — {v}" for k, v in sorted(plan["blocked"].items())]

        print(
            f"[{name}] 그룹 {len(findings)} "
            f"(hoist {sum(1 for f in findings if f.mode == 'hoist')}, "
            f"wrap {sum(1 for f in findings if f.mode == 'wrap')}) · "
            f"사전 신규 {len(plan['additions'])} · 값 정정 {len(plan['edits'])} · "
            f"보류 {len(plan['blocked'])} · 파일 {len(per_file)}"
        )

        if not args.apply:
            continue

        for path, items in per_file.items():
            text = path.read_text()
            for f in sorted(items, key=lambda x: x.start, reverse=True):
                text = text[: f.start] + f.replacement + text[f.end :]
            path.write_text(text)

        if plan["edits"]:
            _apply_dict_edits(plan["dict_rel"], plan["edits"])

        if plan["additions"]:
            dpath = ROOT / plan["dict_rel"]
            src = dpath.read_text()
            start, end = object_span(src, "_DX_I18N_DICT")
            block = "\n".join(
                _render_entry(k, plan["additions"][k])
                for k in sorted(plan["additions"])
            )
            insert_at = src.rfind("}", start, end)
            headsrc = src[:insert_at].rstrip()
            if not headsrc.endswith((",", "{")):
                headsrc += ","
            marker = "\n  // ── 마크업 lang-span 에서 옮겨온 항목 ──\n"
            dpath.write_text(headsrc + marker + block + "\n" + src[insert_at:])

    print(
        f"\n합계: 그룹 {totals['groups']} "
        f"(hoist {totals['hoist']} / wrap {totals['wrap']}) · "
        f"사전 신규 {totals['add']} · 값 정정 {totals['fix']} · "
        f"보류 key {totals['hold']}"
    )
    if holds:
        print("\n보류 — key 하나에 문구가 둘이라 사람이 정해야 한다:")
        for line in holds:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
