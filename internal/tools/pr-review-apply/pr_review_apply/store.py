# SPDX-License-Identifier: Apache-2.0
"""`.dx-pr-review/<owner>-<repo>-<n>/` — review.json (parsed review), decisions.json (human
decisions), publish-queue.json (deferred publish). `root` is the repo root (walk up to `.git`)."""
from __future__ import annotations
import datetime as _dt
import json
from pathlib import Path
from typing import Optional

DECISIONS = ("apply", "skip", "defer", "no-action")


class UsageError(Exception):
    """User-facing error -> exit 2 in the CLI."""


def find_root(start: Optional[Path] = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in (cur, *cur.parents):
        if (p / ".git").exists():
            return p
    return cur


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Store:
    def __init__(self, d: Path):
        self.dir = d

    @classmethod
    def for_review(cls, review: dict, root: Optional[Path] = None) -> "Store":
        pr = review["pr"]
        return cls(find_root(root) / ".dx-pr-review" / f"{pr['owner']}-{pr['repo']}-{pr['number']}")

    @classmethod
    def locate(cls, root: Optional[Path] = None, pr_number: Optional[int] = None) -> "Store":
        base = find_root(root) / ".dx-pr-review"
        dirs = (sorted(p for p in base.iterdir() if p.is_dir() and (p / "review.json").is_file())
                if base.is_dir() else [])
        if pr_number is not None:
            dirs = [p for p in dirs if p.name.endswith(f"-{pr_number}")]
        if len(dirs) != 1:
            raise UsageError(f"error: expected exactly one review dir under {base} (found {len(dirs)}); "
                             "run `fetch` first or pass --pr-number")
        return cls(dirs[0])

    def save_review(self, review: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    def review(self) -> dict:
        return json.loads((self.dir / "review.json").read_text(encoding="utf-8"))

    def decisions(self) -> dict:
        p = self.dir / "decisions.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

    def _write_decisions(self, d: dict) -> None:
        (self.dir / "decisions.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def decide(self, tid: str, decision: str, note: str) -> None:
        if decision not in DECISIONS:
            raise ValueError(decision)
        ids = {t["id"] for t in self.review()["threads"]} | {"summary"}
        if tid not in ids:
            raise UsageError(f"error: unknown thread id {tid!r} (known: {', '.join(sorted(ids))})")
        d = self.decisions()
        prev = d.get(tid, {})
        d[tid] = {"decision": decision, "note": note, "decided_at": _now()}
        if "commit" in prev:
            d[tid]["commit"] = prev["commit"]
        self._write_decisions(d)

    def set_commit(self, sha: str) -> int:
        d = self.decisions()
        n = 0
        for v in d.values():
            if v["decision"] == "apply":
                v["commit"] = sha
                n += 1
        self._write_decisions(d)
        return n

    def mark_published(self, tid: str) -> None:
        d = self.decisions()
        d.setdefault(tid, {})["published_at"] = _now()
        self._write_decisions(d)
