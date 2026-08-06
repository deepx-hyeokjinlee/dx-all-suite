import subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]  # dx-ai-studio/


def test_launcher_sh_sets_debug_env_and_help():
    src = (ROOT / "launcher.sh").read_text(encoding="utf-8")
    assert "--debug)" in src and 'export DX_STUDIO_DEBUG=1' in src
    assert "--debug=" in src
    assert "--debug" in src.split("Usage:", 1)[-1][:400]


def test_gitignore_excludes_debug_log_dir():
    gi = (ROOT / ".gitignore")
    assert gi.exists(), ".gitignore must exist"
    assert "var/log/" in gi.read_text(encoding="utf-8")


def test_debug_flag_actually_exports(tmp_path):
    script = ROOT / "launcher.sh"
    harness = ("set -e; DX_STUDIO_DEBUG=; "
               "while [[ \"$#\" -gt 0 ]]; do case \"$1\" in "
               "--debug=*) export DX_STUDIO_DEBUG=1; export DX_STUDIO_DEBUG_LOG=\"${1#*=}\"; shift ;; "
               "--debug) export DX_STUDIO_DEBUG=1; shift ;; *) shift ;; esac; done; "
               "echo \"$DX_STUDIO_DEBUG:$DX_STUDIO_DEBUG_LOG\"")
    s = script.read_text(encoding="utf-8")
    assert "--debug=*)" in s and "--debug)" in s
    out = subprocess.run(["bash", "-c", harness, "_", "--debug=/tmp/x.log"],
                         capture_output=True, text=True).stdout.strip()
    assert out == "1:/tmp/x.log"
