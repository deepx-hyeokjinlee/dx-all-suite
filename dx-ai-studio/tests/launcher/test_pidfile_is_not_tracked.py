"""launcher/.launcher_pids 는 저장소에 있으면 안 된다.

_cleanup_old_pids() 는 시작할 때 이 파일의 PID 를 이전 launcher 가 남긴 것으로 보고
process group 째 SIGTERM/SIGKILL 한다. b79f6cb 에서 실수로 커밋돼, 새로 clone 한
머신에서 launcher 를 처음 켜면 그 머신에서 같은 번호를 우연히 쓰고 있던 무관한
프로세스를 죽일 수 있었다.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIDFILE = "launcher/.launcher_pids"


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_pidfile_is_not_tracked():
    assert _git("ls-files", "--error-unmatch", PIDFILE).returncode != 0, (
        f"{PIDFILE} 가 git 에 추적되고 있다 — git rm --cached {PIDFILE}"
    )


def test_pidfile_is_ignored():
    assert _git("check-ignore", "-q", PIDFILE).returncode == 0, (
        f"{PIDFILE} 가 .gitignore 에 없다"
    )
