"""Tests for formatter cell helpers, summary line, TableFormatter, and TextFormatter."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from project_monitor.formatters.table import (
    TableFormatter,
    _branch_cell,
    _commit_cell,
    _remote_cell,
    _status_cell,
    _summary_line,
)
from project_monitor.formatters.text import TextFormatter
from project_monitor.models import RepoInfo
from tests.conftest import capture_table


def _repo(**kwargs) -> RepoInfo:
    defaults: dict = {"name": "test-repo", "path": Path("/tmp/test"), "branch": "main"}
    defaults.update(kwargs)
    return RepoInfo(**defaults)


# ---------------------------------------------------------------------------
# _branch_cell
# ---------------------------------------------------------------------------


def test_branch_cell_normal():
    markup = _branch_cell(_repo(branch="feature/x"))
    assert "feature/x" in markup


def test_branch_cell_with_error():
    markup = _branch_cell(_repo(error="git failed"))
    assert "—" in markup
    assert "feature" not in markup


# ---------------------------------------------------------------------------
# _status_cell
# ---------------------------------------------------------------------------


def test_status_cell_clean():
    markup = _status_cell(_repo())
    assert "Clean" in markup


def test_status_cell_error():
    markup = _status_cell(_repo(error="timeout"))
    assert "Error" in markup


def test_status_cell_staged_only():
    markup = _status_cell(_repo(staged=2))
    assert "2 staged" in markup
    assert "modified" not in markup
    assert "untracked" not in markup


def test_status_cell_all_three():
    markup = _status_cell(_repo(staged=1, unstaged=2, untracked=3))
    assert "1 staged" in markup
    assert "2 modified" in markup
    assert "3 untracked" in markup


# ---------------------------------------------------------------------------
# _commit_cell
# ---------------------------------------------------------------------------


def test_commit_cell_with_hash():
    markup = _commit_cell(_repo(last_commit_hash="abc1234", last_commit_msg="fix bug"))
    assert "abc1234" in markup
    assert "fix bug" in markup


def test_commit_cell_no_hash():
    markup = _commit_cell(_repo(last_commit_hash=""))
    assert "—" in markup


def test_commit_cell_error():
    markup = _commit_cell(_repo(error="failed", last_commit_hash="abc1234"))
    assert "—" in markup


# ---------------------------------------------------------------------------
# _remote_cell
# ---------------------------------------------------------------------------


def test_remote_cell_no_remote():
    markup = _remote_cell(_repo(has_remote=False))
    assert "No remote" in markup


def test_remote_cell_in_sync():
    markup = _remote_cell(_repo(has_remote=True, ahead=0, behind=0))
    assert "In sync" in markup


def test_remote_cell_ahead_only():
    markup = _remote_cell(_repo(has_remote=True, ahead=3, behind=0))
    assert "↑3" in markup
    assert "↓" not in markup


def test_remote_cell_behind_only():
    markup = _remote_cell(_repo(has_remote=True, ahead=0, behind=2))
    assert "↓2" in markup
    assert "↑" not in markup


def test_remote_cell_diverged():
    markup = _remote_cell(_repo(has_remote=True, ahead=2, behind=1))
    assert "↑2" in markup
    assert "↓1" in markup


def test_remote_cell_error():
    markup = _remote_cell(_repo(error="git failed"))
    assert "—" in markup


# ---------------------------------------------------------------------------
# _summary_line
# ---------------------------------------------------------------------------


def test_summary_all_clean():
    repos = [_repo() for _ in range(3)]
    line = _summary_line(repos)
    assert "3 clean" in line


def test_summary_mixed():
    repos = [_repo(), _repo(staged=1), _repo(unstaged=1)]
    line = _summary_line(repos)
    assert "1 clean" in line
    assert "2 need attention" in line


def test_summary_with_errors():
    repos = [_repo(error="failed")]
    line = _summary_line(repos)
    assert "1 error" in line


def test_summary_total_count():
    repos = [_repo(), _repo(error="x"), _repo(staged=1)]
    line = _summary_line(repos)
    assert "3 repo" in line


# ---------------------------------------------------------------------------
# TableFormatter.render — full render
# ---------------------------------------------------------------------------


def test_render_empty_list():
    output = capture_table([])
    assert "No git repositories found" in output


def test_render_output_contains_repo_name():
    repo = RepoInfo(name="my-app", path=Path("/tmp/my-app"), branch="main")
    output = capture_table([repo])
    assert "my-app" in output


def test_render_ascii_mode():
    repo = RepoInfo(name="r", path=Path("/tmp/r"), branch="main")
    output = capture_table([repo])
    assert "+" in output or "|" in output  # ASCII box chars present


def test_render_shows_summary():
    repo = RepoInfo(name="r", path=Path("/tmp/r"), branch="main")
    output = capture_table([repo])
    assert "Found 1 repo" in output


# ---------------------------------------------------------------------------
# TableFormatter error-repo paths
# ---------------------------------------------------------------------------


def test_render_all_repos_have_errors():
    repos = [
        RepoInfo(name="bad1", path=Path("/tmp/bad1"), branch="?", error="timeout"),
        RepoInfo(name="bad2", path=Path("/tmp/bad2"), branch="?", error="not found"),
    ]
    output = capture_table(repos)
    assert "bad1" in output
    assert "bad2" in output
    assert "1 error" not in output  # two errors
    assert "2 error" in output


def test_render_mixed_error_and_clean():
    repos = [
        RepoInfo(name="ok", path=Path("/tmp/ok"), branch="main"),
        RepoInfo(name="bad", path=Path("/tmp/bad"), branch="?", error="timeout"),
    ]
    output = capture_table(repos)
    assert "ok" in output
    assert "bad" in output
    assert "1 error" in output


def test_render_error_repo_branch_shows_dash():
    repo = RepoInfo(name="r", path=Path("/tmp/r"), branch="some-branch", error="failed")
    markup = _branch_cell(repo)
    assert "some-branch" not in markup
    assert "—" in markup


def test_render_error_repo_remote_shows_dash():
    repo = RepoInfo(name="r", path=Path("/tmp/r"), branch="?", error="failed",
                    has_remote=True, ahead=5)
    markup = _remote_cell(repo)
    assert "—" in markup
    assert "↑" not in markup


def test_render_error_repo_commit_shows_dash():
    repo = RepoInfo(name="r", path=Path("/tmp/r"), branch="?", error="failed",
                    last_commit_hash="abc1234", last_commit_msg="msg")
    markup = _commit_cell(repo)
    assert "abc1234" not in markup
    assert "—" in markup


# ---------------------------------------------------------------------------
# TextFormatter
# ---------------------------------------------------------------------------


def test_text_formatter_writes_correct_content(tmp_path: Path):
    out_file = tmp_path / "status.txt"
    repo = RepoInfo(name="my-project", path=tmp_path, branch="main")
    TextFormatter(out_file).render([repo])
    content = out_file.read_text(encoding="utf-8")
    assert "my-project" in content
    assert "main" in content


def test_text_formatter_empty_repos(tmp_path: Path):
    out_file = tmp_path / "status.txt"
    TextFormatter(out_file).render([])
    content = out_file.read_text(encoding="utf-8")
    assert "No git repositories found" in content


def test_text_formatter_bad_path_raises(tmp_path: Path):
    bad_path = tmp_path / "nonexistent_dir" / "output.txt"
    with pytest.raises(OSError):
        TextFormatter(bad_path).render([])
