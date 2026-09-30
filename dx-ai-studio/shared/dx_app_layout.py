"""dx_app 예제 layout — 경로를 만드는 곳은 여기 하나 (spec 2026-10-01 dx_app per-model layout).

dx_app 은 두 모양으로 온다:

- **legacy** (main ``01b7727``): ``src/<lang>_example/<task>/<model>/<model>_<variant>.{py,cpp}``
- **per_model** (``deepx-yjlee/dx_app`` ``feat/per-model-example-dirs`` ``8d0b748``, 곧 staging):
  ``src/<lang>_example/<task>/<family>/<stem>/<stem>_<variant>.{py,cpp}`` — stem 은 ``.dxnn`` 이름이고
  registry 의 ``variant``. 옛 경로 shim 은 없다.

어느 쪽이든 C++ binary 는 ``<build>/<name>_<variant>`` (name = legacy 의 model, per_model 의 stem) 라서
달라지는 것은 **예제 폴더** 뿐이다. 그래서 호출부는 (task, name) 만 들고 여기서 폴더를 찾는다.

모델 파일은 ``assets/models`` 다음에 suite 의 ``workspace/res/models`` 에서도 찾는다 (branch 의 run_demo.sh ·
run_demo.py 와 같은 순서). 0 byte 파일은 받다 만 것이라 없는 것으로 친다.

계약: tests/dx_app/test_layout.py
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

LEGACY = "legacy"
PER_MODEL = "per_model"
LANGS = ("python", "cpp")
_SKIP = {"common", "build", "sample", "__pycache__", "utils", "factory"}
_SUFFIX = {"python": ".py", "cpp": ".cpp"}


@dataclass(frozen=True)
class Example:
    task: str
    name: str                      # legacy: model dir · per_model: stem (= .dxnn 이름)
    family: Optional[str] = None   # per_model 만
    py_dir: Optional[Path] = None
    cpp_dir: Optional[Path] = None

    def dir(self, lang: str) -> Optional[Path]:
        return self.py_dir if lang == "python" else self.cpp_dir


def _base(root: Path, lang: str) -> Path:
    return Path(root) / "src" / f"{lang}_example"


def _is_example_dir(d: Path, lang: str) -> bool:
    suf = _SUFFIX[lang]
    return any((d / f"{d.name}_{v}{suf}").is_file() for v in ("sync", "async"))


@lru_cache(maxsize=8)
def _detect(root: str) -> str:
    reg = Path(root) / "config" / "model_registry.json"
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
        if any(isinstance(r, dict) and r.get("variant") and r.get("family") for r in rows[:50]):
            return PER_MODEL
    except (OSError, ValueError):
        pass
    # registry 가 없으면 tree 로: <task>/<family>/<stem>/<stem>_sync.* 가 하나라도 있으면 per_model
    for lang in LANGS:
        base = _base(Path(root), lang)
        if not base.is_dir():
            continue
        for task in base.iterdir():
            if not task.is_dir() or task.name in _SKIP:
                continue
            for fam in task.iterdir():
                if fam.is_dir() and any(s.is_dir() and _is_example_dir(s, lang) for s in fam.iterdir()):
                    return PER_MODEL
    return LEGACY


def detect(root) -> str:
    return _detect(str(root))


@lru_cache(maxsize=8)
def _index(root: str) -> dict:
    kind = _detect(root)
    found: dict = {}
    for lang in LANGS:
        base = _base(Path(root), lang)
        if not base.is_dir():
            continue
        for task in sorted(p for p in base.iterdir() if p.is_dir() and p.name not in _SKIP):
            if kind == LEGACY:
                cands = [(None, d) for d in task.iterdir() if d.is_dir() and d.name not in _SKIP]
            else:
                cands = [(fam.name, d) for fam in task.iterdir() if fam.is_dir() and fam.name not in _SKIP
                         for d in fam.iterdir() if d.is_dir() and d.name not in _SKIP]
                # add_model.sh (branch 에서도 그대로) 는 <task>/<model>/ 모양으로 만든다 — per-model tree 안의 그것도 예제다
                cands += [(None, d) for d in task.iterdir() if d.is_dir() and d.name not in _SKIP]
            for family, d in cands:
                if not _is_example_dir(d, lang):
                    continue
                key = (task.name, d.name)
                cur = found.get(key) or Example(task=task.name, name=d.name, family=family)
                found[key] = Example(cur.task, cur.name, cur.family or family,
                                     d if lang == "python" else cur.py_dir,
                                     d if lang == "cpp" else cur.cpp_dir)
    return found


def clear_cache() -> None:
    _detect.cache_clear()
    _index.cache_clear()


def examples(root) -> Iterable[Example]:
    return list(_index(str(root)).values())


def find(root, task: str, name: str) -> Optional[Example]:
    ex = _index(str(root)).get((task, name))
    if ex is None and task:
        # 옛 이름으로 불렸을 때 (예: legacy task key) — 같은 이름의 예제가 하나뿐이면 그것
        hits = [e for e in _index(str(root)).values() if e.name == name]
        ex = hits[0] if len(hits) == 1 else None
    return ex


def example_dir(root, lang: str, task: str, name: str) -> Path:
    """예제 폴더. 모르는 예제는 legacy 모양의 경로를 돌려준다 (없는 경로 — 호출부의 '없음' 판정이 그대로)."""
    ex = find(root, task, name)
    d = ex.dir(lang) if ex else None
    return d if d is not None else _base(Path(root), lang) / task / name


def python_script(root, task: str, name: str, variant: str) -> Path:
    return example_dir(root, "python", task, name) / f"{name}_{variant}.py"


def cpp_source(root, task: str, name: str, variant: str) -> Path:
    return example_dir(root, "cpp", task, name) / f"{name}_{variant}.cpp"


def cpp_binary(build_dir, name: str, variant: str) -> Path:
    return Path(build_dir) / f"{name}_{variant}"


def config_path(root, task: str, name: str) -> Optional[Path]:
    for lang in ("cpp", "python"):
        p = example_dir(root, lang, task, name) / "config.json"
        if p.is_file():
            return p
    return None


def load_config(root, task: str, name: str) -> dict:
    p = config_path(root, task, name)
    if p is None:
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def flat_config(data: dict) -> dict:
    """per_model 의 config.json 은 중첩 spec 이고 threshold 는 ``config`` 안에 있다. 실행에 넘기는 것은 늘 평평하게
    — C++ ``--config`` reader 는 평평한 key 만 읽는다."""
    if isinstance(data, dict) and "variant" in data and isinstance(data.get("config"), dict):
        return dict(data["config"])
    return dict(data or {})


def threshold_config(root, task: str, name: str) -> dict:
    return flat_config(load_config(root, task, name))


# ── model files ─────────────────────────────────────────────────────────────────────────
def model_locations(root, suite_root=None) -> list:
    locs = [Path(root) / "assets" / "models"]
    if suite_root is not None:
        locs.append(Path(suite_root) / "workspace" / "res" / "models")
    return locs


def find_model(model_file: str, root, suite_root=None, models_dir=None) -> Optional[Path]:
    """``assets/models/x.dxnn`` 또는 ``x.dxnn`` → 실제 파일 (0 byte 제외). 절대 경로는 그대로 확인만."""
    p = PurePosixPath(model_file)
    if p.is_absolute():
        q = Path(model_file)
        return q if q.is_file() and q.stat().st_size > 0 else None
    rel = p.parts[2:] if p.parts[:2] == ("assets", "models") else p.parts
    locs = ([Path(models_dir)] if models_dir else []) + model_locations(root, suite_root)
    if p.parts[:2] != ("assets", "models") and len(p.parts) > 1:
        locs = [Path(root)] + locs            # sample/... 같은 모델 트리 밖의 상대 경로
        rel = p.parts
    for base in locs:
        q = base.joinpath(*rel)
        try:
            if q.is_file() and q.stat().st_size > 0:
                return q
        except OSError:
            continue
    return None


def container_version(path) -> Optional[int]:
    """.dxnn container 판: 'DXNN' 다음 little-endian uint32 (8 byte 만 읽는다, NPU 없이)."""
    try:
        with open(path, "rb") as f:
            head = f.read(8)
    except OSError:
        return None
    if len(head) < 8 or head[:4] != b"DXNN":
        return None
    v = struct.unpack("<I", head[4:8])[0]
    # 판이 아닌 값 (예: 'DXNN' 뒤에 글이 오는 test fixture) 은 모르는 것 — 모르면 막지 않는다
    return v if 0 < v < 256 else None
