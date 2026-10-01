"""공개 ModelZoo 페이로드 파서는 `shared/` 에 한 벌만 있다.

dx_modelzoo 는 카탈로그를 채우려고, dx_app 은 SETUP 페이지의 다운로드 목록을
만들려고 같은 페이로드를 읽는다. 두 모듈은 서로 import 하지 않으므로 이 지식이
한쪽에 있으면 다른 쪽이 베껴야 하고, 그러면 공개 페이지가 다시 바뀔 때 한쪽만
고쳐진다 — 실제로 그 페이지는 2026-09 에 테이블에서 인라인 JSON 으로 한 번
바뀌었다.

여기서 지키는 것은 "위임이 껍데기가 아니다" 다. `dx_modelzoo` 쪽 경로로 부르든
`shared` 쪽 경로로 부르든 같은 객체여야 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "dx_modelzoo"
    / "fixtures"
    / "public_modelzoo_payload.html"
)


def _html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_shared_module_is_the_implementation():
    from shared import modelzoo_payload

    assert hasattr(modelzoo_payload, "parse_public_payload")
    assert hasattr(modelzoo_payload, "parse_public_modelzoo_html")


def test_dx_modelzoo_path_carries_no_implementation_of_its_own():
    """위임 파일에 파싱 로직이 다시 들어가면 두 벌이 된다.

    객체 동일성(`is`)으로는 이걸 못 잡는다 — tests/shared/conftest.py 가
    `shared/` 자체를 sys.path 에 올리므로 같은 파일이 `shared.modelzoo_payload`
    와 `modelzoo_payload` 두 모듈 객체로 존재할 수 있고, 그러면 함수 객체도
    서로 다르다. 파서가 상태 없는 순수 함수라 그 자체는 해롭지 않지만,
    동일성은 이 저장소가 보장하는 성질이 아니다.

    그래서 실제로 지켜야 할 것을 본다: 위임 파일은 재수출뿐이어야 한다.
    """
    from dx_modelzoo.metadata import _public_parser

    src = Path(_public_parser.__file__).read_text(encoding="utf-8")
    body = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    assert "from shared.modelzoo_payload import" in body, "공유 구현을 가져오지 않는다"
    for smell in ("json.loads", "def parse_public_payload", "__MODEL_ZOO_DATA__"):
        assert smell not in body, (
            f"위임 파일에 구현이 돌아왔다 ({smell!r}) — 지식이 두 벌이 된다"
        )


def test_both_import_paths_agree():
    """어느 경로로 부르든 같은 결과가 나와야 한다."""
    from dx_modelzoo.metadata import _public_parser
    from shared import modelzoo_payload

    html = _html()
    assert _public_parser.parse_public_payload(html) == modelzoo_payload.parse_public_payload(html)


def test_payload_carries_all_four_tiers():
    """Q-Master 까지 읽는다 — dx_app 의 설치 흐름이 이 값에 기댄다."""
    from shared.modelzoo_payload import parse_public_payload

    rows = parse_public_payload(_html())
    assert rows, "픽스처에서 한 건도 못 읽었다"

    artifact_keys = set()
    for row in rows:
        artifact_keys |= set(row.get("artifacts", {}))
    for tier in ("qlite_dxnn", "qpro_dxnn", "qmaster_dxnn"):
        assert tier in artifact_keys, f"{tier} 를 아무 행에서도 못 찾았다"


def test_missing_global_raises_rather_than_returning_a_thin_catalog():
    from shared.modelzoo_payload import parse_public_payload

    with pytest.raises(ValueError):
        parse_public_payload("<html><body><table><tr><th>Name</th></tr></table></body></html>")
