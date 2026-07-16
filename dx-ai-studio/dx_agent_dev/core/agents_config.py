"""에이전트별 CLI/모델 설정 테이블.

모델 목록·플래그는 폐쇄망에서 실 CLI로 확정 불가 → 합리적 초기값(provisional).
일반망 검증 후 이 파일 한 곳에서 조정한다(spec §6, §11).
copilot은 모델 선택이 없으므로 models=[] / default_model=None.
"""

AGENTS = {
    "copilot": {
        "cli_bin": "copilot",
        # copilot has no model-list command (only `--model` + BYOK `providers`); static set
        # derived from the live GitHub Copilot catalog (the github-copilot/* provider that
        # `opencode models` enumerates, prefix stripped — the copilot CLI accepts these bare).
        # Default matches the original harness (.deepx/e2e/test.sh:
        # DX_AGENT_E2E_COPILOT_MODEL=claude-sonnet-4.6).
        "models": [
            "auto",
            "claude-opus-4.8", "claude-opus-4.7", "claude-opus-4.6", "claude-opus-4.5",
            "claude-sonnet-4.6", "claude-sonnet-4.5", "claude-haiku-4.5",
            "gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "gpt-5-mini",
            "gemini-3.1-pro-preview", "gemini-3.5-flash",
        ],
        "default_model": "claude-sonnet-4.6",
        "output_format": "text",
        # copilot CLI: `--effort/--reasoning-effort <level>` (none|low|medium|high|xhigh|max)
        "reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
        "default_effort": "medium",
    },
    "codex": {
        "cli_bin": "codex",
        "models": ["gpt-5-codex", "gpt-5"],
        "default_model": "gpt-5-codex",
        "output_format": "json",
    },
    "claude": {
        "cli_bin": "claude",
        # claude CLI has no model-list command; `--model` accepts an alias ('opus','sonnet',
        # 'haiku','fable') or a full name. Full current catalog (claude-api skill is authoritative).
        "models": [
            "claude-fable-5",
            "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
            "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-haiku-4-5",
        ],
        "default_model": "claude-sonnet-4-6",
        "output_format": "stream-json",
        # `claude --effort <level>` (일반망 확인). 미지원 agent는 이 키 생략.
        "reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
        "default_effort": "medium",
    },
    "opencode": {
        "cli_bin": "opencode",
        # Lists dynamically via `opencode models` (OpenCodeAdapter.list_models). These are
        # the real-provider static fallback. Default matches the original harness
        # (.deepx/e2e/test.sh: DX_AGENT_E2E_OPENCODE_MODEL=github-copilot/claude-sonnet-4.6).
        "models": ["github-copilot/claude-sonnet-4.6", "github-copilot/claude-opus-4.6",
                   "github-copilot/gpt-5.2"],
        "default_model": "github-copilot/claude-sonnet-4.6",
        "output_format": "text",
        # opencode CLI: `--variant <level>` (provider-specific reasoning effort).
        "reasoning_efforts": ["low", "medium", "high", "xhigh", "max"],
        "default_effort": "high",
    },
    "cursor": {
        "cli_bin": "cursor-agent",
        "models": ["auto", "sonnet-4.6", "gpt-5.3-codex", "gpt-5.3-codex-high"],
        "default_model": "auto",
        "output_format": "stream-json",
        # cursor-agent: effort via model bracket e.g. sonnet-4.6[effort=high]
        "reasoning_efforts": ["low", "medium", "high"],
        "default_effort": "medium",
    },
}

# session_id 짧은형 매핑(spec §10). 미등록 모델은 원문 사용.
MODEL_SHORT = {
    "claude-fable-5": "fable5",
    "claude-opus-4-8": "opus48",
    "claude-opus-4-7": "opus47",
    "claude-opus-4-6": "opus46",
    "claude-sonnet-4-6": "sonnet46",
    "claude-sonnet-4-5": "sonnet45",
    "claude-haiku-4-5": "haiku45",
    "gpt-5-codex": "gpt5codex",
    "gpt-5": "gpt5",
    "anthropic/claude-sonnet-4-6": "sonnet46",
    "openai/gpt-5": "gpt5",
    "sonnet-4.6": "sonnet46",
}
