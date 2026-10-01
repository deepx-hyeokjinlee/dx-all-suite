#!/usr/bin/env python3
"""Model Zoo card · 상세 화면의 추론 결과 이미지를 per-model layout 의 dx_app 예제로 만든다.

generate_thumbnails.py 는 legacy dx_app 서버에 /api/run 을 보낸다 — 예제가 없는 model 은 남의 binary 를 빌려
돌려 (super resolution model 에 분류 결과 "jackfruit 75%") 틀린 그림이 나왔고, publish page 에만 있는 새 model
(spec 2026-10-01 dx_app per-model layout 결정 8) 은 예제도 model 파일도 없어 그림이 없었다.

여기서는 model 마다:
  1. 그 model 의 artifact 파일 이름 (= dx_app per-model 예제의 stem) 으로 예제를 찾고
  2. .dxnn 을 받아 (끝나면 지운다 — 디스크가 작다) dx_engine 이 읽은 실제 입력 shape 을 적고
  3. studio 의 run_inference 로 (그 예제 자신의 전처리 · 후처리 · 기본 입력) 한 장 돌려
  4. thumbnails/<id>.jpg · examples/<id>_result.jpg (+ before/after · overlay 는 _original) 로 저장한다.
실제 입력 shape 이 catalog 의 값과 다르면 model_enrichment.json 의 input_resolution 을 고친다 (sync 가 그것을 쓴다).

    DX_APP_ROOT=<per-model dx_app> python -m dx_modelzoo.scripts.generate_examples [--missing] [--ids a,b] [--dry-run]

DX-RT 가 그 .dxnn container 를 읽을 수 있어야 한다 (2_5_0 = v9 → DX-RT 3.5.0).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from dx_modelzoo.core.config import DATA_DIR, EXAMPLE_TYPES
from shared import dx_app_layout as layout
from shared import dxrt

THUMB_DIR = DATA_DIR / "thumbnails"
EXAMPLE_DIR = DATA_DIR / "examples"
ENRICHMENT = DATA_DIR / "model_enrichment.json"
_TIERS = ("qlite_dxnn", "qpro_dxnn", "qmaster_dxnn")


def artifact_url(model: dict):
    for tier in _TIERS:
        url = ((model.get("artifacts") or {}).get(tier) or {}).get("remote_url") or ""
        if url.endswith(".dxnn"):
            return url
    return None


def stem_of(model: dict):
    url = artifact_url(model)
    return url.rsplit("/", 1)[-1][:-len(".dxnn")] if url else None


def has_own_images(model_id: str) -> bool:
    return (THUMB_DIR / f"{model_id}.jpg").is_file() and (EXAMPLE_DIR / f"{model_id}_result.jpg").is_file()


def plan(models: list, app_root, ids=None, missing=False) -> list:
    """(model, example) 짝. 예제가 없거나 받을 .dxnn 이 없으면 이유와 함께."""
    by_stem = {e.name: e for e in layout.examples(app_root) if e.py_dir is not None or e.cpp_dir is not None}
    out = []
    for m in models:
        if ids and m["id"] not in ids:
            continue
        if missing and not ids and has_own_images(m["id"]):
            continue
        stem = stem_of(m)
        ex = by_stem.get(stem) if stem else None
        reason = None if ex else ("no .dxnn artifact" if not stem else f"no dx_app example for {stem}")
        out.append({"id": m["id"], "stem": stem, "url": artifact_url(m), "example": ex, "skip": reason,
                    "category": m.get("category"),
                    "resolution": (m.get("specification") or {}).get("input_resolution") or ""})
    return out


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(tmp, dest)


def _input_shape(model_path: Path):
    """dx_engine 이 읽은 입력 tensor shape (runtime venv 에서)."""
    from shared.runtime import runtime_python
    code = ("import json,sys;from dx_engine import InferenceEngine;"
            "print(json.dumps(InferenceEngine(sys.argv[1]).get_input_tensors_info()[0]['shape']))")
    r = subprocess.run([runtime_python() or sys.executable, "-c", code, str(model_path)], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def _resolution(shape) -> str:
    """NHWC [1,H,W,C] → 'HxWxC' (dx_app 의 파일 이름 · bisenet 등 기존 값과 같은 순서)."""
    if not shape or len(shape) < 3:
        return ""
    dims = [int(x) for x in shape[1:]]
    if len(dims) == 3 and dims[0] in (1, 3, 4) and dims[-1] not in (1, 3, 4):   # NCHW
        dims = dims[1:] + dims[:1]
    return "x".join(str(d) for d in dims)


def _same_dims(a: str, b: str) -> bool:
    """'224x224x3' 와 '416x416x3' 는 다르고, 'HxW' · 'WxH' 의 순서만 다른 것은 같다."""
    pa, pb = [p for p in a.split("x") if p], [p for p in b.split("x") if p]
    return sorted(pa[:2]) == sorted(pb[:2]) if len(pa) >= 2 and len(pb) >= 2 else False


def _fix_curated_resolution(model_id: str, res: str) -> None:
    path = DATA_DIR / "model_catalog.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for m in data.get("models", []):
        if m.get("id") == model_id and isinstance(m.get("specification"), dict) \
                and m["specification"].get("input_resolution") not in (None, res):
            m["specification"]["input_resolution"] = res
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return


def run_one(item: dict, app_root: Path, keep: bool, enrichment: dict) -> str:
    from dx_app.core.inference import run_inference

    ex = item["example"]
    model_dir = app_root / "assets" / "models"
    dest = model_dir / f"{item['stem']}.dxnn"
    fetched = False
    if not (dest.is_file() and dest.stat().st_size > 0):
        _download(item["url"], dest)
        fetched = True
    try:
        need = dxrt.needs_for_file(dest)
        if need:
            return f"needs DX-RT {need}"
        res = _resolution(_input_shape(dest))
        if res and not _same_dims(res, item["resolution"]):
            enrichment.setdefault(item["id"], {})["input_resolution"] = res
            _fix_curated_resolution(item["id"], res)   # curated catalog 이 merge 에서 이기므로 거기도
        lang = "python" if ex.py_dir is not None else "cpp"
        r = run_inference(item["stem"], ex.task, f"assets/models/{item['stem']}.dxnn", lang=lang,
                          variant="sync", input_type="image")
        img = r.get("result_image")
        if r.get("error") or not img:
            return f"failed: {r.get('error') or ('exit ' + str(r.get('exit_code')))}"
        data = base64.b64decode(img)
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        EXAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        (THUMB_DIR / f"{item['id']}.jpg").write_bytes(data)
        (EXAMPLE_DIR / f"{item['id']}_result.jpg").write_bytes(data)
        if EXAMPLE_TYPES.get(item["category"], "single") in ("before_after", "overlay"):
            spec = layout.load_config(app_root, ex.task, item["stem"])
            src = app_root / (spec.get("default_image") or "")
            if src.is_file():
                shutil.copy2(src, EXAMPLE_DIR / f"{item['id']}_original.jpg")
        return f"ok ({lang}, {r.get('fps')} FPS, input {res})"
    finally:
        if fetched and not keep:
            dest.unlink(missing_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", default="", help="이 model id 만 (쉼표)")
    ap.add_argument("--missing", action="store_true", help="자기 thumbnail · 결과 그림이 없는 model 만")
    ap.add_argument("--keep-models", action="store_true", help="받은 .dxnn 을 지우지 않는다")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    from dx_app.core.config import DX_APP_ROOT
    from dx_modelzoo.core import catalog
    app_root = Path(DX_APP_ROOT)
    if layout.detect(app_root) != layout.PER_MODEL:
        print(f"[ERROR] {app_root} 는 per-model layout 이 아니다 — DX_APP_ROOT 를 teammate dx_app 으로")
        return 2
    ids = {i for i in args.ids.split(",") if i}
    items = plan(catalog.reload_catalog()["models"], app_root, ids=ids, missing=args.missing)
    enrichment = json.loads(ENRICHMENT.read_text(encoding="utf-8")) if ENRICHMENT.is_file() else {}
    done = failed = 0
    for n, item in enumerate(items, 1):
        if item["skip"]:
            print(f"[{n}/{len(items)}] {item['id']}: skip — {item['skip']}", flush=True)
            continue
        if args.dry_run:
            print(f"[{n}/{len(items)}] {item['id']}: would run {item['example'].task}/{item['stem']}", flush=True)
            continue
        try:
            status = run_one(item, app_root, args.keep_models, enrichment)
        except Exception as e:  # 한 model 의 실패가 나머지를 막지 않게
            status = f"failed: {e}"
        ok = status.startswith("ok")
        done += ok
        failed += not ok
        print(f"[{n}/{len(items)}] {item['id']}: {status}", flush=True)
        if ok:
            ENRICHMENT.write_text(json.dumps(enrichment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[DONE] {done} ok, {failed} failed, {sum(1 for i in items if i['skip'])} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
