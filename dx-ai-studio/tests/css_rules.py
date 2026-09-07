"""CSS rule 본문 추출 — 계약 테스트들이 공유한다.

네 개 테스트 파일이 같은 헬퍼를 각자 복제하고 있었고, 그래서 셸이 그룹
셀렉터를 쓰기 시작했을 때 네 곳이 동시에 깨졌다. CSS 중복을 없애는 작업을
하면서 테스트 헬퍼는 네 벌이었던 셈이라, 여기로 합친다.
"""
from __future__ import annotations

import re

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# 셀렉터에는 < 나 ; 가 없다. 그 둘을 막아야 HTML 안의 <style> 앞부분을
# 셀렉터로 삼키지 않는다 (> 는 자식 결합자라 허용). at-rule 의 여는 블록도 건너뛴다.
_RULE = re.compile(r"(?m)^[ \t]*([^{}@\n<;][^{}<;]*?)\{([^{}]*)\}")


def iter_rules(css: str):
    """(셀렉터 목록, 본문) 쌍을 문서 순서대로 돌려준다."""
    for m in _RULE.finditer(_COMMENT.sub(" ", css)):
        yield [n.strip() for n in m.group(1).split(",")], m.group(2)


def css_rule(css: str, selector: str) -> str:
    """첫 번째로 만나는 rule 의 본문.

    그룹 셀렉터도 정의로 인정한다 — 공유 계층이 같은 규칙에 두 이름을 묶어
    두기 때문이다 (.dx-shell-header-right, .toolbar).
    """
    for names, body in iter_rules(css):
        if selector in names:
            return body
    raise AssertionError(f"selector {selector!r} not found in CSS")


def css_rule_last(css: str, selector: str) -> str:
    """마지막 rule 의 본문 — 뒤에서 덮어쓰는 정의까지 보려면 이쪽을 쓴다."""
    found = None
    for names, body in iter_rules(css):
        if selector in names:
            found = body
    if found is None:
        raise AssertionError(f"selector {selector!r} not found in CSS")
    return found


def defines(css: str, selector: str) -> bool:
    """그 셀렉터를 정의하는 rule 이 있는가."""
    return any(selector in names for names, _ in iter_rules(css))
