"""``.github/scripts/push_with_retry.sh``: a content conflict is won by this run's commit with PUSH_PREFER=ours (2.61.9)."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "push_with_retry.sh"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null"}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout


def _repos(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    a, b = tmp_path / "a", tmp_path / "b"
    git(tmp_path, "clone", "-q", str(remote), str(a))
    (a / "models.json").write_text("base\n")
    (a / "other.txt").write_text("base\n")
    git(a, "add", "-A")
    git(a, "commit", "-q", "-m", "base")
    git(a, "push", "-q", "origin", "HEAD:main")
    git(tmp_path, "clone", "-q", str(remote), str(b))  # b starts from the same base: the older run
    return remote, a, b


def test_without_a_conflict_the_default_still_pushes(tmp_path):
    remote, a, b = _repos(tmp_path)
    (a / "other.txt").write_text("from a\n")
    git(a, "commit", "-q", "-am", "a")
    git(a, "push", "-q", "origin", "HEAD:main")
    (b / "models.json").write_text("from b\n")  # another file: only a race, no conflict
    git(b, "commit", "-q", "-am", "b")
    r = subprocess.run(["bash", str(SCRIPT), "main"], cwd=b, env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert git(remote, "show", "main:models.json") == "from b\n" and git(remote, "show", "main:other.txt") == "from a\n"


def test_prefer_ours_resolves_the_conflict_of_two_runs_that_rewrote_the_same_file(tmp_path):
    remote, a, b = _repos(tmp_path)
    (a / "models.json").write_text("from the other run\n")
    git(a, "commit", "-q", "-am", "other run")
    git(a, "push", "-q", "origin", "HEAD:main")
    (b / "models.json").write_text("from this run\n")
    git(b, "commit", "-q", "-am", "this run")
    r = subprocess.run(["bash", str(SCRIPT), "main"], cwd=b, env={**ENV, "PUSH_PREFER": "ours"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert git(remote, "show", "main:models.json") == "from this run\n"


def test_prefer_ours_writes_this_runs_complete_files_not_a_mixture_of_hunks(tmp_path):
    """Codex review of 2.62.0: ``-X theirs`` kept the other run's non-conflicting hunks, so a regenerated report mixed two runs."""
    remote, a, b = _repos(tmp_path)
    rows = lambda vals: "".join(f"r{i},{v}\n" for i, v in enumerate(vals))  # noqa: E731
    (a / "report.csv").write_text(rows([1] * 10))
    git(a, "add", "-A")
    git(a, "commit", "-q", "-m", "report")
    git(a, "push", "-q", "origin", "HEAD:main")
    git(b, "pull", "-q", "origin", "main")
    (a / "report.csv").write_text(rows([2] + [1] * 8 + [2]))  # the other run: first and last row (the last is far from this run's changes)
    (a / "other.txt").write_text("from the other run\n")  # a file this run does not touch
    git(a, "commit", "-q", "-am", "other run")
    git(a, "push", "-q", "origin", "HEAD:main")
    mine = rows([3, 3] + [1] * 8)  # this run regenerated the whole file: its last row is 1
    (b / "report.csv").write_text(mine)
    git(b, "commit", "-q", "-am", "this run")
    r = subprocess.run(["bash", str(SCRIPT), "main"], cwd=b, env={**ENV, "PUSH_PREFER": "ours"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert git(remote, "show", "main:report.csv") == mine  # this run's file, not its first rows with the other run's last row
    assert git(remote, "show", "main:other.txt") == "from the other run\n"  # untouched files keep the remote's content
    assert git(remote, "log", "-1", "--format=%s", "main").strip() == "this run"


def test_prefer_ours_also_replays_a_deletion(tmp_path):
    remote, a, b = _repos(tmp_path)
    (a / "other.txt").write_text("from the other run\n")
    git(a, "commit", "-q", "-am", "other run")
    git(a, "push", "-q", "origin", "HEAD:main")
    git(b, "rm", "-q", "models.json")
    (b / "new.csv").write_text("n,1\n")
    git(b, "add", "-A")
    git(b, "commit", "-q", "-m", "this run")
    r = subprocess.run(["bash", str(SCRIPT), "main"], cwd=b, env={**ENV, "PUSH_PREFER": "ours"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    files = set(git(remote, "ls-tree", "--name-only", "main").split())
    assert files == {"other.txt", "new.csv"} and git(remote, "show", "main:other.txt") == "from the other run\n"

