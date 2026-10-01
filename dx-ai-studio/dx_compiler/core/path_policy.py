"""compile 경로 정책 — 허용된 폴더 안의 실제 파일 · 폴더만 (QA COM-A2, 2026-10-01).

`/compile` · `/compile/resume` · `/config/generate` 와 compiler_service.submit · submit_resume 가 받는 경로
(model_path · config_path · qxnn_path · dataset_path · output_dir) 를 실행 전에 본다.

- 허용 루트: suite root · studio `var/` · 사용자 홈 · `/media` · `/mnt` + ``DX_COMPILER_ALLOWED_ROOTS``
  (``os.pathsep`` 구분). 모두 resolve 해서 비교한다.
- 포함 여부는 resolve 한 실제 경로의 **구성요소** 로 본다 (``Path.relative_to``) — ``/ws-evil`` 은 ``/ws``
  아래가 아니다. symlink 는 resolve 로 실제 위치를 보므로 밖을 가리키면 거부된다.
- 거부 메시지에 서버 경로를 넣지 않는다.

2026-09-18 에는 "서버를 localhost 밖에 노출하지 않는다" 는 전제로 compile 경로에 검사를 걸지 않기로 했다
(config.is_safe_path 주석 · 그날의 spec R1). 기본 bind 가 모든 인터페이스라 전제가 성립하지 않아 철회한다.

계약: tests/dx_compiler/test_path_policy.py
spec: docs/superpowers/specs/2026-10-01-studio-remote-auth-and-compile-paths-design.md (D)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from shared.paths import STUDIO_ROOT, SUITE_ROOT


class PathPolicyError(ValueError):
    """경로가 정책 밖 — HTTP 400 으로 돌려준다."""


def _default_roots() -> list[Path]:
    roots = [SUITE_ROOT, STUDIO_ROOT / "var", Path.home(), Path("/media"), Path("/mnt")]
    return [r for r in roots if str(r)]


def _jobs_root() -> Path:
    return STUDIO_ROOT / "var" / "compiler" / "jobs"


def allowed_roots() -> list[Path]:
    extra = [Path(p) for p in os.environ.get("DX_COMPILER_ALLOWED_ROOTS", "").split(os.pathsep) if p.strip()]
    out = []
    for r in [*_default_roots(), *extra]:
        try:
            out.append(r.resolve())
        except (OSError, RuntimeError):
            continue
    return out


def _inside(path: Path, roots: Iterable[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _text(raw, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise PathPolicyError(f"{field} is required")
    if "\x00" in raw:
        raise PathPolicyError(f"{field} is not a valid path")
    return raw.strip()


def check_input_file(raw, field: str) -> Path:
    """존재하는 일반 파일이고 허용 루트 안 — resolve 한 경로를 돌려준다."""
    try:
        p = Path(_text(raw, field)).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise PathPolicyError(f"{field} does not exist") from None
    if not _inside(p, allowed_roots()):
        raise PathPolicyError(f"{field} is outside the allowed folders")
    if not p.is_file():
        raise PathPolicyError(f"{field} is not a file")
    return p


def check_input_dir(raw, field: str) -> Path:
    """존재하는 디렉터리이고 허용 루트 안 (dataset_path)."""
    try:
        p = Path(_text(raw, field)).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise PathPolicyError(f"{field} does not exist") from None
    if not _inside(p, allowed_roots()):
        raise PathPolicyError(f"{field} is outside the allowed folders")
    if not p.is_dir():
        raise PathPolicyError(f"{field} is not a folder")
    return p


def check_output_dir(raw, field: str = "output_dir") -> Path:
    """쓸 폴더 — 아직 없으면 가장 가까운 존재하는 부모를 resolve 해서 본다. 만들지는 않는다."""
    p = Path(_text(raw, field)).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    tail: list[str] = []
    cur = p
    while not cur.exists():
        if cur.parent == cur:
            raise PathPolicyError(f"{field} is not a valid path")
        tail.append(cur.name)
        cur = cur.parent
    try:
        base = cur.resolve(strict=True)
    except (OSError, RuntimeError):
        raise PathPolicyError(f"{field} is not a valid path") from None
    if not base.is_dir():
        raise PathPolicyError(f"{field} is not a folder")
    if any(part in ("..", ".") for part in tail):
        raise PathPolicyError(f"{field} is not a valid path")
    resolved = base.joinpath(*reversed(tail))
    roots = allowed_roots()
    if not _inside(base, roots) or not _inside(resolved, roots):
        raise PathPolicyError(f"{field} is outside the allowed folders")
    # compiler 가 작업마다 만드는 내부 폴더 (다른 작업의 산출물) 는 출력 위치가 아니다
    try:
        if _inside(resolved, [_jobs_root().resolve()]):
            raise PathPolicyError(f"{field} cannot be a compiler job folder")
    except (OSError, RuntimeError):
        pass
    return resolved


def would_overwrite_input(destination: Path, inputs: Iterable[str]) -> bool:
    """게시할 산출물이 입력 파일 자리인가 (resolve 해서 비교)."""
    try:
        dest = Path(destination).resolve()
    except (OSError, RuntimeError):
        return True
    for raw in inputs:
        if not raw:
            continue
        try:
            if Path(raw).resolve() == dest:
                return True
        except (OSError, RuntimeError):
            continue
    return False
