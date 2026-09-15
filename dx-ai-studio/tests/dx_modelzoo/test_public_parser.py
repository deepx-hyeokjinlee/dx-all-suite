"""공개 ModelZoo 어댑터 계약.

이 파일은 원래 서버 렌더 HTML 테이블 파서를 검증했다 — 3행 그룹 헤더, 셀의
href 추출, 모델이 아닌 테이블 건너뛰기 같은 것들. 페이지가 리팩토링되면서 그
테이블이 사라졌으므로 그 검증들은 존재하지 않는 구조를 지키고 있었다. 파싱
자체의 계약은 tests/dx_modelzoo/test_public_payload_parser.py 로 옮겼다(실제
페이로드 고정본으로 검증한다).

여기 남는 것은 **파싱 방식과 무관한 어댑터 계약**이다: 주입된 fetch 를 쓰는가,
네트워크가 죽으면 실패를 보고하는가. 이 둘은 페이지가 또 바뀌어도 유효하다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from dx_modelzoo.metadata.adapters import public_modelzoo_adapter

_FIXTURE = (Path(__file__).parent / "fixtures" / "public_modelzoo_payload.html").read_text(
    encoding="utf-8"
)


class TestPublicModelZooAdapter(unittest.TestCase):
    def test_adapter_uses_injected_fetch(self):
        r = public_modelzoo_adapter(".", fetch_text=lambda url: _FIXTURE)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(len(r["models"]), 8)

    def test_adapter_handles_fetch_failure(self):
        def boom(url):
            raise RuntimeError("network down")

        r = public_modelzoo_adapter(".", fetch_text=boom)
        self.assertFalse(r["ok"])
        self.assertTrue(r["errors"])

    def test_adapter_reports_a_shape_change_as_failure(self):
        """페이지 구조가 바뀌면 빈 카탈로그를 내놓지 말고 실패로 보고해야 한다.

        조용한 부분 성공이 가장 위험하다 — 모델 수가 줄어든 카탈로그는 눈으로
        구분되지 않은 채 merge 를 통과한다.
        """
        r = public_modelzoo_adapter(".", fetch_text=lambda url: "<html>no payload</html>")
        self.assertFalse(r["ok"])
        self.assertTrue(any("__MODEL_ZOO_DATA__" in e for e in r["errors"]), r["errors"])


if __name__ == "__main__":
    unittest.main()
