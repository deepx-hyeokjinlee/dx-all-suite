# SPDX-License-Identifier: Apache-2.0
import json
from pr_review_apply import ghes, mhtml, store


class FakeTransport:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, payload=None):
        self.calls.append((method, url, payload))
        for (m, suffix), resp in self.routes.items():
            if m == method and url.endswith(suffix):
                return resp
        return (404, {"message": "not found"})


REVIEW_COMMENTS = [
    {"id": 18833, "path": ".deepx/templates/assets/harness_bootstrap.sh", "start_line": 98, "line": 102,
     "body": "🟡 suite_url ...", "user": {"login": "dci"}, "created_at": "2026-09-17T06:19:34Z",
     "html_url": "https://gh.deepx.ai/deepx/dx-all-suite/pull/91#discussion_r18833",
     "diff_hunk": "@@ -1 +98,5 @@\n+if [ -n \"$origin\" ]; then"},
    {"id": 18850, "in_reply_to_id": 18833, "path": ".deepx/templates/assets/harness_bootstrap.sh", "line": 102,
     "body": "<!-- dx-pr-review-apply r18833 -->\n반영했습니다", "user": {"login": "dhyang"},
     "created_at": "2026-09-18T01:00:00Z", "html_url": "x"},
]


def test_fetch_review_groups_threads_and_marks_published():
    tr = FakeTransport({
        ("GET", "/pulls/91"): (200, {"title": "t", "head": {"sha": "a" * 40, "ref": "feature/x"}, "base": {"ref": "main"},
                                   "body": "desc", "user": {"login": "dhyang"}, "created_at": "2026-09-17T06:17:35Z"}),
        ("GET", "/pulls/91/comments?per_page=100&page=1"): (200, REVIEW_COMMENTS),
        ("GET", "/pulls/91/reviews?per_page=100"): (200, [{"user": {"login": "dci"}, "body": "코드 리뷰 요약 ...",
                                                            "submitted_at": "2026-09-17T06:19:34Z"}]),
    })
    rv = ghes.fetch_review("https://gh.deepx.ai/deepx/dx-all-suite/pull/91", transport=tr)
    assert rv["pr"]["head_sha"] == "a" * 40 and rv["pr"]["base_ref"] == "main"
    assert rv["summary"]["author"] == "dci"
    assert len(rv["threads"]) == 1
    t = rv["threads"][0]
    assert (t["id"], t["start"], t["end"]) == ("r18833", 98, 102)
    assert t["replies"][0]["author"] == "dhyang" and t["already_replied"] is True
    assert 'if [ -n "$origin" ]; then' in t["diff_context"]


def test_publish_live_posts_replies_then_rerequests_reviewer(tmp_path, fixture_mhtml):
    rv = mhtml.parse_file(fixture_mhtml)
    st = store.Store.for_review(rv, root=tmp_path); st.save_review(rv)
    st.decide("r18833", "apply", "n"); st.set_commit("abc1234def")
    st.decide("r18829", "skip", "s"); st.decide("r18847", "no-action", "praise")
    tr = FakeTransport({("POST", "/comments/18833/replies"): (201, {"id": 1}),
                        ("POST", "/comments/18829/replies"): (201, {"id": 2}),
                        ("POST", "/pulls/91/requested_reviewers"): (201, {})})
    n = ghes.publish(st, retrigger="rerequest", reviewers=["dci"], transport=tr)
    assert [m for m, _, _ in tr.calls] == ["POST", "POST", "POST"]
    assert tr.calls[0][1].endswith("/repos/deepx/dx-all-suite/pulls/91/comments/18829/replies")
    assert tr.calls[-1][2] == {"reviewers": ["dci"]}
    assert st.decisions()["r18833"]["published_at"] and st.decisions()["r18829"]["published_at"]
    assert "published_at" not in st.decisions()["r18847"]
    assert n == {"replies": 2, "rerequest": 1, "comment": 0}
    # idempotent: nothing left to publish
    assert ghes.publish(st, retrigger="none", reviewers=[], transport=tr) == {"replies": 0, "rerequest": 0, "comment": 0}


def test_publish_queue_writes_actions_and_markdown(tmp_path, fixture_mhtml):
    rv = mhtml.parse_file(fixture_mhtml)
    st = store.Store.for_review(rv, root=tmp_path); st.save_review(rv)
    st.decide("r18845", "apply", "import os"); st.set_commit("abc1234def")
    q = ghes.write_queue(st, retrigger="both", reviewers=["dci"], comment_text="@dci review")
    data = json.loads(q.read_text())
    assert [a["kind"] for a in data["actions"]] == ["reply", "rerequest", "comment"]
    assert data["actions"][0]["url"].endswith("/pulls/91/comments/18845/replies")
    assert (st.dir / "replies.md").read_text().startswith("### r18845")
    tr = FakeTransport({("POST", "/replies"): (201, {}), ("POST", "/requested_reviewers"): (201, {}),
                        ("POST", "/issues/91/comments"): (201, {})})
    assert ghes.run_queue(q, transport=tr) == 3
    assert st.decisions()["r18845"]["published_at"]


def test_publish_dry_run_calls_nothing(tmp_path, fixture_mhtml, capsys):
    rv = mhtml.parse_file(fixture_mhtml)
    st = store.Store.for_review(rv, root=tmp_path); st.save_review(rv); st.decide("r18845", "skip", "x")
    tr = FakeTransport({})
    n = ghes.publish(st, retrigger="rerequest", reviewers=["dci"], transport=tr, dry_run=True)
    assert tr.calls == [] and n == {"replies": 0, "rerequest": 0, "comment": 0}
    assert "DRY-RUN POST" in capsys.readouterr().out and "published_at" not in st.decisions()["r18845"]


def test_probe_bot_verdicts():
    hooks = [{"active": True, "events": ["pull_request", "issue_comment"], "config": {"url": "https://n8n.deepx.ai/webhook/x"}}]
    v = ghes.probe_verdict(200, hooks)
    assert v["rerequest"] == "possible" and v["comment"] == "possible" and "n8n" in v["hooks"][0]
    v = ghes.probe_verdict(403, None)
    assert v["rerequest"] == "unknown" and "admin" in v["note"]
    v = ghes.probe_verdict(200, [{"active": True, "events": ["pull_request"], "config": {"url": "u"}}])
    assert v["comment"] == "not-subscribed"


def test_token_chain_and_api_base(monkeypatch):
    for k in ("GHES_SYNC_DST_TOKEN", "GH_ENTERPRISE_TOKEN", "GHES_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GHES_TOKEN", "t3"); monkeypatch.setenv("GH_ENTERPRISE_TOKEN", "t2")
    assert ghes.token_from_env() == ("GH_ENTERPRISE_TOKEN", "t2")
    assert ghes.api_base("https://gh.deepx.ai") == "https://gh.deepx.ai/api/v3"
    assert ghes.api_base("https://github.com") == "https://api.github.com"
