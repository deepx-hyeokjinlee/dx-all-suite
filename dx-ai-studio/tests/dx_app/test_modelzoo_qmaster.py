"""Q-Master 티어가 표시에서 끝나지 않고 설치 경로까지 간다.

1단계가 ModelZoo 화면에 Q-Master 를 그리게 만들었는데, dx_app 쪽 다운로더에는
`qmaster` 문자열이 한 번도 없었다 — 보이지만 받을 수 없는 상태였다.

설치 위치는 Q-Pro 의 규칙을 따라 assets/models/q-master/ 다.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _mz():
    import dx_app.core.modelzoo as mz

    return mz


def test_qmaster_has_its_own_install_dir():
    mz = _mz()
    assert mz.QMASTER_DIR.name == "q-master"
    assert mz.QMASTER_DIR.parent == mz.MODELS_DIR


def test_every_tier_is_in_the_chip_table():
    """세 곳의 이진 분기를 표 하나로 모았다 — 표가 진실의 출처다."""
    mz = _mz()
    assert set(mz._CHIP_DIRS) == {"qlite", "qpro", "qmaster"}
    assert mz._CHIP_DIRS["qlite"] == (mz.MODELS_DIR, "assets/models")
    assert mz._CHIP_DIRS["qpro"] == (mz.QPRO_DIR, "assets/models/q-pro")
    assert mz._CHIP_DIRS["qmaster"] == (mz.QMASTER_DIR, "assets/models/q-master")


def test_download_sends_qmaster_to_its_own_dir():
    """task 조립은 스레드를 띄우지 않는 순수 함수라 그대로 검사한다."""
    mz = _mz()
    tasks = mz._build_tasks([{
        "name": "RepVGG-A0",
        "chip": "qmaster",
        "dxnn_url": "https://sdk.deepx.ai/modelzoo/q-master-dxnn/2_4_0/repvgga0_224x224.dxnn",
        "json_url": "https://sdk.deepx.ai/modelzoo/q-master-json/2_4_0/repvgga0_224x224.json",
    }])
    assert len(tasks) == 2, tasks
    for task in tasks:
        assert task["chip"] == "qmaster"
        assert task["dest"].parent == mz.QMASTER_DIR, task["dest"]


def test_each_tier_lands_in_its_own_directory():
    mz = _mz()
    for chip, (dest_dir, _rel) in mz._CHIP_DIRS.items():
        tasks = mz._build_tasks([{
            "name": "m", "chip": chip,
            "dxnn_url": "https://sdk.deepx.ai/x/m.dxnn", "json_url": None,
        }])
        assert tasks[0]["dest"].parent == dest_dir, chip


def test_unknown_chip_is_rejected_rather_than_silently_qpro():
    """else 가 기본값이던 시절엔 오타난 chip 이 전부 q-pro 로 갔다."""
    mz = _mz()
    with pytest.raises(ValueError, match="unknown chip"):
        mz._build_tasks([{
            "name": "typo", "chip": "qmater",
            "dxnn_url": "https://sdk.deepx.ai/x/a.dxnn", "json_url": None,
        }])

    res = mz.modelzoo_download([{
        "name": "typo", "chip": "qmater",
        "dxnn_url": "https://sdk.deepx.ai/x/a.dxnn", "json_url": None,
    }])
    assert not res["ok"], "모르는 chip 을 받아들였다"
    assert "chip" in (res.get("error") or "").lower()


def test_refresh_exists_checks_the_qmaster_dir(tmp_path, monkeypatch):
    mz = _mz()
    qm = tmp_path / "q-master"
    qm.mkdir()
    (qm / "repvgga0_224x224.dxnn").write_bytes(b"x")
    monkeypatch.setattr(mz, "QMASTER_DIR", qm)
    monkeypatch.setitem(mz._CHIP_DIRS, "qmaster", (qm, "assets/models/q-master"))

    models = [{
        "name": "RepVGG-A0",
        "qlite": {"dxnn_url": None},
        "qpro": {"dxnn_url": None},
        "qmaster": {
            "dxnn_url": "https://sdk.deepx.ai/x/repvgga0_224x224.dxnn",
            "exists": False,
        },
    }]
    mz._refresh_exists(models)
    assert models[0]["qmaster"]["exists"] is True


def test_auto_register_uses_the_qmaster_relative_path():
    """레지스트리에 적히는 경로가 실제 설치 위치와 같아야 한다."""
    mz = _mz()
    src = Path(mz.__file__).read_text(encoding="utf-8")
    assert 'assets/models/q-master' not in src.replace('"assets/models/q-master"', ''), (
        "q-master 경로가 _CHIP_DIRS 밖에 하드코딩돼 있다"
    )
