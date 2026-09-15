"""공개 ModelZoo 페이로드 리더 — 구현은 `shared/modelzoo_payload.py` 에 있다.

dx_app 의 SETUP 카탈로그도 같은 페이로드를 읽는다. 두 모듈은 각자 자기 포트에서
도는 독립 서버라 서로 import 하지 않으므로, 티어·필드 지식은 공유 자리인
`shared/` 에 한 벌만 둔다. 여기 남은 것은 기존 import 경로를 지키는 위임이다.
"""
from shared.modelzoo_payload import (  # noqa: F401
    parse_public_modelzoo_html,
    parse_public_payload,
)

__all__ = ["parse_public_modelzoo_html", "parse_public_payload"]
