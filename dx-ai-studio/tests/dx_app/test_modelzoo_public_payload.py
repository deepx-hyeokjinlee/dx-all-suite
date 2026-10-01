"""SETUP 페이지의 public 소스는 테이블이 아니라 페이로드를 읽는다.

`developer.deepx.ai/modelzoo/` 는 2026-09 에 리팩토링되면서 데이터 행을 잃었다 —
실제 응답에 `<table>` 은 1개, `<tr>` 은 2개(헤더 뼈대)뿐이고 모델은
`window.__MODEL_ZOO_DATA__` 안에 있다. 그래서 이 소스로는 테이블 파서가
20칼럼 판정에 실패하고 legacy 분기로 떨어져 0건을 돌려준다.

여기서 지키는 것은 "public 소스가 페이로드를 본다" 와 "네 번째 티어가
설치 흐름까지 도달한다" 두 가지다.
"""
from __future__ import annotations

from pathlib import Path

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "dx_modelzoo"
    / "fixtures"
    / "public_modelzoo_payload.html"
)


def _models():
    from dx_app.core.modelzoo import _models_from_payload

    return _models_from_payload(FIXTURE.read_text(encoding="utf-8"))


def test_payload_yields_every_row():
    models = _models()
    assert len(models) == 8, f"픽스처 8행 중 {len(models)}건만 읽었다"


def test_each_model_carries_the_shape_dx_app_consumes():
    for m in _models():
        assert m["name"]
        assert "task" in m
        for tier in ("qlite", "qpro", "qmaster"):
            assert tier in m, f"{m['name']} 에 {tier} 블록이 없다"
            assert "dxnn_url" in m[tier]
            assert "exists" in m[tier]


def test_artifact_urls_are_absolute():
    """페이로드의 아티팩트 경로는 base 기준 상대다 — 다운로더는 절대 URL 이 필요하다."""
    seen = 0
    for m in _models():
        for tier in ("qlite", "qpro", "qmaster"):
            url = m[tier].get("dxnn_url")
            if url:
                assert url.startswith("http"), f"{m['name']}/{tier} 이 상대 경로다: {url}"
                seen += 1
    assert seen, "절대 URL 을 하나도 못 봤다"


def test_qmaster_is_none_where_the_source_has_none():
    """354개 중 15개만 Q-Master 다. 없는 걸 있다고 하면 다운로드가 404 로 죽는다."""
    models = _models()
    with_qm = [m for m in models if m["qmaster"].get("dxnn_url")]
    without_qm = [m for m in models if not m["qmaster"].get("dxnn_url")]
    assert with_qm, "픽스처에 Q-Master 가 있는 행이 있어야 한다"
    assert without_qm, "픽스처에 Q-Master 가 없는 행도 있어야 한다"
    for m in without_qm:
        assert m["qmaster"]["dxnn_url"] is None


def test_list_routes_public_source_to_the_payload_reader(monkeypatch):
    """modelzoo_list(source='public') 가 테이블 파서로 가면 0건이 된다."""
    import dx_app.core.modelzoo as mz

    monkeypatch.setattr(mz, "_fetch_page", lambda source: (FIXTURE.read_text(encoding="utf-8"), None))
    mz._cache.update({"models": [], "source": None, "ts": 0})

    result = mz.modelzoo_list(source=mz.SOURCE_PUBLIC)
    assert result["ok"], result.get("error")
    assert len(result["models"]) == 8
