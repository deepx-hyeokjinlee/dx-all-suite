# SPDX-License-Identifier: Apache-2.0
"""Text renderers: `show` table and per-thread reply bodies."""
from __future__ import annotations
import re

MARK = "<!-- dx-pr-review-apply {tid} -->"


def _loc(t: dict) -> str:
    name = t["path"].rsplit("/", 1)[-1] or "(summary)"
    return f"{name}:{t['start']}-{t['end']}" if t["end"] != t["start"] else f"{name}:{t['start']}"


def show(review: dict, decisions: dict, pending_only: bool = False) -> str:
    pr = review["pr"]
    out = [f"PR #{pr['number']} {pr['title']}  head={pr['head_sha'][:8]}  {pr['url']}", ""]
    s = review.get("summary") or {}
    if s.get("body"):
        out += [f"[summary] {s['author']} {s['created_at']}", *("    " + l for l in s["body"].splitlines()[:40]), ""]
    out.append(f"{'id':<9} {'state':<10} {'location':<48} first line")
    for t in review["threads"]:
        st = decisions.get(t["id"], {}).get("decision", "pending")
        if pending_only and st != "pending":
            continue
        first = t["body"].splitlines()[0] if t["body"] else ""
        out.append(f"{t['id']:<9} {st:<10} {_loc(t):<48} {first[:90]}")
    return "\n".join(out)


def reply_body(t: dict, d: dict) -> str:
    head = MARK.format(tid=t["id"]) + "\n"
    if d["decision"] == "apply":
        sha = d.get("commit", "")[:8]
        ref = f" — `{sha}`" if sha else ""
        return f"{head}반영했습니다{ref} (`{t['path']}:{t['start']}-{t['end']}`): {d['note']}"
    if d["decision"] == "skip":
        return f"{head}반영하지 않았습니다 — {d['note']}"
    return f"{head}보류 — {d['note']}"


def replies(review: dict, decisions: dict) -> list[dict]:
    out = []
    for t in review["threads"]:
        d = decisions.get(t["id"])
        if not d or d.get("decision") in (None, "no-action") or d.get("published_at"):
            continue
        out.append({"id": t["id"], "path": t["path"], "body": reply_body(t, d)})
    return out

