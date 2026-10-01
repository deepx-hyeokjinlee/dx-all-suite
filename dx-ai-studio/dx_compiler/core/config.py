"""DX Compiler Configuration — paths, constants, and shared state."""
import hashlib
import os
import tempfile
from pathlib import Path

from shared.paths import SUITE_ROOT, is_safe_path as _shared_is_safe_path, var_dir

SCRIPT_DIR    = Path(__file__).resolve().parent.parent   # dx_compiler/
STATIC_DIR    = SCRIPT_DIR / "static"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
CORE_DIR      = SCRIPT_DIR / "core"
SDK_ROOT      = SUITE_ROOT / "dx-compiler"               # SDK 패키지 (install.sh, example/)
SDK_EXAMPLE   = SDK_ROOT / "example"
SDK_PROPS     = SDK_ROOT / "compiler.properties"
SAMPLE_MODELS_DIR = SDK_ROOT / "dx_com" / "sample_models"
CALIB_DIR         = SDK_ROOT / "dx_com" / "calibration_dataset"

DEFAULT_PORT = 8095
SERVER_NAME  = "DX Compiler"

UPLOAD_DIR = var_dir("compiler", "uploads")

# Allowed base directories for file-system access.
_ALLOWED_ROOTS: list = [
    Path("/home"), Path("/tmp"), Path(tempfile.gettempdir()),
    Path("/data"), Path("/mnt"), Path("/opt"),
]


def is_safe_path(p: str) -> bool:
    """Check that *p* resolves to a location under an allowed root.

    **이것은 보안 경계가 아니다.** 파일 탐색기가 루트 전체를 훑지 않게 하는 UX
    가드레일이다 (fs_browse.py 의 모듈 docstring 이 같은 말을 한다).

    컴파일 경로(`/compile`, `/compile/resume`, `/config/generate` 의 model_path ·
    config_path · output_dir · qxnn_path · dataset_path)는 이 함수가 아니라
    `dx_compiler.core.path_policy` 가 본다 — 허용 루트 안의 실제 파일 · 폴더만.

    2026-09-18 에는 "서버를 localhost 밖으로 노출하지 않는다" 는 전제로 컴파일 경로에
    검사를 걸지 않기로 했다 (그날 spec R1). 기본 bind 가 모든 인터페이스라 전제가
    성립하지 않았고 (QA COM-A1), 2026-10-01 QA COM-A2 로 철회했다.

    근거와 대안 비교: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md (R1)
    """
    try:
        Path(p).resolve()
    except (OSError, ValueError):
        return False
    return _shared_is_safe_path(p, [UPLOAD_DIR] + _ALLOWED_ROOTS)


def static_version() -> str:
    """Generate a short hash from key static file contents for cache-busting."""
    h = hashlib.md5()
    for name in (
        "compiler-i18n.js",
        "viewer_panel.js",
        "config_wizard.js",
        "setup_panel.js",
        "tutorial.js",
        "graph_renderer.js",
        "graph_viewer.js",
    ):
        p = STATIC_DIR / "js" / name
        if p.exists():
            h.update(p.read_bytes())
    for name in ("graph_viewer.css", "style.css"):
        p = STATIC_DIR / "css" / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:8]
