# SPDX-License-Identifier: Apache-2.0
import subprocess, sys
from conftest import CLI


def run(*args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, text=True, capture_output=True)


def test_fetch_show_decide_replies_roundtrip(tmp_path, fixture_mhtml):
    r = run("fetch", "--mhtml", str(fixture_mhtml), "--root", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "10 threads" in r.stdout
    d = tmp_path / ".dx-pr-review" / "deepx-dx-all-suite-91"
    assert (d / "review.json").is_file()
    r = run("decide", "--id", "r18833", "--apply", "--note", "n", "--root", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    r = run("commit-ref", "--sha", "abc1234def", "--root", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0
    r = run("replies", "--root", str(tmp_path), cwd=tmp_path)
    assert "r18833" in r.stdout and "abc1234d" in r.stdout
    r = run("show", "--pending", "--root", str(tmp_path), cwd=tmp_path)
    assert "r18833" not in r.stdout and "r18829" in r.stdout


def test_decide_unknown_id_fails(tmp_path, fixture_mhtml):
    run("fetch", "--mhtml", str(fixture_mhtml), "--root", str(tmp_path), cwd=tmp_path)
    r = run("decide", "--id", "r1", "--skip", "--note", "n", "--root", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 2 and "unknown thread id" in r.stderr


def test_store_picks_the_single_review_dir_when_only_one_exists(tmp_path, fixture_mhtml):
    run("fetch", "--mhtml", str(fixture_mhtml), "--root", str(tmp_path), cwd=tmp_path)
    r = run("show", "--root", str(tmp_path), cwd=tmp_path)          # no --pr needed
    assert r.returncode == 0 and "r18833" in r.stdout
