"""에이전트 CLI / 하니스 디렉토리 감지."""
import concurrent.futures
import os
import shutil
import time

from dx_agent_dev.core.config import harness_search_paths

_models_cache = {}      # name -> (ts, models) — CLI 조회 비용 절감용 단기 캐시
_MODELS_TTL = 120.0
# 어댑터별 list_models()가 자체 subprocess timeout(cursor/opencode: 20s)을 갖고 있지만,
# 여기서도 상한을 둬 (미래의) 타임아웃 없는 구현이 /api/agent/models 응답을 막지 않게 한다.
_MODELS_CALL_TIMEOUT = 15.0


def list_agent_models(name):
    """agent의 고를 수 있는 model id 목록 (agent_model_info 의 models)."""
    return agent_model_info(name)["models"]


def agent_model_info(name):
    """{"models": 고를 수 있는 id, "default_model": id, "catalog": [{id, name, usage, enabled}] 또는 None}.

    어댑터의 동적 조회 우선, 실패 시 정적 config 폴백. CLI 조회는 비용이 있어 짧게 캐시하고, 응답이
    없는 CLI 호출이 엔드포인트를 막지 않도록 하드 타임아웃을 둔다(_MODELS_CALL_TIMEOUT).

    copilot 은 계정의 목록 (ACP) 을 받아 **전체를 보이고 계정 것만 고르게** 한다 — catalog = 계정 목록
    (enabled) + 정적 표에만 있는 것 (enabled False: 이 계정에서 막혔거나 은퇴). 계정마다 요금제 · 회사
    정책이 달라 쓸 수 있는 model 이 다르다 (사용자 결정 2026-09-30).
    """
    from dx_agent_dev.core.agents_config import AGENTS
    from dx_agent_dev.core.adapters import make_adapter
    now = time.time()
    cached = _models_cache.get(name)
    if cached and (now - cached[0]) < _MODELS_TTL:
        return cached[1]
    cfg = AGENTS.get(name, {})
    info = None
    try:
        adapter = make_adapter(name)
        if adapter is not None:
            # shutdown(wait=False): a hung call must not block this one — don't wait for the worker.
            probe = getattr(adapter, "account_models", None) or adapter.list_models
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            try:
                got = pool.submit(probe).result(timeout=_MODELS_CALL_TIMEOUT)
            finally:
                pool.shutdown(wait=False)
            if isinstance(got, dict) and got.get("models"):
                account = got["models"]
                ids = {m["id"] for m in account}
                catalog = list(account) + [{"id": m, "name": m, "usage": None, "enabled": False}
                                           for m in cfg.get("models", []) if m not in ids]
                pickable = [m["id"] for m in account if m["enabled"]]
                info = {"models": pickable, "catalog": catalog,
                        "default_model": got.get("default") if got.get("default") in pickable
                        else (pickable[0] if pickable else cfg.get("default_model"))}
            elif isinstance(got, list) and got:
                info = {"models": got, "catalog": None, "default_model": cfg.get("default_model")}
    except Exception:
        info = None
    if info is None:
        info = {"models": list(cfg.get("models", [])), "catalog": None, "default_model": cfg.get("default_model")}
    _models_cache[name] = (now, info)
    return info

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
    pinned = os.environ.get("DX_AGENT_DEV_PIN_AGENTS")
    if pinned is not None:
        # 비주얼 회귀용 고정: 개발자 PATH/로그인 상태 대신 주어진 이름을 순서대로,
        # 로그인된 것으로 돌려준다. 계약: tests/dx_agent_dev/test_agents_can_be_pinned.py
        names = [n.strip() for n in pinned.split(",") if n.strip() in AGENTS]
        return [_agent_entry(n, AGENTS[n], True) for n in names]
    from dx_agent_dev.core.adapters import make_adapter
    from dx_agent_dev.core.adapters.base import find_cli
    out = []
    for name, cfg in AGENTS.items():
        if find_cli(cfg["cli_bin"]):
            try:
                adapter = make_adapter(name)
                authed = adapter.is_authenticated() if adapter else None
            except Exception:
                authed = None
            out.append(_agent_entry(name, cfg, authed))
    return out


def _agent_entry(name, cfg, authed):
    return {
        "name": name,
        "models": list(cfg["models"]),
        "default_model": cfg["default_model"],
        "authenticated": authed,
        "reasoning_efforts": list(cfg.get("reasoning_efforts", [])),
        "default_effort": cfg.get("default_effort"),
    }


def detect_environment():
    """실행 가능 여부 판정. DX_AGENT_ADAPTER=mock이면 Mock 강제(검증용, spec §5.4).

    반환값에 "agents"(detect_available_agents() 결과)를 포함한다 — 호출부가 같은
    요청 안에서 detect_available_agents()를 다시 부르지 않고 이 값을 재사용할 수
    있도록(중복 계산 제거). forced_mock 조기 반환 경로는 원래도 이 계산을 건너뛰므로
    "agents" 키를 넣지 않는다(호출부는 forced_mock일 때 이 키를 쓰지 않는다).
    """
    if os.environ.get("DX_AGENT_ADAPTER") == "mock":
        return {"available": True, "forced_mock": True, "cli": None,
                "harness_dirs": [], "reason": None}
    from dx_agent_dev.core.adapters.base import find_cli
    cli = find_cli(COPILOT_BIN)
    # 설치된 에이전트가 하나라도 있으면 사용 가능(copilot 전용 게이트 제거 — claude/codex/cursor/opencode 포함).
    # detect_available_agents()는 copilot도 포함하므로 cli는 표시/기본값 용도로만 유지.
    agents = detect_available_agents()
    has_agent = bool(agents) or bool(cli)
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
        "agents": agents,
    }
