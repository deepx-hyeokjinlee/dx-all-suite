"""원격 접근 — Host 허용 · 페어링 코드 · 세션 (QA COM-A1, 2026-10-01).

보드에서 띄운 studio 를 노트북 브라우저로 쓰는 흐름은 유지하되, 원격 요청은 인증이 있어야 한다.

- 로컬 (보드 자신 · SSH/VS Code 터널) 은 그대로.
- 원격 브라우저: launcher 콘솔에만 나오는 6자리 페어링 코드를 한 번 넣으면 세션 쿠키 (HttpOnly ·
  SameSite=Strict). 서버에는 토큰의 SHA-256 만 0600 파일로 남는다.
- API 클라이언트: DX_API_TOKEN (Authorization: Bearer · X-DX-Api-Token).
- Host: IP 주소는 허용 (DNS rebinding 은 공격자 도메인 이름으로만 일어난다), 이름은 localhost · 이 기계의
  hostname · DX_ALLOWED_HOSTS 만.

계약: tests/shared/test_remote_access.py
spec: docs/superpowers/specs/2026-10-01-studio-remote-auth-and-compile-paths-design.md (B · C)
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import secrets
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

SESSION_COOKIE = "dx_session"


# ── Host ──────────────────────────────────────────────────────────────────────

def _split_host(host_header: str) -> str:
    h = (host_header or "").strip().lower()
    if h.startswith("["):
        end = h.find("]")
        return h[1:end] if end != -1 else ""
    if h.count(":") == 1:
        h = h.split(":", 1)[0]
    return h.rstrip(".")


def host_allowed(host_header: str, hostname: Optional[str] = None) -> bool:
    host = _split_host(host_header)
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    if host == "localhost" or host.endswith(".localhost"):
        return True
    names = set()
    for n in (hostname if hostname is not None else socket.gethostname(),
              *([] if hostname is not None else [socket.getfqdn()])):
        n = (n or "").strip().lower().rstrip(".")
        if n:
            names.update({n, n + ".local"})
    for n in os.environ.get("DX_ALLOWED_HOSTS", "").split(","):
        n = n.strip().lower().rstrip(".")
        if n:
            names.add(_split_host(n))
    return host in names


# ── 페어링 코드 ────────────────────────────────────────────────────────────────

def _announce_to_console(code: str) -> None:
    print("\n  ┌──────────────────────────────────────────────────────────────┐")
    print(f"  │  Remote access code: {code}   (enter it in the remote browser) │")
    print("  │  원격 접속 코드      — 다른 PC 의 브라우저에 한 번 입력하세요   │")
    print("  └──────────────────────────────────────────────────────────────┘\n", flush=True)


class Pairing:
    """6자리 1회용 코드. 5번 틀리면 60초 잠그고 코드를 바꾼다. 성공해도 바꾼다."""

    def __init__(self, announce: Callable[[str], None] = _announce_to_console,
                 now: Callable[[], float] = time.time, max_attempts: int = 5, lock_seconds: int = 60):
        self._announce = announce
        self._now = now
        self._max = max_attempts
        self._lock_s = lock_seconds
        self._lock = threading.Lock()
        self._failures = 0
        self._locked_until = 0.0
        self.code = ""
        self._rotate()

    def _rotate(self) -> None:
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self._failures = 0
        try:
            self._announce(self.code)
        except Exception:
            pass

    def verify(self, candidate) -> str:
        with self._lock:
            if self._now() < self._locked_until:
                return "locked"
            if isinstance(candidate, str) and secrets.compare_digest(candidate.strip(), self.code):
                self._rotate()
                return "ok"
            self._failures += 1
            if self._failures >= self._max:
                self._locked_until = self._now() + self._lock_s
                self._rotate()
                return "locked"
            return "bad"


# ── 세션 ──────────────────────────────────────────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def default_sessions_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "dx-ai-studio" / "sessions.json"


class SessionStore:
    """세션 토큰의 해시만 0600 파일에 둔다. 만료 기본 30일 (DX_SESSION_DAYS)."""

    def __init__(self, path: Path, days: Optional[float] = None, now: Callable[[], float] = time.time):
        self.path = Path(path)
        if days is None:
            try:
                days = float(os.environ.get("DX_SESSION_DAYS", "30"))
            except ValueError:
                days = 30.0
        self.ttl = days * 86400
        self._now = now
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._items = {k: v for k, v in data.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            self._items = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".sessions.")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._items, f)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def create(self, user_agent: str = "", ip: str = "") -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        sid = secrets.token_hex(6)
        now = self._now()
        with self._lock:
            self._items[_hash(token)] = {"id": sid, "created": now, "last_seen": now,
                                         "user_agent": (user_agent or "")[:200], "ip": ip or ""}
            self._save()
        return token, sid

    def valid(self, token) -> Optional[dict]:
        if not isinstance(token, str) or not token:
            return None
        key = _hash(token)
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            if self._now() - float(item.get("created", 0)) > self.ttl:
                self._items.pop(key, None)
                self._save()
                return None
            item["last_seen"] = self._now()
            return dict(item)

    def revoke(self, sid: str) -> bool:
        with self._lock:
            for k, v in list(self._items.items()):
                if v.get("id") == sid:
                    self._items.pop(k)
                    self._save()
                    return True
        return False

    def revoke_token(self, token: str) -> None:
        with self._lock:
            if self._items.pop(_hash(token or ""), None) is not None:
                self._save()

    def list(self) -> list[dict]:
        now = self._now()
        with self._lock:
            return [dict(v) for v in self._items.values() if now - float(v.get("created", 0)) <= self.ttl]


class RemoteAccess:
    """launcher 가 가진 원격 접근 상태 (페어링 · 세션)."""

    def __init__(self, sessions: Optional[SessionStore] = None, pairing: Optional[Pairing] = None):
        self.sessions = sessions or SessionStore(default_sessions_file())
        self.pairing = pairing or (Pairing() if os.environ.get("DX_PAIRING", "on").lower() != "off" else None)

    @staticmethod
    def cookie_value(cookie_header: str) -> str:
        for part in (cookie_header or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == SESSION_COOKIE:
                return v
        return ""
