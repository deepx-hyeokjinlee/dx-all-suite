# SPDX-License-Identifier: Apache-2.0
"""
Which repos ghes-sync covers.

`setup_remotes.sh` is config-driven: it iterates the `[repo NAME]` sections of
sync.conf. A submodule with no section is therefore not merely skipped — it
produces **no output at all**, which reads as "only that repo failed". That is
exactly how dx-modelzoo looked broken while it was in fact never configured.

These tests keep the covered set explicit and tied to the suite's actual
submodules, so adding a submodule without deciding its sync status fails here
instead of silently disappearing from the tool's output.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

# sync.conf ships with src_host / branch EMPTY on purpose; a developer's gitignored sync.override.conf
# fills them in locally. Tests must pass without that file, so supply the required settings via env
# and point --override at an empty file so a developer's override cannot leak in either.
_ENV = {**os.environ, "GHES_SYNC_SRC_HOST": "https://github.com/example-mirror-org", "GHES_SYNC_BRANCH": "feature/x"}


def _suite_root(start: Path) -> Path:
    cur = start.resolve()
    marker = Path(".deepx") / "tools" / "src" / "dx_agent_dev_gen" / "cli.py"
    for _ in range(10):
        if (cur / marker).is_file():
            return cur
        cur = cur.parent
    raise RuntimeError("suite root not found")


SUITE = _suite_root(Path(__file__).parent)
CONF = SUITE / "internal" / "tools" / "ghes-sync" / "sync.conf"
GITMODULES = SUITE / ".gitmodules"

SECTION_RE = re.compile(r"^\[repo ([^\]]+)\]", re.M)


def conf_text() -> str:
    return CONF.read_text(encoding="utf-8")


def conf_sections() -> list:
    return SECTION_RE.findall(conf_text())


def test_dx_modelzoo_is_configured():
    assert "dx-modelzoo" in conf_sections(), (
        "dx-modelzoo has no [repo] section, so setup_remotes.sh never visits it "
        "and prints nothing for it"
    )


def test_every_suite_submodule_is_covered():
    """Every submodule of the suite must have a sync.conf section — otherwise
    the tool is silent about it. Only the suite's top-level .gitmodules is read:
    nested submodules (dx_app / dx_stream under dx-runtime) are listed in
    dx-runtime/.gitmodules and are covered by their own [repo] sections."""
    names = re.findall(r'^\[submodule "([^"]+)"\]', GITMODULES.read_text(encoding="utf-8"), re.M)
    missing = sorted(set(names) - set(conf_sections()))
    assert not missing, (
        "submodules absent from sync.conf (setup_remotes.sh will not report "
        "them at all): %s" % missing
    )


def test_nested_repos_precede_the_parent_that_gitlinks_them():
    """sync.conf's own documented rule: 'Section order = processing order:
    nested repos BEFORE the parent whose gitlinks point at them.'"""
    text = conf_text()
    suite_at = text.index("[repo dx-all-suite]")
    for name in ("dx-runtime", "dx-compiler", "dx-modelzoo"):
        assert text.index("[repo %s]" % name) < suite_at, (
            "%s must be declared before [repo dx-all-suite]" % name
        )


def test_suite_gitlinks_list_every_direct_submodule():
    """Read the submodules from .gitmodules rather than a hand-kept list — that list is
    how dx-k8s-device-plugin (#104) stayed invisible until the coverage test caught it.
    A repo configured `sync = off` is exempt: it is never fetched, so its cache cannot
    hold the pointer and a strict gitlink check could never pass."""
    text = conf_text()
    suite_section = text.split("[repo dx-all-suite]", 1)[1]
    names = re.findall(r'^\[submodule "([^"]+)"\]', GITMODULES.read_text(encoding="utf-8"), re.M)
    missing = [n for n in names
               if "%s:%s" % (n, n) not in suite_section and not _is_sync_off(n)]
    assert not missing, "dx-all-suite gitlinks must include %s" % missing


