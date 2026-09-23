# SPDX-License-Identifier: Apache-2.0
"""GHES REST v3 client + live fetch + publish. Token chain mirrors ghes-sync
(GHES_SYNC_DST_TOKEN > GH_ENTERPRISE_TOKEN > GHES_TOKEN > GH_TOKEN); without a token the `gh` CLI
(`gh api`) is used if present. Transport objects expose `request(method, url, payload) -> (code, json)`
so tests inject a fake."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from . import render, store
from .mhtml import _PR_URL

TOKEN_VARS = ("GHES_SYNC_DST_TOKEN", "GH_ENTERPRISE_TOKEN", "GHES_TOKEN", "GH_TOKEN")


def token_from_env() -> tuple[str, str]:
    for k in TOKEN_VARS:
        if os.environ.get(k):
            return k, os.environ[k]
    return "", ""


def api_base(host: str) -> str:
    h = host.rstrip("/")
    return "https://api.github.com" if h.endswith("github.com") else h + "/api/v3"


class UrllibTransport:
    def __init__(self, token: str, timeout: int = 30):
        self.token, self.timeout = token, timeout

    def request(self, method, url, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"token {self.token}", "Accept": "application/vnd.github+json",
            "Content-Type": "application/json", "User-Agent": "dx-pr-review-apply"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read().decode("utf-8", "replace")
                return r.status, (json.loads(body) if body.strip() else {})
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(body)
            except ValueError:
                return e.code, {"message": body[:300]}


class GhCliTransport:
    """`gh api` fallback (gh must be logged in to the GHES host)."""

    def request(self, method, url, payload=None):
        cmd = ["gh", "api", "-X", method, url, "--include"] + (["--input", "-"] if payload is not None else [])
        r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None,
                           text=True, capture_output=True)
        sep = "\r\n\r\n" if "\r\n\r\n" in r.stdout else "\n\n"
        head, _, body = r.stdout.partition(sep)
        m = re.search(r"HTTP/\S+ (\d+)", head)
        code = int(m.group(1)) if m else (200 if r.returncode == 0 else 500)
        try:
            return code, (json.loads(body) if body.strip() else {})
        except ValueError:
            return code, {"message": (r.stderr or body)[:300]}


def default_transport():
    _, tok = token_from_env()
    if tok:
        return UrllibTransport(tok)
    if shutil.which("gh"):
        return GhCliTransport()
    raise store.UsageError("error: no GHES token (export one of " + " / ".join(TOKEN_VARS) + ") and no `gh` on PATH")


def _pr_parts(pr_url: str) -> dict:
    m = _PR_URL.match(pr_url)
    if not m:
        raise store.UsageError(f"error: not a PR url: {pr_url}")
    d = m.groupdict()
    d["number"] = int(d.pop("num"))
    d["api"] = f"{api_base(d['host'])}/repos/{d['owner']}/{d['repo']}"
    return d


def _paged(tr, url: str) -> list:
    out, page = [], 1
    while True:
        code, data = tr.request("GET", f"{url}?per_page=100&page={page}")
        if code != 200:
            raise store.UsageError(f"error: GET {url} -> HTTP {code}: {data.get('message', '')}")
        out += data
        if len(data) < 100:
            return out
        page += 1


def _hunk_text(hunk: str) -> str:
    lines = (hunk or "").splitlines()[1:]          # drop the @@ header
    return "\n".join(l[1:] if l[:1] in "+- " else l for l in lines)


def fetch_review(pr_url: str, transport=None) -> dict:
    tr = transport or default_transport()
    p = _pr_parts(pr_url)
    code, pr = tr.request("GET", f"{p['api']}/pulls/{p['number']}")
    if code != 200:
        raise store.UsageError(f"error: GET pulls/{p['number']} -> HTTP {code}: {pr.get('message', '')}")
    comments = _paged(tr, f"{p['api']}/pulls/{p['number']}/comments")
    code, reviews = tr.request("GET", f"{p['api']}/pulls/{p['number']}/reviews?per_page=100")
    author = pr["user"]["login"]
    summary = next(({"author": r["user"]["login"], "created_at": r.get("submitted_at", ""), "body": r.get("body") or ""}
                    for r in (reviews if code == 200 else [])
                    if (r.get("body") or "").strip() and r["user"]["login"] != author),
                   {"author": "", "created_at": "", "body": ""})
    threads = []
    for c in (c for c in comments if not c.get("in_reply_to_id")):
        reps = [r for r in comments if r.get("in_reply_to_id") == c["id"]]
        end = c.get("line") or c.get("original_line") or 0
        start = c.get("start_line") or c.get("original_start_line") or end
        tid = f"r{c['id']}"
        threads.append({
            "id": tid, "url": c["html_url"], "path": c["path"], "start": start, "end": end,
            "diff_context": _hunk_text(c.get("diff_hunk")),
            "author": c["user"]["login"], "created_at": c["created_at"], "body": c["body"],
            "replies": [{"author": r["user"]["login"], "created_at": r["created_at"], "body": r["body"]} for r in reps],
            "resolved": False,
            "already_replied": any(render.MARK.format(tid=tid) in r["body"] for r in reps),
        })
    return {"schema": 1, "source": {"kind": "rest", "url": pr_url},
            "pr": {"host": p["host"], "owner": p["owner"], "repo": p["repo"], "number": p["number"], "url": pr_url,
                   "title": pr["title"], "head_sha": pr["head"]["sha"], "head_ref": pr["head"]["ref"],
                   "base_ref": pr["base"]["ref"]},
            "description": {"author": author, "created_at": pr["created_at"], "body": pr.get("body") or ""},
            "summary": summary, "threads": threads}


# ── publish ──
def _actions(st: store.Store, retrigger: str, reviewers: list, comment_text: str) -> list[dict]:
    rv = st.review()
    p = _pr_parts(rv["pr"]["url"])
    base = p["api"]
    acts = [{"kind": "reply", "tid": r["id"],
             "url": f"{base}/pulls/{p['number']}/comments/{r['id'][1:]}/replies", "payload": {"body": r["body"]}}
            for r in render.replies(rv, st.decisions())]
    if retrigger in ("rerequest", "both") and reviewers:
        acts.append({"kind": "rerequest", "url": f"{base}/pulls/{p['number']}/requested_reviewers",
                     "payload": {"reviewers": list(reviewers)}})
    if retrigger in ("comment", "both"):
        acts.append({"kind": "comment", "url": f"{base}/issues/{p['number']}/comments",
                     "payload": {"body": comment_text or "@dci review"}})
    return acts


def _run_actions(st: Optional[store.Store], acts: list, tr, dry_run: bool = False) -> dict:
    n = {"replies": 0, "rerequest": 0, "comment": 0}
    for a in acts:
        if dry_run:
            print(f"DRY-RUN POST {a['url']} {json.dumps(a['payload'], ensure_ascii=False)[:120]}")
            continue
        code, data = tr.request("POST", a["url"], a["payload"])
        if code not in (200, 201):
            print(f"warn: {a['kind']} -> HTTP {code}: {data.get('message', '')}")
            continue
        n["replies" if a["kind"] == "reply" else a["kind"]] += 1
        if a["kind"] == "reply" and st is not None:
            st.mark_published(a["tid"])
    return n


def publish(st: store.Store, retrigger="rerequest", reviewers=("dci",), comment_text="",
            transport=None, dry_run=False) -> dict:
    acts = _actions(st, retrigger, list(reviewers), comment_text)
    tr = transport if (transport is not None or dry_run) else default_transport()
    return _run_actions(st, acts, tr, dry_run)


def write_queue(st: store.Store, retrigger="rerequest", reviewers=("dci",), comment_text="") -> Path:
    acts = _actions(st, retrigger, list(reviewers), comment_text)
    q = st.dir / "publish-queue.json"
    q.write_text(json.dumps({"schema": 1, "store": str(st.dir), "pr": st.review()["pr"], "actions": acts},
                            ensure_ascii=False, indent=2), encoding="utf-8")
    (st.dir / "replies.md").write_text(
        "\n".join(f"### {a['tid']}\n{a['payload']['body']}\n" for a in acts if a["kind"] == "reply"), encoding="utf-8")
    return q


def run_queue(q: Path, transport=None, dry_run=False) -> int:
    data = json.loads(Path(q).read_text(encoding="utf-8"))
    st = store.Store(Path(data["store"])) if Path(data["store"], "decisions.json").is_file() else None
    tr = transport if (transport is not None or dry_run) else default_transport()
    return sum(_run_actions(st, data["actions"], tr, dry_run).values())


# ── probe-bot ──
def probe_verdict(code: int, hooks) -> dict:
    if code != 200 or hooks is None:
        return {"rerequest": "unknown", "comment": "unknown", "hooks": [],
                "note": f"GET /hooks -> HTTP {code}: repo admin token needed; keep the default "
                        "(re-request reviewer) and confirm the events in n8n"}
    active = [h for h in hooks if h.get("active")]
    ev = {e for h in active for e in h.get("events", [])}
    return {"hooks": [f"{h.get('config', {}).get('url', '?')} events={','.join(h.get('events', []))}" for h in active],
            "rerequest": "possible" if "pull_request" in ev or "*" in ev else "not-subscribed",
            "comment": "possible" if {"issue_comment", "pull_request_review_comment"} & ev or "*" in ev else "not-subscribed",
            "note": "a `pull_request` hook receives review_requested; whether n8n filters on it cannot be seen from here"}


def probe_bot(pr_url: str, transport=None) -> dict:
    tr = transport or default_transport()
    p = _pr_parts(pr_url)
    code, hooks = tr.request("GET", f"{p['api']}/hooks")
    return probe_verdict(code, hooks if code == 200 else None)


# ── CLI wiring ──
def add_subcommands(sp) -> None:
    pub = sp.add_parser("publish", help="post thread replies, then re-trigger the review bot")
    g = pub.add_mutually_exclusive_group(required=True)
    g.add_argument("--pr", help="live: PR url (needs a token or gh)")
    g.add_argument("--queue", action="store_true", help="offline: write publish-queue.json + replies.md")
    g.add_argument("--queue-file", help="execute a queue written elsewhere (on a GHES-reachable machine)")
    pub.add_argument("--retrigger", choices=["rerequest", "comment", "both", "none"], default="rerequest",
                     help="how to wake the review bot after the replies (default: re-request the reviewer)")
    pub.add_argument("--reviewers", default="dci", help="comma list (default dci)")
    pub.add_argument("--comment-text", default="@dci review", help="body for --retrigger comment|both")
    pub.add_argument("--dry-run", action="store_true")
    pub.set_defaults(fn=cmd_publish)
    pb = sp.add_parser("probe-bot", help="inspect repo webhooks to learn which re-trigger can work")
    pb.add_argument("--pr", required=True)
    pb.set_defaults(fn=cmd_probe)


def cmd_publish(a) -> int:
    reviewers = [r for r in a.reviewers.split(",") if r]
    if a.queue_file:
        print(f"{run_queue(Path(a.queue_file), dry_run=a.dry_run)} action(s) executed")
        return 0
    st = store.Store.locate(Path(a.root) if a.root else None, a.pr_number)
    if a.queue:
        q = write_queue(st, a.retrigger, reviewers, a.comment_text)
        print(f"queued -> {q}\nreplies markdown -> {st.dir / 'replies.md'}\n"
              f"run on a GHES-reachable machine: pr_review_apply.py publish --queue-file {q}")
        return 0
    n = publish(st, a.retrigger, reviewers, a.comment_text, dry_run=a.dry_run)
    print(f"replies={n['replies']} rerequest={n['rerequest']} comment={n['comment']}")
    return 0


def cmd_probe(a) -> int:
    print(json.dumps(probe_bot(a.pr), ensure_ascii=False, indent=2))
    return 0
