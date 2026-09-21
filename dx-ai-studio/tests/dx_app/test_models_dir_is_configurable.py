"""모델이 어디 설치돼 있는지는 설정으로 정할 수 있어야 한다.

동기는 둘이다.

1. **제품** — 모델은 크다(.dxnn 하나가 85MB 인 것도 있다). 다른 디스크에 두고
   쓰고 싶다는 요구는 자연스럽다. 지금은 `dx_app/assets/models` 로 못박혀 있다.

2. **테스트 결정성** — 이게 급한 쪽이다. dx_app 랜딩의 모델 표는 **로컬에 무엇이
   설치돼 있는지** 에 따라 다르게 그려진다. models.js 의 `dl = !!runnable` 이
   설치된 모델에만 C++/PYTHON/MODE 열을 켜고 ACTIONS 에 Graph 버튼을 더한다.
   다섯 열의 폭이 달라져 표가 통째로 리플로우되고, 비주얼 베이스라인이 최대 22%
   어긋났다. 원인은 UI 가 아니라 **테스트가 개발자 파일시스템이라는 통제되지 않은
   입력을 그대로 찍고 있다**는 것이다.

   이 저장소는 같은 문제를 이미 한 번 풀었다 — `tests/server_helpers.py` 가
   dx_monitor 에 `DX_MONITOR_SKIP_HARDWARE_INIT=1` 을 세워 실제 하드웨어 읽기를
   끈다. dx_app 의 설치 모델도 같은 성격인데 통제하지 않았을 뿐이다.

여기서는 운영 코드에 테스트 플래그를 심지 않는다. **경로를 설정 가능하게** 만들고
테스트가 그 설정을 쓴다 — 같은 결과를 얻으면서 제품도 나아진다.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

ENV = "DX_APP_MODELS_DIR"


@pytest.fixture()
def reloaded(monkeypatch):
    """config/models 를 주어진 환경으로 다시 읽어 들인다."""

    def _load(models_dir: str | None):
        if models_dir is None:
            monkeypatch.delenv(ENV, raising=False)
        else:
            monkeypatch.setenv(ENV, models_dir)
        import dx_app.core.config as config

        importlib.reload(config)
        import dx_app.core.models as models

        importlib.reload(models)
        return config, models

    yield _load
    for name in ("dx_app.core.models", "dx_app.core.config"):
        import sys

        if name in sys.modules:
            importlib.reload(sys.modules[name])


def test_without_the_env_the_default_location_is_unchanged(reloaded):
    config, _ = reloaded(None)
    assert config.MODELS_DIR == config.ASSETS_DIR / "models"


def test_the_env_moves_the_models_directory(reloaded, tmp_path):
    config, _ = reloaded(str(tmp_path))
    assert config.MODELS_DIR == tmp_path


def test_a_model_is_not_installed_when_the_directory_is_empty(reloaded, tmp_path):
    """이것이 비주얼 결정성의 핵심이다 — 실제 설치 여부와 무관하게 비어 보여야 한다."""
    _, models = reloaded(str(tmp_path))
    assert models._required_dxnn_exists("assets/models/espcn-x4_17x17.dxnn") is False


def test_a_model_is_installed_when_it_sits_in_the_configured_directory(reloaded, tmp_path):
    (tmp_path / "espcn-x4_17x17.dxnn").write_bytes(b"not a real model")
    _, models = reloaded(str(tmp_path))
    assert models._required_dxnn_exists("assets/models/espcn-x4_17x17.dxnn") is True


def test_chip_subdirectories_follow_the_configured_root(reloaded, tmp_path):
    """q-pro / q-master 는 모델 디렉터리 **아래** 에 있다. 같이 따라와야 한다."""
    (tmp_path / "q-pro").mkdir()
    (tmp_path / "q-pro" / "x.dxnn").write_bytes(b"x")
    _, models = reloaded(str(tmp_path))
    assert models._required_dxnn_exists("assets/models/q-pro/x.dxnn") is True


def test_paths_outside_the_models_tree_are_untouched(reloaded, tmp_path):
    """이 설정은 **모델 디렉터리만** 옮긴다.

    assets/videos 나 sample/ 은 그대로 DX_APP_ROOT 기준이어야 한다 — 처음에
    "밖을 가리키면 False" 라고 썼다가 틀렸다. 그 함수는 존재만 보고 확장자를
    따지지 않으므로, 실재하는 sample 파일은 True 가 맞다. 확인할 것은
    **어디로 해석되는가** 이지 존재 여부가 아니다.
    """
    config, _ = reloaded(str(tmp_path))
    assert config.ASSETS_DIR == config.DX_APP_ROOT / "assets"
    assert config.resolve_model_path("assets/videos/x.mp4") == \
        config.DX_APP_ROOT / "assets" / "videos" / "x.mp4"
    assert config.resolve_model_path("sample/img/sample_dog.jpg") == \
        config.DX_APP_ROOT / "sample" / "img" / "sample_dog.jpg"
    # 그리고 모델 경로는 설정을 따른다 — 같은 함수가 둘을 갈라야 한다.
    assert config.resolve_model_path("assets/models/x.dxnn") == tmp_path / "x.dxnn"
