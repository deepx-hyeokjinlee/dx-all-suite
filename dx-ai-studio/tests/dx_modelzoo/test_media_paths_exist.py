"""The catalog only points at thumbnails and result images that exist.

A path to a missing file costs three 404s per model on every catalog load. A missing image is no image (the card
shows its task icon, the detail page its 'Run inference' note); BEiT-L/16 384, the same model filed as
beit_large_patch16, uses that model's file.
"""
from __future__ import annotations

import importlib


def test_every_media_path_in_the_catalog_exists():
    cat = importlib.import_module("dx_modelzoo.core.catalog")
    models = cat.get_catalog()["models"]
    missing = []
    for m in models:
        if m.get("thumbnail") and not cat._image_on_disk(m["thumbnail"]):
            missing.append(("thumbnail", m["id"], m["thumbnail"]))
        res = (m.get("example_images") or {}).get("result")
        if res and not cat._image_on_disk(res):
            missing.append(("result", m["id"], res))
    assert missing == [], missing[:8]
    from tests.installed_sdk import require
    require(cat._image_on_disk("thumbnails/beit_large_patch16.jpg"),
            "the Model Zoo thumbnails are not generated (dx_modelzoo/scripts/generate_thumbnails.py)")
    beit = next(m for m in models if m["id"] == "beit_l_p16_384x384")
    assert beit["thumbnail"] == "thumbnails/beit_large_patch16.jpg"


def test_a_release_with_only_the_optimized_copies_keeps_its_images(tmp_path, monkeypatch):
    """A clone ships data/optimized (tracked), not data/thumbnails or data/examples (ignored). The catalog keeps a
    path whose optimized copy exists — the page loads that copy — and drops one with neither."""
    cat = importlib.import_module("dx_modelzoo.core.catalog")
    (tmp_path / "optimized" / "thumbnails").mkdir(parents=True)
    (tmp_path / "optimized" / "thumbnails" / "m1-jpg.webp").write_bytes(b"RIFF")
    (tmp_path / "optimized" / "examples").mkdir(parents=True)
    (tmp_path / "optimized" / "examples" / "m1_result-png.jpg").write_bytes(b"\xff\xd8")
    monkeypatch.setattr(cat, "DATA_DIR", tmp_path)
    model = {"id": "m1", "thumbnail": "thumbnails/m1.jpg",
             "example_images": {"result": "examples/m1_result.png", "original": "examples/m1_original.jpg"}}
    cat._settle_media(model)
    assert model["thumbnail"] == "thumbnails/m1.jpg"
    assert model["example_images"] == {"result": "examples/m1_result.png"}
