# SPDX-License-Identifier: Apache-2.0
"""Network-free fixtures for ghes-sync.sh: local bare repos stand in for the
github.com mirror (src) and the GHES (dst); a fake `gh` on PATH records every
invocation and answers `pr list` / `pr create` with canned output."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def _suite_root(start: Path) -> Path:
    cur = start.resolve()
    marker = Path(".deepx") / "tools" / "src" / "dx_agent_dev_gen" / "cli.py"
    for _ in range(10):
        if (cur / marker).is_file():
            return cur
        cur = cur.parent
    raise RuntimeError("suite root not found")


SUITE = _suite_root(Path(__file__))
TOOL = SUITE / "internal" / "tools" / "ghes-sync" / "ghes-sync.sh"
GIT_ID = ["-c", "user.email=t@example.com", "-c", "user.name=t"]


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *GIT_ID, *args], cwd=cwd, text=True, capture_output=True, check=check)


class Repos:
    """`src/<name>.git` and `dst/<name>.git` bare repos + scratch worktrees."""

    def __init__(self, root: Path):
        self.root = root
        self.src = root / "src"
        self.dst = root / "dst"
        self.work = root / "work"
        for d in (self.src, self.dst, self.work):
            d.mkdir(parents=True, exist_ok=True)

    def bare(self, side: str, name: str) -> Path:
        return (self.src if side == "src" else self.dst) / f"{name}.git"

    def url(self, side: str, name: str) -> str:
        return f"file://{self.bare(side, name)}"

    def make(self, *names: str) -> None:
        for n in names:
            for side in ("src", "dst"):
                git("init", "-q", "--bare", str(self.bare(side, n)))

    def rev(self, side: str, name: str, ref: str) -> str | None:
        r = git("rev-parse", "--verify", "-q", ref, cwd=self.bare(side, name), check=False)
        return r.stdout.strip() or None

    def commit(self, side: str, name: str, branch: str, msg: str, *,
               files: dict | None = None, gitlinks: dict | None = None,
               parent_branch: str | None = None, tag: str | None = None) -> str:
        """Append a commit to <side>/<name>.git:<branch>. Starts the branch
        from *parent_branch* (or as an orphan) when it does not exist yet.
        *gitlinks* = {path: sha} recorded as mode-160000 entries (the pointed
        commit need not exist — exactly like a superproject)."""
        bare = self.bare(side, name)
        wt = Path(tempfile.mkdtemp(prefix=f"{side}-{name}-", dir=self.work))
        git("init", "-q", str(wt))
        base = branch if self.rev(side, name, f"refs/heads/{branch}") else parent_branch
        if base and self.rev(side, name, f"refs/heads/{base}"):
            git("fetch", "-q", f"file://{bare}", f"+refs/heads/{base}:refs/remotes/o/{base}", cwd=wt)
            git("checkout", "-q", "-b", branch, f"refs/remotes/o/{base}", cwd=wt)
        else:
            git("symbolic-ref", "HEAD", f"refs/heads/{branch}", cwd=wt)
        for rel, content in (files or {}).items():
            p = wt / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        if files:
            git("add", "-A", cwd=wt)
        for path, sha in (gitlinks or {}).items():
            git("update-index", "--add", "--cacheinfo", f"160000,{sha},{path}", cwd=wt)
        git("commit", "-q", "--allow-empty", "-m", msg, cwd=wt)
        if tag:
            git("tag", tag, cwd=wt)
        git("push", "-q", "-f", f"file://{bare}", f"refs/heads/{branch}:refs/heads/{branch}", cwd=wt)
        if tag:
            git("push", "-q", "-f", f"file://{bare}", f"refs/tags/{tag}:refs/tags/{tag}", cwd=wt)
        return git("rev-parse", "HEAD", cwd=wt).stdout.strip()

    def mirror_branch(self, name: str, branch: str) -> None:
        """Copy src:<branch> to dst:<branch> (fixture shortcut for 'already synced')."""
        git("fetch", "-q", self.url("src", name), f"+refs/heads/{branch}:refs/heads/{branch}",
            cwd=self.bare("dst", name))


class Env:
    def __init__(self, tmp_path: Path):
        self.tmp = tmp_path
        self.repos = Repos(tmp_path / "repos")
        self.cache = tmp_path / "cache"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.gh_log = tmp_path / "gh.log"
        self.gh_prs = tmp_path / "gh_prs.json"
        self.gh_prs.write_text("[]", encoding="utf-8")
        self.conf = tmp_path / "sync.conf"
        self._install_fake_gh()

    def _install_fake_gh(self) -> None:
        gh = self.bin / "gh"
        gh.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> '{self.gh_log}'\n"
            'case "$1 $2" in\n'
            f"  'pr list') cat '{self.gh_prs}';;\n"
            "  'pr create') echo 'https://gh.example/deepx/x/pull/42';;\n"
            "  *) exit 0;;\n"
            "esac\n"
        )
        gh.chmod(0o755)

    def remove_fake_gh(self) -> None:
        (self.bin / "gh").unlink()

    def install_fake_curl(self, list_json: str = "[]") -> tuple:
        """Emulate the two REST calls the tool makes: GET (list) -> `[]` + 200,
        POST (create) -> a PR JSON + 201. Logs argv to curl.log and copies any
        `-K` config file (where the Authorization header lives) to curl.cfg."""
        log = self.tmp / "curl.log"; cfg = self.tmp / "curl.cfg"
        shim = self.bin / "curl"
        shim.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' \"$*\" >> '{log}'\n"
            "out=''; post=0; prev=''\n"
            'for a in "$@"; do\n'
            f"  [ \"$prev\" = -K ] && cat \"$a\" >> '{cfg}'\n"
            '  [ "$prev" = -o ] && out="$a"\n'
            '  [ "$a" = POST ] && post=1\n'
            '  prev="$a"\n'
            "done\n"
            'if [ "$post" -eq 1 ]; then\n'
            "  [ -n \"$out\" ] && printf '%s' '{\"url\":\"x\",\"id\":1,\"number\":5,\"html_url\":\"https://ghes.example/deepx/dx_app/pull/5\"}' > \"$out\"\n"
            "  printf '201'\n"
            "else\n"
            f"  [ -n \"$out\" ] && printf '%s' '{list_json}' > \"$out\"\n"
            "  printf '200'\n"
            "fi\n"
        )
        shim.chmod(0o755)
        return log, cfg

    def set_open_prs(self, prs: list) -> None:
        self.gh_prs.write_text(json.dumps(prs), encoding="utf-8")

    def gh_calls(self) -> list[str]:
        return self.gh_log.read_text(encoding="utf-8").splitlines() if self.gh_log.exists() else []

    def write_conf(self, repos: list, *, branch: str = "feature/x", pr_base: str = "main",
                   mode: str = "pr", extra_defaults: str = "") -> Path:
        """repos = [(name, "key = value\\n..."), ...] in processing order."""
        lines = [
            "[defaults]",
            f"src_host = file://{self.repos.src}",
            f"dst_host = file://{self.repos.dst}",
            f"branch = {branch}",
            f"pr_base = {pr_base}",
            f"mode = {mode}",
            f"cache_dir = {self.cache}",
            extra_defaults,
        ]
        for name, body in repos:
            lines.append(f"[repo {name}]")
            if body:
                lines.append(body.strip())
        self.conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.conf

    def install_fake_git(self) -> Path:
        """Log every git invocation (argv + GIT_TERMINAL_PROMPT) to git.log, then run the real git."""
        real = shutil.which("git")
        log = self.tmp / "git.log"
        shim = self.bin / "git"
        shim.write_text(
            "#!/usr/bin/env bash\n"
            f"printf 'GTP=%s | %s\\n' \"${{GIT_TERMINAL_PROMPT-unset}}\" \"$*\" >> '{log}'\n"
            f"exec '{real}' \"$@\"\n"
        )
        shim.chmod(0o755)
        return log

    # Tools the script (and the shims' `#!/usr/bin/env bash`) need when PATH is reduced to hide `gh`.
    SHADOW_TOOLS = ("bash", "sh", "git", "awk", "grep", "sed", "mktemp", "base64", "tr", "head", "tail",
                    "cat", "rm", "chmod", "mkdir", "cut", "sleep", "timeout", "env", "wc", "dirname",
                    "basename", "date", "readlink", "ls", "cp", "mv", "touch", "true", "false", "test", "tar")

    def shadow_bin(self) -> Path:
        """A bin dir with symlinks to every needed tool EXCEPT gh — emulates a
        machine without the gh CLI (Windows git bash) without touching the real one."""
        d = self.tmp / "shadow"
        if not d.exists():
            d.mkdir()
            for t in self.SHADOW_TOOLS:
                real = shutil.which(t)
                if real:
                    (d / t).symlink_to(real)
        return d

    def run(self, *args: str, timeout: int = 120, extra_env: dict | None = None,
            hide_gh: bool = False) -> subprocess.CompletedProcess:
        path = f"{self.bin}:{self.shadow_bin()}" if hide_gh else f"{self.bin}:{os.environ['PATH']}"
        env = {**os.environ, "PATH": path}
        env.pop("GIT_TERMINAL_PROMPT", None)          # the tool itself must set it
        # Tests pin the Korean wording; force it regardless of the runner's locale. A test that wants the
        # locale to decide passes extra_env={"GHES_SYNC_LANG": ""} (empty = unset for the tool).
        env.setdefault("GHES_SYNC_LANG", "ko")
        env.update(extra_env or {})
        return subprocess.run(["bash", str(TOOL), "--config", str(self.conf), *args],
                              text=True, capture_output=True, timeout=timeout, env=env)


@pytest.fixture
def env(tmp_path) -> Env:
    return Env(tmp_path)


def out(r: subprocess.CompletedProcess) -> str:
    return r.stdout + r.stderr
