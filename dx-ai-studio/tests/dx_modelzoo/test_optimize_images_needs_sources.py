"""원본이 없으면 **소리 내어** 실패해야 한다.

`data/thumbnails` 와 `data/examples` 를 git 에서 빼기로 했다(2026-09-21 결정).
브라우저가 실제로 받는 것은 `data/optimized/` 이고 원본은 그 입력일 뿐이다.
788개 원본이 전부 최적화본을 가지고 있음을 확인한 뒤 뺐다.

그러면서 위험이 하나 생긴다: 원본이 없는 상태에서 optimize_images 를 돌리면
예전에는 **처리 0건으로 조용히 성공** 했다. 새로 clone 한 사람이 최적화본을
다시 만들려다 "아무 일도 안 일어났는데 성공" 을 보게 된다. 그 침묵이
`optimize_images.py` 의 원래 결함(출력이 있으면 무조건 스킵)과 같은 종류다.

원본을 되살리려면 dx_app 서버 + .dxnn 모델 + NPU 가 필요하다
(generate_thumbnails.py). 그 사실을 오류 메시지가 말해야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PIL")

from dx_modelzoo.scripts.optimize_images import optimize_images  # noqa: E402


def test_a_missing_source_root_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        optimize_images(tmp_path / "does-not-exist", tmp_path / "out", write=True)
    assert "generate_thumbnails" in str(e.value), "되살리는 방법을 말해야 한다"


def test_an_empty_source_root_is_an_error(tmp_path):
    """디렉터리는 있는데 이미지가 없는 경우 — gitignore 후 새 clone 의 모습이다."""
    (tmp_path / "src").mkdir()
    with pytest.raises(FileNotFoundError):
        optimize_images(tmp_path / "src", tmp_path / "out", write=True)


def test_a_dry_run_still_reports_the_problem(tmp_path):
    """--write 없이 확인만 하려는 사람도 같은 사실을 알아야 한다."""
    (tmp_path / "src").mkdir()
    with pytest.raises(FileNotFoundError):
        optimize_images(tmp_path / "src", tmp_path / "out", write=False)


def test_sources_present_still_work(tmp_path):
    from PIL import Image

    src = tmp_path / "src" / "thumbnails"
    src.mkdir(parents=True)
    Image.new("RGB", (40, 30), (1, 2, 3)).save(src / "a.jpg")
    report = optimize_images(tmp_path / "src", tmp_path / "out", write=True)
    assert report["written"] == 1
