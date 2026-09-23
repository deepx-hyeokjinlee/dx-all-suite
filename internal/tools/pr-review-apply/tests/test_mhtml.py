# SPDX-License-Identifier: Apache-2.0
from pr_review_apply import mhtml


def test_load_returns_pr_url_and_html(fixture_mhtml):
    url, html = mhtml.load_mhtml(fixture_mhtml)
    assert url == "https://gh.deepx.ai/deepx/dx-all-suite/pull/91"
    assert "review-thread-component" in html


def test_parse_pr_meta(fixture_mhtml):
    rv = mhtml.parse_file(fixture_mhtml)
    pr = rv["pr"]
    assert (pr["host"], pr["owner"], pr["repo"], pr["number"]) == ("https://gh.deepx.ai", "deepx", "dx-all-suite", 91)
    assert pr["head_sha"] == "332131482793ceafea6da37cef9c5b2d923940de"
    assert pr["title"].startswith("ci: sync dx-all-suite feature/dx-agent-dev")
    assert rv["source"] == {"kind": "mhtml", "path": str(fixture_mhtml)}


def test_parse_ten_threads_with_path_range_id_body(fixture_mhtml):
    th = mhtml.parse_file(fixture_mhtml)["threads"]
    assert len(th) == 10
    by_id = {t["id"]: t for t in th}
    t = by_id["r18833"]
    assert t["path"] == ".deepx/templates/assets/harness_bootstrap.sh"
    assert (t["start"], t["end"]) == (98, 102)
    assert t["author"] == "dci"
    assert "suite_url" in t["body"] and "clone" in t["body"]
    assert 'suite_url="$(printf' in t["diff_context"]
    assert t["url"] == "https://gh.deepx.ai/deepx/dx-all-suite/pull/91#discussion_r18833"
    assert by_id["r18849"]["path"] == "internal/tools/ghes-sync/sync.conf"
    assert (by_id["r18849"]["start"], by_id["r18849"]["end"]) == (38, 48)
    assert all(t["resolved"] is False for t in th)


def test_summary_comment_is_the_reviewers_top_level_comment(fixture_mhtml):
    rv = mhtml.parse_file(fixture_mhtml)
    assert rv["summary"]["author"] == "dci"
    assert "코드 리뷰 요약" in rv["summary"]["body"]
    assert rv["description"]["author"] == "dhyang"
    assert "Automated sync by ghes-sync.sh" in rv["description"]["body"]


def test_html_to_text_keeps_code_fences_and_collapses_blank_lines():
    s = "<p>a</p><pre><code>x = 1\n</code></pre><p>b &amp; c</p>\n\n\n<div>d</div>"
    assert mhtml.html_to_text(s) == "a\n```\nx = 1\n```\nb & c\nd"
