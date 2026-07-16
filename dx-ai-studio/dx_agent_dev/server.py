#!/usr/bin/env python3
"""DX Agent Dev Server — 대화형 콘솔 (port 8099)."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

from dx_agent_dev.core.config import (DEFAULT_PORT, STATIC_DIR, TEMPLATES_DIR, SERVER_NAME,
                         WORKSPACE_ROOT, PROMPT_MAX_LEN, resolve_target)
from dx_agent_dev.core import environment
from dx_agent_dev.core.agent_runner import AgentRunner, CopilotAdapter, MockAdapter
from dx_agent_dev.core.conversation_store import ConversationStore
from dx_agent_dev.core.message_pipeline import CLI_RESUME_AGENTS, prepare_sse_event
from dx_agent_dev.core.prompt_wrap import wrap_autopilot_prompt, wrap_console_prompt, wrap_with_conversation_history
from dx_agent_dev.core.run_context import RunContext
from dx_agent_dev.core.adapters import make_adapter
from dx_agent_dev.core.showcases import load_showcases
from shared.dx_server import DXBaseHandler
from shared.chat import ChatEngine

PORT = DEFAULT_PORT

_chat_engine = ChatEngine(
    app_name="dx_agent_dev",
    fallback_rules=[
        (["agent", "console", "build", "에이전트", "콘솔", "빌드"], {
            "ko": "DX Agent Dev 콘솔에 자연어로 요청하면 NPU 앱을 만들어 줍니다.",
            "en": "Describe what you want in the DX Agent Dev console and it builds an NPU app.",
        }),
    ],
)


def _degraded_payload(env):
    """강등 SSE 페이로드(MED-8, §10 #8). 순수 함수 — 단위 테스트 대상."""
    return {"type": "degraded", "text": env.get("reason") or "unavailable"}


def _make_runner():
    env = environment.detect_environment()
    if env.get("forced_mock") or not env["available"]:
        adapter = MockAdapter()
    else:
        adapter = CopilotAdapter(env["cli"])
    return AgentRunner(adapter, WORKSPACE_ROOT)


_runner = _make_runner()
_conversations = ConversationStore()


class AgentDevHandler(DXBaseHandler):
    server_name = SERVER_NAME
    static_dir = STATIC_DIR
    templates_dir = TEMPLATES_DIR
    log_filter = ["/static/", "/api/agent/status"]

    def route(self):
        if self.handle_chat_routes(_chat_engine):
            return
        if self.route_common():
            return
        if self.command == "GET":
            if self.url_path == "/api/agent/status":
                return self.send_json(self._status())
            if self.url_path == "/api/agent/showcases":
                return self.send_json({"showcases": load_showcases()})
            if self.url_path == "/api/agent/login/status":
                return self.send_json(self._login_status())
            if self.url_path == "/api/agent/models":
                return self.send_json(self._agent_models())
        if self.command == "POST":
            if self.url_path == "/api/agent/run":
                return self._run_sse()
            if self.url_path == "/api/agent/cancel":
                _runner.cancel()
                return self.send_json({"ok": True})
        self.route_legacy()

    def _status(self):
        env = environment.detect_environment()
        forced = env.get("forced_mock", False)
        agents = [] if forced else environment.detect_available_agents()
        return {
            "available": env["available"] or forced,
            "reason": env.get("reason"),
            "busy": _runner.is_busy(),
            "showcase_count": len(load_showcases()),
            "agents": agents,
        }

    def _agent_models(self):
        """?agent=<name> → 동적 모델 목록(+default). 정적 config 폴백은 list_agent_models 내부."""
        from urllib.parse import urlparse, parse_qs
        from dx_agent_dev.core.agents_config import AGENTS
        agent = (parse_qs(urlparse(self.path).query).get("agent", [""])[0] or "").strip()
        models = environment.list_agent_models(agent) if agent else []
        return {"agent": agent, "models": models,
                "default_model": AGENTS.get(agent, {}).get("default_model")}

    def _login_status(self):
        """in-UI 로그인 보조: ?agent=<name> → 설치/인증 상태 + 로그인 명령 안내.

        대화형 OAuth는 결국 브라우저가 필요하므로, 여기서는 정확한 로그인 명령을 안내하고
        is_authenticated()로 완료 여부를 재확인할 수 있게 한다(거짓 음성 방지: None=unknown).
        """
        from urllib.parse import urlparse, parse_qs
        from dx_agent_dev.core.adapters import make_adapter
        agent = (parse_qs(urlparse(self.path).query).get("agent", [""])[0] or "").strip()
        adapter = make_adapter(agent) if agent else None
        if adapter is None:
            return {"agent": agent, "installed": False, "authenticated": None, "hint": None}
        return {
            "agent": agent,
            "installed": adapter.is_available(),
            "authenticated": adapter.is_authenticated(),
            "hint": adapter.login_cmd_hint,
        }

    def _run_sse(self):
        body = self.read_json_body()
        raw_prompt = (body.get("prompt") or "").strip()
        if not raw_prompt:
            return self.send_error_json(400, "empty prompt")
        if len(raw_prompt) > PROMPT_MAX_LEN:
            return self.send_error_json(400, "prompt too long")

        conversation_id = (body.get("conversation_id") or "").strip() or None
        conv = _conversations.get(conversation_id) if conversation_id else None

        env = environment.detect_environment()
        forced = env.get("forced_mock", False)
        if not (env["available"] or forced):
            self.start_sse()
            self.send_sse_data(json.dumps(_degraded_payload(env)))
            self.end_sse()
            return

        mode = (body.get("mode") or "interactive").strip()
        autopilot = (mode == "autopilot")

        agent = (body.get("agent") or "").strip() or None
        model = (body.get("model") or "").strip() or None
        effort = (body.get("effort") or "").strip() or None
        target = (body.get("target") or "").strip() or None
        adapter = None
        if agent is not None:
            adapter = make_adapter(agent, model, effort)
            if adapter is None:
                return self.send_error_json(400, "unknown agent")
            if not forced:
                available = {a["name"] for a in environment.detect_available_agents()}
                if agent not in available:
                    return self.send_error_json(400, "unknown agent")
        if forced:
            adapter = None

        if conv is None:
            conv = _conversations.create(agent=agent, model=model, effort=effort)
        else:
            if agent and conv.agent and conv.agent != agent:
                return self.send_error_json(400, "agent mismatch for conversation")
            conv.agent = conv.agent or agent
            conv.model = model or conv.model
            conv.effort = effort or conv.effort

        agent_name = agent or conv.agent or ""
        if autopilot:
            # One-shot run: no resume, no interactive history, autopilot directive only.
            prompt = wrap_autopilot_prompt(raw_prompt)
            run_ctx = RunContext(
                conversation_id=conv.id,
                is_followup=False,
                cli_session_id=None,
                supports_cli_resume=False,
                autopilot=True,
            )
        else:
            is_followup = conv.is_followup
            if is_followup and agent_name not in CLI_RESUME_AGENTS:
                prompt = wrap_with_conversation_history(raw_prompt, conv)
            else:
                prompt = wrap_console_prompt(raw_prompt, is_followup=is_followup)
            run_ctx = RunContext(
                conversation_id=conv.id,
                is_followup=is_followup,
                cli_session_id=conv.cli_session_id,
                supports_cli_resume=agent_name in CLI_RESUME_AGENTS,
            )
        if len(prompt) > PROMPT_MAX_LEN:
            return self.send_error_json(400, "prompt too long")

        if _runner.is_busy():
            return self.send_error_json(409, "agent busy")

        conv.add_user(raw_prompt)
        # cwd = the selected target workdir (harness_dirs[0]), so the agent discovers that
        # project's CLAUDE.md + .claude/skills — mirrors the original SCENARIO_WORKDIRS.
        target_dir = str(resolve_target(target))
        harness = [target_dir] + [h for h in env.get("harness_dirs", []) if h != target_dir]
        assistant_chunks: list[str] = []
        session_dir_bound = bool(conv.session_dir)

        self.start_sse()
        try:
            for ev in _runner.run(
                prompt, harness, adapter=adapter, conversation=conv, run_ctx=run_ctx,
            ):
                if ev.get("type") == "session":
                    sid = ev.get("cli_session_id")
                    if sid:
                        _conversations.bind_cli_session(conv, sid)
                    status_text = ev.get("status_text")
                    if status_text:
                        if not self.send_sse_data(json.dumps(
                            {"type": "status", "text": status_text}, ensure_ascii=False,
                        )):
                            break
                    continue

                if ev.get("type") == "message":
                    text = ev.get("text") or ""
                    if ev.get("delta"):
                        assistant_chunks.append(text)
                    elif ev.get("final"):
                        assistant_chunks = [text]
                    else:
                        assistant_chunks.append(text)

                if ev.get("type") == "done":
                    ev = dict(ev)
                    ev["conversation_id"] = conv.id
                    if not session_dir_bound and ev.get("session_dir"):
                        _conversations.bind_session_dir(conv, ev["session_dir"])
                        session_dir_bound = True

                out = prepare_sse_event(ev)
                if out is None:
                    continue
                if not self.send_sse_data(json.dumps(out, ensure_ascii=False)):
                    break

            assistant_text = "".join(assistant_chunks).strip()
            if assistant_text:
                from dx_agent_dev.core.message_sanitize import sanitize_assistant_text
                conv.add_assistant(sanitize_assistant_text(assistant_text))
            _conversations.save(conv)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.end_sse()


def create_server(port: int = PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), AgentDevHandler)


if __name__ == "__main__":
    from shared.dx_server import DXServer
    DXServer(AgentDevHandler, SERVER_NAME, PORT).start()
