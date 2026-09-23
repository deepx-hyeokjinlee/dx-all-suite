# SPDX-License-Identifier: Apache-2.0
import json
from pr_review_apply import mhtml, store, render


def _rv(fixture_mhtml):
    return mhtml.parse_file(fixture_mhtml)


def test_store_dir_is_owner_repo_number_under_root(tmp_path, fixture_mhtml):
    st = store.Store.for_review(_rv(fixture_mhtml), root=tmp_path)
    assert st.dir == tmp_path / ".dx-pr-review" / "deepx-dx-all-suite-91"
    st.save_review(_rv(fixture_mhtml))
    assert json.loads((st.dir / "review.json").read_text())["pr"]["number"] == 91
    assert st.decisions() == {}


def test_decide_and_commit_ref(tmp_path, fixture_mhtml):
    st = store.Store.for_review(_rv(fixture_mhtml), root=tmp_path)
    st.save_review(_rv(fixture_mhtml))
    st.decide("r18833", "apply", "sed 실패 시 로그 추가")
    st.decide("r18847", "no-action", "칭찬")
    st.set_commit("abc1234def")
    d = st.decisions()
    assert d["r18833"]["decision"] == "apply" and d["r18833"]["commit"] == "abc1234def"
    assert "commit" not in d["r18847"]
    assert d["r18833"]["decided_at"].endswith("Z")


def test_replies_only_for_apply_skip_defer(tmp_path, fixture_mhtml):
    rv = _rv(fixture_mhtml)
    st = store.Store.for_review(rv, root=tmp_path); st.save_review(rv)
    st.decide("r18833", "apply", "변환 실패를 명시적으로 처리"); st.set_commit("abc1234def")
    st.decide("r18829", "skip", "도구 출력이 의도적으로 한국어")
    st.decide("r18845", "defer", "후속 정리")
    st.decide("r18847", "no-action", "칭찬")
    rs = render.replies(rv, st.decisions())
    assert [r["id"] for r in rs] == ["r18829", "r18833", "r18845"]           # thread order
    a = next(r for r in rs if r["id"] == "r18833")["body"]
    assert a.startswith("<!-- dx-pr-review-apply r18833 -->")
    assert "반영했습니다" in a and "`abc1234d`" in a and "harness_bootstrap.sh:98-102" in a
    assert "반영하지 않았습니다" in next(r for r in rs if r["id"] == "r18829")["body"]
    assert "보류" in next(r for r in rs if r["id"] == "r18845")["body"]


def test_show_table_lists_every_thread_with_state(tmp_path, fixture_mhtml):
    rv = _rv(fixture_mhtml)
    st = store.Store.for_review(rv, root=tmp_path); st.save_review(rv); st.decide("r18833", "apply", "x")
    txt = render.show(rv, st.decisions())
    assert txt.count("\n") >= 12 and "r18833" in txt and "apply" in txt and "pending" in txt
    assert "dci" in txt and "코드 리뷰 요약" in txt

