"""SDK Library 목록을 dx-all-suite 의 md 에 맞춘다 (2026-10-01).

sdk-library-data.json 은 손으로 고른 목록 (drawer · section · 제목) 이다. 그 틀은 그대로 두고, 보여 줄 때:

- md 의 크기는 디스크에서 (손으로 적은 값은 175 개 중 125 개가 틀렸다)
- 한 section 안의 같은 파일은 한 번만
- 등록된 문서가 있는 ``docs`` 폴더에 새 md 가 생기면 그 section 에 저절로 (제목은 첫 ``#`` 줄) — 예전에는
  JSON 을 고치기 전까지 보이지 않았다. agent 지시 파일 (CLAUDE · AGENTS · copilot) 은 문서가 아니다.
- pymdownx snippet (``--8<-- "file"``) 을 펼친다 — dx_app 의 change log 가 그 한 줄이었다.

계약: tests/launcher/test_sdk_library_live.py
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

_NOT_DOCS = re.compile(r"^(claude|agents|copilot[-_]instructions)([-_].*)?\.md$", re.I)
_SNIPPET = re.compile(r'^-{2}8<-{2}\s+["\']([^"\']+)["\']\s*$', re.M)


def _title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("_", " ")


def _size(path: Path):
    try:
        return path.stat().st_size
    except OSError:
        return None


def augment(data: dict, suite_root) -> dict:
    suite_root = Path(suite_root)
    out = copy.deepcopy(data)
    registered = set()
    for drawer in out.get("drawers", []):
        for section in drawer.get("sections", []):
            seen, files = set(), []
            for f in section.get("files", []):
                p = f.get("path")
                if not p or p in seen:
                    continue
                seen.add(p)
                registered.add(p)
                if f.get("type") == "md" or str(p).endswith(".md"):
                    size = _size(suite_root / p)
                    if size is not None:
                        f["size"] = size
                files.append(f)
            section["files"] = files
    for drawer in out.get("drawers", []):
        for section in drawer.get("sections", []):
            dirs = sorted({str(Path(f["path"]).parent) for f in section["files"]
                           if str(f["path"]).endswith(".md") and "docs" in Path(f["path"]).parts})
            for d in dirs:
                folder = suite_root / d
                if not folder.is_dir():
                    continue
                for md in sorted(folder.glob("*.md")):
                    rel = f"{d}/{md.name}"
                    # 끊긴 symlink 은 문서가 아니다 (dx_stream docs 의 RELEASE_NOTES.md 는 '--8<-- …' 를 가리키는 깨진 link)
                    if rel in registered or _NOT_DOCS.match(md.name) or not md.is_file():
                        continue
                    registered.add(rel)
                    section["files"].append({"path": rel, "title": _title(md), "size": _size(md),
                                             "type": "md", "auto": True})
    return out


def allowed_paths(data: dict) -> set:
    return {f["path"] for d in data.get("drawers", []) for s in d.get("sections", [])
            for f in s.get("files", []) if f.get("path")}


def expand_snippets(text: str, doc_rel: str, suite_root, depth: int = 0) -> str:
    """``--8<-- "file"`` → 그 파일. pymdownx 는 snippet 을 mkdocs 의 base_path 에서 찾는다 — 여기서는 문서의
    폴더부터 위로 올라가며 처음 있는 것 (suite 밖으로는 나가지 않는다)."""
    suite_root = Path(suite_root).resolve()
    if depth > 4:
        return text

    def repl(m):
        name = m.group(1).strip()
        if name.startswith("/") or ".." in Path(name).parts:
            return m.group(0)
        d = (suite_root / doc_rel).parent
        while True:
            cand = (d / name).resolve()
            try:
                cand.relative_to(suite_root)
            except ValueError:
                break
            if cand.is_file():
                inner = cand.read_text(encoding="utf-8", errors="ignore")
                return expand_snippets(inner, str(cand.relative_to(suite_root)), suite_root, depth + 1)
            if d == suite_root or d == d.parent:
                break
            d = d.parent
        return m.group(0)

    return _SNIPPET.sub(repl, text)
