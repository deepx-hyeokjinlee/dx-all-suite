"""Build a static HTML dashboard backed by dataset.json."""

from __future__ import annotations

import json
from pathlib import Path

from .aggregator import save_dataset_json

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "dashboard"


def build_static_dashboard(dataset: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    save_dataset_json(dataset, output_dir / "dataset.json")
    index_template = (_TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (_TEMPLATE_DIR / "app.js").read_text(encoding="utf-8")
    styles_css = (_TEMPLATE_DIR / "styles.css").read_text(encoding="utf-8")
    index_html = index_template.replace("__DATASET_JSON__", json.dumps(dataset))
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    (output_dir / "app.js").write_text(app_js, encoding="utf-8")
    (output_dir / "styles.css").write_text(styles_css, encoding="utf-8")
    return output_dir / "index.html"

