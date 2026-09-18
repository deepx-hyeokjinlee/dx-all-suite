"""Root conftest — repo root import 우선순위를 안정화한다."""
from pathlib import Path
import os
import sys

from tests.browser_support import resolve_chromium_executable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) in sys.path:
    sys.path.remove(str(ROOT))
sys.path.insert(0, str(ROOT))

# 일부 모듈 테스트가 자체 top-level package 경로를 앞에 추가해도 감사 도구 import가
# 흔들리지 않도록 root namespace를 먼저 고정한다.
import tools.i18n_audit  # noqa: E402,F401


def pytest_configure(config):
    """Let browser tests reuse a host Chromium when Playwright has no cache."""
    del config

    # DX_OFFLINE_GUARD=1 이면 외부 소켓을 막은 채로 돈다. run_ci.sh --offline 이
    # 이것을 켠다 — 폐쇄망에서 개발하던 시절에는 환경이 해주던 일이다.
    # localhost 는 막지 않는다: 테스트가 모듈 서버를 띄워 127.0.0.1 로 말한다.
    # 등급과 예외는 docs/offline-contract.md.
    if os.environ.get("DX_OFFLINE_GUARD") == "1":
        from tests.offline_guard import install as install_offline_guard

        install_offline_guard()
    executable = resolve_chromium_executable()
    if executable is None:
        return

    try:
        from playwright.sync_api import BrowserType
    except ModuleNotFoundError:
        return

    original_launch = BrowserType.launch
    if getattr(original_launch, "_dx_system_chromium_fallback", False):
        return

    def launch_with_system_chromium(self, *args, **kwargs):
        browser_name = getattr(self, "name", None)
        if browser_name is None:
            browser_name = getattr(getattr(self, "_impl_obj", None), "name", None)
        if browser_name == "chromium":
            kwargs.setdefault("executable_path", executable)
        return original_launch(self, *args, **kwargs)

    launch_with_system_chromium._dx_system_chromium_fallback = True
    BrowserType.launch = launch_with_system_chromium


def _ensure_launcher_package():
    """Restore launcher package if a test imported launcher/launcher.py as top-level 'launcher'."""
    mod = sys.modules.get("launcher")
    if mod is not None and not hasattr(mod, "__path__"):
        for name in list(sys.modules):
            if name == "launcher" or name.startswith("launcher."):
                del sys.modules[name]


def pytest_runtest_setup(item):
    nodeid = item.nodeid
    if (
        nodeid.startswith("tests/launcher/")
        or "test_boot_animation.py" in nodeid
        or "test_dx_server_body_parsing.py" in nodeid
        or "test_launcher_wiring.py" in nodeid
    ):
        _ensure_launcher_package()
