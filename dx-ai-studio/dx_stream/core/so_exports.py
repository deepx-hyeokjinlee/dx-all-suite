"""후처리 라이브러리 (.so) 가 내보내는 함수 이름 — 파이프라인 빌더의 function-name 목록용.

DxPostprocess 의 function-name 은 라이브러리마다 다르다 (libpostprocess_ppu.so 는 YOLOV5S_PPU ·
SCRFD500M_PPU …, 나머지는 PostProcess). 예전에는 목록이 PostProcess 하나뿐이라 PPU demo 의 함수를
고를 수 없었다 (release audit S-18). binutils (nm) 가 없는 보드도 있어 ELF .dynsym 을 직접 읽는다.
"""
from __future__ import annotations

import struct
from functools import lru_cache
from pathlib import Path

_SHT_DYNSYM = 11
_STT_FUNC = 2
_STB_GLOBAL, _STB_WEAK = 1, 2


def exported_functions(path: str | Path) -> list[str]:
    """정의된 전역 함수 이름. 밑줄로 시작하는 내부 심볼은 뺀다. 읽지 못하면 []."""
    p = Path(path)
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return []
    return list(_read(str(p), mtime))


@lru_cache(maxsize=64)
def _read(path: str, _mtime: int) -> tuple[str, ...]:
    try:
        data = Path(path).read_bytes()
        if data[:4] != b"\x7fELF" or data[4] != 2:  # ELF64 만
            return ()
        end = "<" if data[5] == 1 else ">"
        (shoff,) = struct.unpack_from(end + "Q", data, 0x28)
        shentsize, shnum = struct.unpack_from(end + "HH", data, 0x3A)
        secs = [struct.unpack_from(end + "IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
        names = set()
        for sec in secs:
            if sec[1] != _SHT_DYNSYM:
                continue
            stroff = secs[sec[6]][4]
            for off in range(sec[4], sec[4] + sec[5], 24):
                st_name, st_info, _other, st_shndx = struct.unpack_from(end + "IBBH", data, off)
                if (st_info & 0xF) != _STT_FUNC or (st_info >> 4) not in (_STB_GLOBAL, _STB_WEAK) or st_shndx == 0:
                    continue
                start = stroff + st_name
                name = data[start:data.index(b"\0", start)].decode("ascii", "replace")
                if name and not name.startswith("_"):
                    names.add(name)
        return tuple(sorted(names))
    except (struct.error, ValueError, IndexError):
        return ()
