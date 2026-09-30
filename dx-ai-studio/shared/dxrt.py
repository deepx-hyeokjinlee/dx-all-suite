"""이 PC 의 DX-RT 가 읽을 수 있는 .dxnn container (spec 2026-10-01 dx_app per-model layout 결정 5 · 6).

.dxnn 의 header 는 'DXNN' + little-endian uint32 (container 판) 다. DX-RT 3.4.2 는 6–8 을 읽고, DX Model Zoo 2_5_0
의 파일은 9 다 (teammate dx_app 043351f2 · 이 PC 에서 직접 확인: "Model file format version 9 is not supported.
Please use model file version between 6 and 8."). v9 는 DX-RT 3.5.0 이 필요하다.

- 버전은 ``dx-runtime/dx_rt/release.ver`` (예: ``v3.4.2``) 에서. 모르면 막지 않는다.
- 다운로드: 오래된 DX-RT 에서는 같은 이름의 2_4_0 (v8) 파일을 받는다. 2_4_0 에 없으면 받지 않는다.

계약: tests/dx_app/test_dxrt_container.py (studio 의 dx_app · dx_modelzoo 가 같이 쓴다)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from shared.paths import DX_RUNTIME_ROOT
from shared.dx_app_layout import container_version

NEEDS_FOR_V9 = "3.5.0"
_V9_FROM = (3, 5, 0)


def runtime_version() -> Optional[tuple]:
    try:
        text = (Path(DX_RUNTIME_ROOT) / "dx_rt" / "release.ver").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(x) for x in m.groups()) if m else None


def max_container() -> Optional[int]:
    v = runtime_version()
    if v is None:
        return None
    return 9 if v >= _V9_FROM else 8


def supports(container: Optional[int]) -> bool:
    top = max_container()
    return container is None or top is None or container <= top


def needs_for(container: Optional[int]) -> Optional[str]:
    """이 container 를 돌리려면 필요한 DX-RT (지금 것으로 되면 None)."""
    return None if supports(container) else NEEDS_FOR_V9


def needs_for_file(path) -> Optional[str]:
    return needs_for(container_version(path))


def download_urls(url: str) -> list:
    """받을 URL 을 차례로. DX-RT 가 v9 를 못 읽으면 2_5_0 대신 같은 파일의 2_4_0."""
    if url and "/2_5_0/" in url and not supports(9):
        return [url.replace("/2_5_0/", "/2_4_0/")]
    return [url]


def is_v9_only(url: str) -> bool:
    return bool(url) and "/2_5_0/" in url
