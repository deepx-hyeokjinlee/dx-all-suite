#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""dx-internal-pr-review-apply CLI. See README.md."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pr_review_apply import ghes, mhtml, render, store  # noqa: E402


def _store(a) -> store.Store:
    return store.Store.locate(Path(a.root) if a.root else None, a.pr_number)


def cmd_fetch(a) -> int:
    rv = mhtml.parse_file(a.mhtml) if a.mhtml else ghes.fetch_review(a.pr)
    st = store.Store.for_review(rv, Path(a.root) if a.root else None)
    st.save_review(rv)
    print(f"PR #{rv['pr']['number']}: {len(rv['threads'])} threads, "
          f"summary by {rv['summary'].get('author') or '-'} -> {st.dir}")
    return 0


def cmd_show(a) -> int:
    st = _store(a)
    print(render.show(st.review(), st.decisions(), a.pending))
    return 0


def cmd_decide(a) -> int:
    dec = "apply" if a.apply else "skip" if a.skip else "defer" if a.defer else "no-action"
    _store(a).decide(a.id, dec, a.note)
    print(f"{a.id}: {dec}")
    return 0


def cmd_commit_ref(a) -> int:
    n = _store(a).set_commit(a.sha)
    print(f"{a.sha[:8]} recorded on {n} apply decision(s)")
    return 0


def cmd_replies(a) -> int:
    st = _store(a)
    for r in render.replies(st.review(), st.decisions()):
        print(f"### {r['id']} ({r['path']})\n{r['body']}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pr_review_apply.py",
                                description="Process a bot's code review on a GHES PR: fetch, decide per thread, reply, re-request.")
    common = argparse.ArgumentParser(add_help=False)      # accepted after every subcommand
    common.add_argument("--root", help="repo root (default: walk up to .git)")
    common.add_argument("--pr-number", type=int, help="disambiguate when several review dirs exist")
    sp = p.add_subparsers(dest="cmd", required=True, parser_class=lambda **kw: argparse.ArgumentParser(parents=[common], **kw))
    f = sp.add_parser("fetch", help="read the review from a saved .mhtml or live from the GHES REST API")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--mhtml", help="PR page saved as .mhtml")
    g.add_argument("--pr", help="https://<ghes>/<owner>/<repo>/pull/<n>")
    f.set_defaults(fn=cmd_fetch)
    s = sp.add_parser("show", help="table of every thread with its decision state")
    s.add_argument("--pending", action="store_true", help="only threads without a decision")
    s.set_defaults(fn=cmd_show)
    d = sp.add_parser("decide", help="record the decision for one thread")
    d.add_argument("--id", required=True, help="thread id (r<n>) or 'summary'")
    d.add_argument("--note", required=True, help="reason / what was done — becomes the reply text")
    dg = d.add_mutually_exclusive_group(required=True)
    for opt in ("--apply", "--skip", "--defer", "--no-action"):
        dg.add_argument(opt, action="store_true")
    d.set_defaults(fn=cmd_decide)
    c = sp.add_parser("commit-ref", help="record the single commit sha on every apply decision")
    c.add_argument("--sha", required=True)
    c.set_defaults(fn=cmd_commit_ref)
    sp.add_parser("replies", help="preview the per-thread reply bodies").set_defaults(fn=cmd_replies)
    ghes.add_subcommands(sp)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        return a.fn(a)
    except store.UsageError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
