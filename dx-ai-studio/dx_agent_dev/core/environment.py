"""에이전트 CLI / 하니스 디렉토리 감지."""
import os
import shutil
import time

from dx_agent_dev.core.config import harness_search_paths

_models_cache = {}      # name -> (ts, models) — CLI 조회 비용 절감용 단기 캐시
_MODELS_TTL = 120.0


def list_agent_models(name):
    """agent의 모델 목록. 어댑터의 동적 조회(list_models) 우선, 실패 시 정적 config 폴백.

    CLI 조회는 비용이 있어 짧게 캐시한다.
    """
    from dx_agent_dev.core.agents_config import AGENTS
    from dx_agent_dev.core.adapters import make_adapter
    now = time.time()
    cached = _models_cache.get(name)
    if cached and (now - cached[0]) < _MODELS_TTL:
        return cached[1]
    models = None
    try:
        adapter = make_adapter(name)
        if adapter is not None:
            models = adapter.list_models()
    except Exception:
        models = None
    if not models:
        models = list(AGENTS.get(name, {}).get("models", []))
    _models_cache[name] = (now, models)
    return models

COPILOT_BIN = "copilot"
_HARNESS_MARKER = ".deepx"


def find_harness_dirs():
    """하니스 마커(.deepx)를 가진 후보 경로 목록."""
    found = []
    for base in harness_search_paths():
        try:
            if base and (base / _HARNESS_MARKER).is_dir():
                found.append(base)
        except OSError:
            continue
    return found


def detect_available_agents():
    """설치된 CLI 어댑터 목록(name/models/default_model/authenticated). 드롭다운 동적 노출용.

    authenticated: True/False(확정) 또는 None(unknown). 어댑터의 값싼 자격증명 검사 결과.
    """
    from dx_agent_dev.core.agents_config import AGENTS
    from dx_agent_dev.core.adapters import make_adapter
    out = []
    for name, cfg in AGENTS.items():
        if shutil.which(cfg["cli_bin"]):
            try:
                adapter = make_adapter(name)
                authed = adapter.is_authenticated() if adapter else None
            except Exception:
                authed = None
            out.append({
                "name": name,
                "models": list(cfg["models"]),
                "default_model": cfg["default_model"],
                "authenticated": authed,
                "reasoning_efforts": list(cfg.get("reasoning_efforts", [])),
                "default_effort": cfg.get("default_effort"),
            })
    return out


def detect_environment():
    """실행 가능 여부 판정. DX_AGENT_ADAPTER=mock이면 Mock 강제(검증용, spec §5.4)."""
    if os.environ.get("DX_AGENT_ADAPTER") == "mock":
        return {"available": True, "forced_mock": True, "cli": None,
                "harness_dirs": [], "reason": None}
    cli = shutil.which(COPILOT_BIN)
    # 설치된 에이전트가 하나라도 있으면 사용 가능(copilot 전용 게이트 제거 — claude/codex/cursor/opencode 포함).
    # detect_available_agents()는 copilot도 포함하므로 cli는 표시/기본값 용도로만 유지.
    has_agent = bool(detect_available_agents()) or bool(cli)
    harness = find_harness_dirs()
    if not has_agent:
        reason = "cli_missing"
    elif not harness:
        reason = "harness_missing"
    else:
        reason = None
    return {
        "available": has_agent and bool(harness),
        "forced_mock": False,
        "cli": cli,
        "harness_dirs": [str(h) for h in harness],
        "reason": reason,
    }
