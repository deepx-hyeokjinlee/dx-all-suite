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
    가드레일이다 (fs_browse.py 의 모듈 docstring 이 같은 말을 한다: "the compiler
    UI is a localhost tool operating on the user's own machine").

    그래서 컴파일 경로(`/compile`, `/compile/resume` 의 model_path·config_path·
    output_dir·qxnn_path)에는 **의도적으로 적용하지 않는다.** 걸면
    `/media/usb/model.onnx` 같은 멀쩡한 모델이 403 이 된다 — 안전해지는 것은 없고
    (localhost 에 POST 할 수 있는 사람은 이미 그 계정으로 로그인했고 파일 접근은
    OS 권한이 막는다) 되던 기능만 없어진다.

    이 비대칭은 실수가 아니라 결정이다. 2026-09-18 전수조사에서 "버그" 로
    오인해 조사했고, 아무 데도 적혀 있지 않은 것이 원인이었다.

    **이 결정이 선 전제**: 이 서버를 localhost 밖으로 노출하지 않는다
    (사용자 확인, 2026-09-18). 전제가 바뀌면 결정도 바뀐다 — 외부에 노출하는
    순간 컴파일 경로에도 이 검사를 걸어야 한다.

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
