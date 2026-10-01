"""JS object literal 파서 — i18n 사전을 읽기 위한 최소 구현.

사전은 `window._DX_I18N_DICT = { ... };` 형태의 JS 리터럴이라 json 으로는
못 읽는다. node 는 이 환경에 없다. 필요한 문법이 좁으므로 (문자열 키,
문자열 값, 한 단계 중첩, 후행 콤마, 줄/블록 주석) 직접 읽는다.

값의 원문 조각(source span)도 같이 돌려준다 — 마이그레이션이 기존 항목을
덮어쓰지 않고 "무엇이 다른지" 보고하려면 원문 위치가 필요하다.
"""
from __future__ import annotations


class JSParseError(ValueError):
    pass


_WS = " \t\r\n"


class _Reader:
    def __init__(self, text: str, pos: int = 0) -> None:
        self.s = text
        self.i = pos

    def skip(self) -> None:
        s, n = self.s, len(self.s)
        while self.i < n:
            c = s[self.i]
            if c in _WS:
                self.i += 1
            elif s.startswith("//", self.i):
                nl = s.find("\n", self.i)
                self.i = n if nl < 0 else nl + 1
            elif s.startswith("/*", self.i):
                end = s.find("*/", self.i + 2)
                if end < 0:
                    raise JSParseError("unterminated block comment")
                self.i = end + 2
            else:
                return

    def expect(self, ch: str) -> None:
        self.skip()
        if self.i >= len(self.s) or self.s[self.i] != ch:
            got = self.s[self.i : self.i + 20] if self.i < len(self.s) else "<eof>"
            raise JSParseError(f"expected {ch!r} at {self.i}, got {got!r}")
        self.i += 1

    def string(self) -> str:
        self.skip()
        quote = self.s[self.i]
        if quote not in "'\"":
            raise JSParseError(f"expected string at {self.i}")
        self.i += 1
        out = []
        while True:
            if self.i >= len(self.s):
                raise JSParseError("unterminated string")
            c = self.s[self.i]
            if c == "\\":
                nxt = self.s[self.i + 1]
                out.append(
                    {"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt)
                    if nxt != "u"
                    else chr(int(self.s[self.i + 2 : self.i + 6], 16))
                )
                self.i += 6 if nxt == "u" else 2
            elif c == quote:
                self.i += 1
                return "".join(out)
            else:
                out.append(c)
                self.i += 1

    def ident(self) -> str:
        self.skip()
        start = self.i
        while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] in "_$"):
            self.i += 1
        if start == self.i:
            raise JSParseError(f"expected identifier at {start}")
        return self.s[start : self.i]

    def key(self) -> str:
        self.skip()
        return self.string() if self.s[self.i] in "'\"" else self.ident()

    def value(self):
        self.skip()
        c = self.s[self.i]
        if c in "'\"":
            return self.string()
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        start = self.i
        while self.i < len(self.s) and self.s[self.i] not in ",}]":
            self.i += 1
        raw = self.s[start : self.i].strip()
        return {"true": True, "false": False, "null": None}.get(raw, raw)

    def arr(self) -> list:
        self.expect("[")
        out = []
        while True:
            self.skip()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.skip()
            if self.s[self.i] == ",":
                self.i += 1

    def obj(self) -> dict:
        self.expect("{")
        out: dict = {}
        while True:
            self.skip()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            k = self.key()
            self.expect(":")
            out[k] = self.value()
            self.skip()
            if self.s[self.i] == ",":
                self.i += 1


def parse_object_after(text: str, marker: str) -> dict:
    """`marker` 뒤에 오는 첫 object literal 을 dict 로 돌려준다."""
    at = text.find(marker)
    if at < 0:
        raise JSParseError(f"marker {marker!r} not found")
    r = _Reader(text, at + len(marker))
    r.skip()
    while r.i < len(text) and text[r.i] != "{":
        r.i += 1
    return r.obj()


def object_span(text: str, marker: str) -> tuple[int, int]:
    """`marker` 뒤 object literal 의 (시작, 끝) 인덱스. 끝은 '}' 다음."""
    at = text.find(marker)
    if at < 0:
        raise JSParseError(f"marker {marker!r} not found")
    r = _Reader(text, at + len(marker))
    r.skip()
    while r.i < len(text) and text[r.i] != "{":
        r.i += 1
    start = r.i
    r.obj()
    return start, r.i


def value_spans(text: str, marker: str) -> dict[str, dict[str, tuple[int, int]]]:
    """사전 항목마다 각 언어 값의 (시작, 끝) 인덱스 — 따옴표 포함.

    항목 하나의 값만 고쳐 쓰려면 위치가 필요하다. 전체를 다시 찍어내면
    주석과 손으로 맞춰둔 줄바꿈이 전부 날아간다.
    """
    at = text.find(marker)
    if at < 0:
        raise JSParseError(f"marker {marker!r} not found")
    r = _Reader(text, at + len(marker))
    r.skip()
    while r.i < len(text) and text[r.i] != "{":
        r.i += 1
    r.expect("{")
    out: dict[str, dict[str, tuple[int, int]]] = {}
    while True:
        r.skip()
        if r.s[r.i] == "}":
            r.i += 1
            return out
        key = r.key()
        r.expect(":")
        r.skip()
        if r.s[r.i] == "{":
            r.expect("{")
            langs: dict[str, tuple[int, int]] = {}
            while True:
                r.skip()
                if r.s[r.i] == "}":
                    r.i += 1
                    break
                lang = r.key()
                r.expect(":")
                r.skip()
                start = r.i
                r.value()
                langs[lang] = (start, r.i)
                r.skip()
                if r.s[r.i] == ",":
                    r.i += 1
            out[key] = langs
        else:
            r.value()
        r.skip()
        if r.s[r.i] == ",":
            r.i += 1
