"""copilot -p 비대화형 어댑터(--add-dir 격리)."""
from dx_agent_dev.core.adapters.base import SubprocessAdapter


class CopilotAdapter(SubprocessAdapter):
    cli_bin = "copilot"
    # harness: cwd = target workdir so the agent discovers project CLAUDE.md + skills,
    # matching the original `cd "$_workdir" && copilot -i "$_prompt" --yolo ...`.
    cwd_mode = "harness"
    creds_relpath = (".copilot", "session-store.db")
    login_cmd_hint = "copilot  (first run opens GitHub device login)"

    def build_command(self, prompt, session_dir, harness_dirs, run_ctx=None):
        # --yolo: full tool autonomy (= original harness), supersedes granular --allow-tool.
        cmd = [self._cli, "-p", prompt, "--yolo", "--add-dir", str(session_dir)]
        for h in harness_dirs:
            cmd += ["--add-dir", str(h)]
        if self.model:
            cmd += ["--model", self.model]  # original: copilot -i ... --model "$AGENT_MODEL"
        if self.effort:
            cmd += ["--effort", self.effort]  # none|low|medium|high|xhigh|max
        # Autopilot: disable copilot's ask_user tool so the agent never blocks on user input.
        # claude/cursor/opencode already pass full-permission flags (--yolo / --dangerously-skip-permissions)
        # and rely on the autopilot prompt directive, so no extra flag is needed for those adapters.
        if run_ctx and getattr(run_ctx, "autopilot", False):
            cmd += ["--no-ask-user"]
        return cmd