def test_print_config_enumerates_dx_modelzoo(tmp_path):
    """The parsed config — not just the file — must carry the repo, with both
    remote URLs derived."""
    empty_override = tmp_path / "empty.override.conf"   # --override must be a real file
    empty_override.write_text("", encoding="utf-8")
    proc = subprocess.run(
        [
            "bash",
            str(SUITE / "internal" / "tools" / "ghes-sync" / "ghes-sync.sh"),
            "--config",
            str(CONF),
            "--override",
            str(empty_override),
            "--print-config",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(SUITE),
        env=_ENV,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # --print-config emits bare repo names: `[dx-modelzoo]`, not `[repo ...]`
    assert "[dx-modelzoo]" in proc.stdout, proc.stdout
    section = proc.stdout.split("[dx-modelzoo]", 1)[1].split("\n[", 1)[0]
    assert "src_url = " in section and "dst_url = " in section
    assert "path = dx-modelzoo" in section


def test_setup_remotes_dry_run_reports_dx_modelzoo():
    """The end-to-end symptom that started this: dx-modelzoo must now appear in
    setup_remotes.sh output instead of being silently absent."""
    repo = SUITE / "dx-modelzoo"
    if not (repo / ".git").exists():
        pytest.skip("dx-modelzoo submodule not initialised")
    proc = subprocess.run(
        [
            "bash",
            str(SUITE / "internal" / "tools" / "ghes-sync" / "setup_remotes.sh"),
            "--suite-dir",
            str(SUITE),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(SUITE),
        env=_ENV,
    )
    out = proc.stdout + proc.stderr
    assert "dx-modelzoo" in out, "setup_remotes.sh is still silent about dx-modelzoo:\n" + out


# ── dx-runtime's own submodules ──────────────────────────────────────────────

def _section(name: str) -> str:
    text = conf_text()
    return text.split("[repo %s]" % name, 1)[1].split("\n[repo ", 1)[0]


def test_dx_rt_and_driver_are_configured():
    """dx_rt / dx_rt_npu_linux_driver are never edited here, but the mirror still
    has to receive GHES's latest — they need sections like any other sub-repo."""
    for name in ("dx_rt", "dx_rt_npu_linux_driver"):
        assert name in conf_sections(), "%s has no [repo] section" % name


def test_dx_fw_is_ghcloud_only():
    """dx_fw's source is GHES-only and its fw.bin is public-channel-only: neither
    side of the mirror sync is the right source, so it is sync = off + ghcloud_url."""
    sec = _section("dx_fw")
    assert re.search(r"^sync\s*=\s*off", sec, re.M), sec
    assert re.search(r"^ghcloud_url\s*=\s*https://github\.com/DEEPX-AI/dx_fw\.git", sec, re.M), sec
    assert re.search(r"^path\s*=\s*dx-runtime/dx_fw", sec, re.M), sec


def test_dx_runtime_gitlinks_cover_its_synced_submodules_but_not_dx_fw():
    """A gitlink entry makes the parent's push wait for that sub-repo's cache.
    dx_fw's gitlink is a GHES commit that the ghcloud mirror never contains, so
    listing it would block every dx-runtime push for good."""
    sec = _section("dx-runtime")
    for name in ("dx_app", "dx_stream", "dx_rt", "dx_rt_npu_linux_driver"):
        assert "%s:%s" % (name, name) in sec, "dx-runtime gitlinks must include %s" % name
    assert "dx_fw:dx_fw" not in sec, "dx_fw must NOT be a gitlink target (its pointer is unreachable here)"


def _is_sync_off(name: str) -> bool:
    text = conf_text()
    if "[repo %s]" % name not in text:
        return False
    section = text.split("[repo %s]" % name, 1)[1].split("\n[repo ", 1)[0]
    return bool(re.search(r"^sync\s*=\s*off", section, re.M))


def test_dx_k8s_device_plugin_is_synced():
    """It has a repo in the mirror org, so it syncs like any other submodule."""
    assert "dx-k8s-device-plugin" in conf_sections()
    assert not _is_sync_off("dx-k8s-device-plugin"), "it has a mirror counterpart — do not disable it"
    assert re.search(r"^path\s*=\s*dx-k8s-device-plugin",
                     _section("dx-k8s-device-plugin"), re.M), _section("dx-k8s-device-plugin")
