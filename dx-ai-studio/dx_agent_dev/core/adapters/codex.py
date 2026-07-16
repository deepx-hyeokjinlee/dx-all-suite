"""codex exec --json 어댑터(cwd=harness, -C). NDJSON 라인 단위 스트리밍.

Codex는 ``exec --json`` 으로 thread/turn/item.* 이벤트를 실시간 출력한다.
_map_json_event 의 codex 분기(parse_codex_session 스키마)로 UI 슬롯에 매핑.
"""
import json

from dx_agent_dev.core.adapters.base import SubprocessAdapter, _map_json_event, classify_plain_line


class CodexAdapter(SubprocessAdapter):
    cli_bin = "codex"
    cwd_mode = "harness"

    def build_command(self, prompt, session_dir, harness_dirs, run_ctx=None):
        work = harness_dirs[0] if harness_dirs else session_dir
        cmd = [self._cli, "exec", prompt, "--json", "-s", "danger-full-access"]
        if self.model:
            cmd += ["-m", self.model]
        cmd += ["-C", str(work)]
        return cmd

    def normalize(self, line):
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError, TypeError):
            return classify_plain_line(line)
        return _map_json_event(obj, line)
