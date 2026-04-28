"""Tests for git_ops: _parse_status, _parse_log, _run_git, get_repo_status, check_git_available."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from project_monitor.git_ops import (
    _parse_log,
    _parse_status,
    _run_git,
    check_git_available,
    get_repo_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal porcelain=v2 header lines used across multiple tests.
_BRANCH_MAIN = "# branch.oid abc1234\n# branch.head main\n"
_REMOTE_INSYNC = "# branch.upstream origin/main\n# branch.ab +0 -0\n"


def _make_run_result(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# ---------------------------------------------------------------------------
# _parse_status — happy paths
# ---------------------------------------------------------------------------


def test_parse_status_clean():
    raw = _BRANCH_MAIN + _REMOTE_INSYNC
    branch, ahead, behind, has_remote, staged, unstaged, untracked = _parse_status(raw)
    assert branch == "main"
    assert staged == unstaged == untracked == 0
    assert has_remote is True
    assert ahead == 0 and behind == 0


def test_parse_status_staged():
    raw = _BRANCH_MAIN + "1 M. N... 100644 100644 100644 aaa bbb file.txt\n"
    _, _, _, _, staged, unstaged, _ = _parse_status(raw)
    assert staged == 1
    assert unstaged == 0


def test_parse_status_unstaged():
    raw = _BRANCH_MAIN + "1 .M N... 100644 100644 100644 aaa bbb file.txt\n"
    _, _, _, _, staged, unstaged, _ = _parse_status(raw)
    assert staged == 0
    assert unstaged == 1


def test_parse_status_both_xy():
    raw = _BRANCH_MAIN + "1 MM N... 100644 100644 100644 aaa bbb file.txt\n"
    _, _, _, _, staged, unstaged, _ = _parse_status(raw)
    assert staged == 1
    assert unstaged == 1


def test_parse_status_untracked():
    raw = _BRANCH_MAIN + "? newfile.txt\n"
    _, _, _, _, _, _, untracked = _parse_status(raw)
    assert untracked == 1


def test_parse_status_ahead_behind():
    raw = _BRANCH_MAIN + "# branch.upstream origin/main\n# branch.ab +3 -1\n"
    _, ahead, behind, has_remote, _, _, _ = _parse_status(raw)
    assert ahead == 3
    assert behind == 1
    assert has_remote is True


def test_parse_status_no_remote():
    raw = _BRANCH_MAIN  # no upstream or ab lines
    _, ahead, behind, has_remote, _, _, _ = _parse_status(raw)
    assert has_remote is False
    assert ahead == 0
    assert behind == 0


def test_parse_status_upstream_only():
    raw = _BRANCH_MAIN + "# branch.upstream origin/main\n"
    _, ahead, behind, has_remote, _, _, _ = _parse_status(raw)
    assert has_remote is True
    assert ahead == 0
    assert behind == 0


def test_parse_status_detached_head():
    raw = "# branch.oid abc1234\n# branch.head (detached)\n"
    branch, *_ = _parse_status(raw)
    assert branch == "(detached)"


# ---------------------------------------------------------------------------
# _parse_status — error / malformed inputs
# ---------------------------------------------------------------------------


def test_parse_status_empty_string():
    result = _parse_status("")
    branch, ahead, behind, has_remote, staged, unstaged, untracked = result
    assert branch == "?"
    assert staged == unstaged == untracked == 0
    assert has_remote is False


def test_parse_status_malformed_ab_missing_field():
    raw = _BRANCH_MAIN + "# branch.ab +2\n"  # missing '-behind' part
    _, ahead, behind, has_remote, _, _, _ = _parse_status(raw)
    # should not raise; has_remote stays False because parsing failed
    assert has_remote is False


def test_parse_status_malformed_ab_not_int():
    raw = _BRANCH_MAIN + "# branch.ab +abc -xyz\n"
    _, ahead, behind, has_remote, _, _, _ = _parse_status(raw)
    assert has_remote is False
    assert ahead == 0 and behind == 0


def test_parse_status_unicode_replacement_chars():
    raw = _BRANCH_MAIN + "1 M. N... 100644 100644 100644 aaa bbb fi�le.txt\n"
    # must not raise
    _, _, _, _, staged, _, _ = _parse_status(raw)
    assert staged == 1


# ---------------------------------------------------------------------------
# _parse_log — happy paths
# ---------------------------------------------------------------------------


def test_parse_log_normal():
    commit_hash, msg = _parse_log("abc1234 fix auth bug")
    assert commit_hash == "abc1234"
    assert msg == "fix auth bug"


def test_parse_log_empty_string():
    commit_hash, msg = _parse_log("")
    assert commit_hash == ""
    assert msg == "(no commits)"


def test_parse_log_long_message_truncated():
    long_msg = "x" * 50
    _, msg = _parse_log(f"abc1234 {long_msg}")
    assert len(msg) == 40


def test_parse_log_hash_only():
    commit_hash, msg = _parse_log("abc1234")
    assert commit_hash == "abc1234"
    assert msg == ""


# ---------------------------------------------------------------------------
# _run_git — error paths (unit tests on the private helper)
# ---------------------------------------------------------------------------


def test_run_git_file_not_found(tmp_path: Path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        out, err = _run_git(["status"], tmp_path)
    assert out == ""
    assert "not found" in err


def test_run_git_timeout(tmp_path: Path):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5)):
        out, err = _run_git(["status"], tmp_path)
    assert out == ""
    assert "timed out" in err


def test_run_git_permission_error(tmp_path: Path):
    with patch("subprocess.run", side_effect=PermissionError("denied")):
        out, err = _run_git(["status"], tmp_path)
    assert out == ""
    assert "permission" in err.lower()


def test_run_git_generic_oserror(tmp_path: Path):
    with patch("subprocess.run", side_effect=BlockingIOError("too many open files")):
        out, err = _run_git(["status"], tmp_path)
    assert out == ""
    assert "OS error" in err


def test_run_git_nonzero_returncode(tmp_path: Path):
    mock_result = _make_run_result(returncode=128, stderr="not a git repository")
    with patch("subprocess.run", return_value=mock_result):
        out, err = _run_git(["status"], tmp_path)
    assert out == ""
    assert "not a git repository" in err


# ---------------------------------------------------------------------------
# get_repo_status — integration (subprocess mocked)
# ---------------------------------------------------------------------------


def _patch_run(status_stdout: str, log_stdout: str = "abc1234 init", log_rc: int = 0):
    """Return a patch context that feeds two subprocess.run calls in order."""
    status_result = _make_run_result(stdout=status_stdout)
    log_result = _make_run_result(stdout=log_stdout, returncode=log_rc,
                                  stderr="fatal: no commits" if log_rc else "")
    return patch("subprocess.run", side_effect=[status_result, log_result])


def test_get_repo_status_clean(tmp_path: Path):
    status_raw = _BRANCH_MAIN + _REMOTE_INSYNC
    with _patch_run(status_raw):
        info = get_repo_status(tmp_path)
    assert info.is_clean is True
    assert info.branch == "main"
    assert info.last_commit_hash == "abc1234"
    assert info.error is None


def test_get_repo_status_git_not_found(tmp_path: Path):
    with patch("subprocess.run", side_effect=FileNotFoundError):
        info = get_repo_status(tmp_path)
    assert info.error is not None
    assert "not found" in info.error


def test_get_repo_status_timeout(tmp_path: Path):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5)):
        info = get_repo_status(tmp_path)
    assert info.error is not None
    assert "timed out" in info.error


def test_get_repo_status_log_fails_gracefully(tmp_path: Path):
    """When git log fails (no commits yet), RepoInfo should have no error."""
    status_raw = _BRANCH_MAIN
    with _patch_run(status_raw, log_stdout="", log_rc=128):
        info = get_repo_status(tmp_path)
    assert info.error is None
    assert info.last_commit_msg == "(no commits)"


def test_get_repo_status_both_calls_fail(tmp_path: Path):
    """If git status itself fails, RepoInfo.error is set immediately."""
    status_result = _make_run_result(returncode=128, stderr="not a git repo")
    with patch("subprocess.run", return_value=status_result):
        info = get_repo_status(tmp_path)
    assert info.error == "not a git repo"


def test_get_repo_status_no_commits_repo(tmp_path: Path):
    """A brand-new repo with staged files but zero commits is handled cleanly."""
    status_raw = _BRANCH_MAIN + "1 A. N... 000000 100644 000000 000 abc staged.txt\n"
    with _patch_run(status_raw, log_stdout="", log_rc=128):
        info = get_repo_status(tmp_path)
    assert info.error is None
    assert info.staged == 1
    assert info.last_commit_msg == "(no commits)"


# ---------------------------------------------------------------------------
# check_git_available
# ---------------------------------------------------------------------------


def test_check_git_available_true():
    result = _make_run_result(returncode=0, stdout="git version 2.40.0")
    with patch("subprocess.run", return_value=result):
        assert check_git_available() is True


def test_check_git_available_false_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_git_available() is False


def test_check_git_available_false_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5)):
        assert check_git_available() is False


def test_check_git_available_false_nonzero():
    with patch("subprocess.run", return_value=_make_run_result(returncode=1)):
        assert check_git_available() is False
