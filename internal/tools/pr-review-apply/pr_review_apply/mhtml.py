# SPDX-License-Identifier: Apache-2.0
"""GHES PR page (saved as .mhtml) -> normalized review dict.

Markup anchors (verified on PR #91, GHES 2026-09): each inline thread is a
`<div class="review-thread-component ...">` block containing the file path
(`Link--primary`), the line range (`js-multi-line-preview-start/end`, else the last
`data-line-number`), the diff context (`blob-code-inner` spans), `id="discussion_r<id>"`
and one or more `<div class="comment-body markdown-body ...">` bodies. Comment bodies that
are not inside a thread block are top-level timeline comments (PR description, review summary)."""
from __future__ import annotations
import email
import html as _html
import re
from email import policy
from pathlib import Path
from typing import Optional

_PR_URL = re.compile(r"^(?P<host>https?://[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<num>\d+)")
_BODY_OPEN = re.compile(r'<div class="comment-body markdown-body[^"]*">')
_BODY_CLOSE = "</task-lists>"


def load_mhtml(path) -> tuple[str, str]:
    """Return (pr_url, html) of the text/html part whose Content-Location is a PR URL."""
    msg = email.message_from_bytes(Path(path).read_bytes(), policy=policy.default)
    best: Optional[tuple[str, str]] = None
    for p in msg.walk():
        if p.get_content_type() != "text/html":
            continue
        body = p.get_payload(decode=True).decode("utf-8", "replace")
        loc = p.get("Content-Location") or ""
        if _PR_URL.match(loc) and (best is None or len(body) > len(best[1])):
            best = (loc.split("#")[0].split("?")[0], body)
    if best is None:
        raise ValueError(f"{path}: no text/html part whose Content-Location is a PR URL")
    return best


def html_to_text(s: str) -> str:
    s = re.sub(r"<(script|style|template|svg)\b[^>]*>.*?</\1>", "", s, flags=re.S)
    s = re.sub(r"<pre\b[^>]*>", "\n```\n", s)
    s = re.sub(r"</pre>", "\n```\n", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|div|li|tr|h\d|summary|blockquote)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def _bodies(seg: str, offset: int = 0) -> list[dict]:
    out = []
    for m in _BODY_OPEN.finditer(seg):
        end = seg.find(_BODY_CLOSE, m.end())
        raw = seg[m.end(): end if end > 0 else m.end() + 20000]
        before = seg[max(0, m.start() - 8000): m.start()]
        auth = re.findall(r'class="author[^"]*"[^>]*>([\w-]+)</a>', before)
        ts = re.findall(r'<relative-time[^>]*datetime="([^"]+)"', before)
        out.append({"author": auth[-1] if auth else "?", "created_at": ts[-1] if ts else "",
                    "body": html_to_text(raw), "pos": offset + m.start()})
    return out


def parse_html(html: str, url: str, source: dict) -> dict:
    m = _PR_URL.match(url)
    if not m:
        raise ValueError(f"not a PR url: {url}")
    number = int(m["num"])
    pr = {"host": m["host"], "owner": m["owner"], "repo": m["repo"], "number": number, "url": url,
          "title": "", "head_sha": "", "head_ref": "", "base_ref": ""}
    t = re.search(r"<title>(.*?)</title>", html, re.S)
    if t:
        pr["title"] = _html.unescape(re.sub(r"\s+", " ", t.group(1))).split(" by ")[0].strip()
    sha = re.search(rf"pull/{number}/files/([0-9a-f]{{40}})", html)
    pr["head_sha"] = sha.group(1) if sha else ""
    refs = re.search(r"wants to merge\s+\d+\s+commits?\s+into\s+(\S+)\s+from\s+(\S+)", html_to_text(html[:400000]))
    if refs:
        pr["base_ref"], pr["head_ref"] = refs.group(1), refs.group(2)

    starts = [x.start() for x in re.finditer(r'class="review-thread-component', html)] + [len(html)]
    threads = []
    for i in range(len(starts) - 1):
        seg = html[starts[i]:starts[i + 1]]
        cid = re.search(r'id="discussion_r(\d+)"', seg)
        path = re.findall(r'Link--primary[^>]*>\s*([^<\s]+)\s*</a>', seg)
        rng = re.findall(r'js-multi-line-preview-(?:start|end)[^>]*>\s*[+-]?(\d+)', seg)
        single = re.findall(r'data-line-number="(\d+)"', seg)
        code = re.findall(r'<span class="blob-code-inner[^"]*">(.*?)</span>\s*</td>', seg, flags=re.S)
        bodies = _bodies(seg, starts[i])
        start = int(rng[0]) if rng else (int(single[-1]) if single else 0)
        end = int(rng[-1]) if rng else start
        tid = f"r{cid.group(1)}" if cid else f"thread{i}"
        threads.append({
            "id": tid, "url": f"{url}#discussion_{tid}", "path": path[0] if path else "",
            "start": start, "end": end,
            "diff_context": "\n".join(html_to_text(c) for c in code),
            "author": bodies[0]["author"] if bodies else "?",
            "created_at": bodies[0]["created_at"] if bodies else "",
            "body": bodies[0]["body"] if bodies else "",
            "replies": [{k: b[k] for k in ("author", "created_at", "body")} for b in bodies[1:]],
            "resolved": "Unresolve conversation" in seg,
        })
    top = [b for b in _bodies(html)
           if not any(starts[k] <= b["pos"] < starts[k + 1] for k in range(len(starts) - 1))]
    empty = {"author": "", "created_at": "", "body": ""}
    description = top[0] if top else dict(empty)
    summary = next((b for b in top[1:] if b["author"] != description["author"]), dict(empty))
    for d in (description, summary):
        d.pop("pos", None)
    return {"schema": 1, "source": source, "pr": pr, "description": description, "summary": summary,
            "threads": threads}


def parse_file(path) -> dict:
    url, html = load_mhtml(path)
    return parse_html(html, url, {"kind": "mhtml", "path": str(path)})
