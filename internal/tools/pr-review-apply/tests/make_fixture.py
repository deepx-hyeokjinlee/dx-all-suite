# SPDX-License-Identifier: Apache-2.0
"""Reduce a saved GHES PR page (.mhtml) to the blocks the parser needs, so a realistic fixture can
be committed (target < 250 KB). Keeps: <title>, the head-sha link, every timeline comment body,
every review-thread-component block. Drops: script/style/svg/template/form/details-menu and data-*
attributes. Usage: python3 make_fixture.py <full.mhtml> <out.mhtml>"""
from __future__ import annotations
import email, re, sys
from email import policy
from pathlib import Path

DROP_TAGS = ("script", "style", "svg", "template", "form", "details-menu", "tool-tip")


def shrink(html: str) -> str:
    for t in DROP_TAGS:
        html = re.sub(rf"<{t}\b[^>]*>.*?</{t}>", "", html, flags=re.S)
    html = re.sub(r'\s(data-(?!line-number)[\w-]+|aria-[\w-]+|title|style)="[^"]*"', "", html)
    return html


def main(src: str, dst: str) -> int:
    msg = email.message_from_bytes(Path(src).read_bytes(), policy=policy.default)
    parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    page = max(parts, key=lambda p: len(p.get_payload(decode=True)))
    html = page.get_payload(decode=True).decode("utf-8", "replace")
    title = re.search(r"<title>.*?</title>", html, re.S).group(0)
    head_link = re.search(r'<a[^>]*id="review-status-[^"]*"[^>]*>', html).group(0)
    # first timeline comment .. end (threads live here); keep 8 KB before it so the parser still
    # finds the author link and <relative-time> that precede the first comment body
    body_start = max(0, html.find('<div class="comment-body markdown-body') - 8000)
    keep = html[body_start:]
    out = f"<html><head>{title}</head><body>{head_link}</a>{shrink(keep)}</body></html>"
    loc = page.get("Content-Location")
    mime = ("MIME-Version: 1.0\nContent-Type: multipart/related; boundary=\"B\"\n\n--B\n"
            f"Content-Type: text/html; charset=utf-8\nContent-Location: {loc}\n\n{out}\n--B--\n")
    Path(dst).write_text(mime, encoding="utf-8")
    print(f"{dst}: {Path(dst).stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
