"""End-to-end CLI tests using typer's CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from project_monitor.cli import app
from project_monitor.models import RepoInfo

runner = CliRunner(mix_stderr=False)


def _make_repo_dir(base: Path) -> Path:
    """Create a minimal fake git repo directory."""
    (base / ".git").mkdir(parents=True, exist_ok=True)
    return base


def _error_repo(path: Path) -> RepoInfo:
    return RepoInfo(name=path.name, path=path, branch="?", error="git timed out")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_cli_no_repos_exits_zero(tmp_path: Path):
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 0
    assert result.exception is None


def test_cli_default_path_is_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    # no crash — empty folder with no repos exits 0
    assert result.exit_code == 0
    assert result.exception is None


# ---------------------------------------------------------------------------
# Error-handling paths
# ---------------------------------------------------------------------------


def test_cli_all_repos_fail_git_still_renders(tmp_path: Path):
    """CLI renders a table even when every repo's git call fails."""
    _make_repo_dir(tmp_path / "broken-repo")

    with patch(
        "project_monitor.cli.get_repo_status",
        return_value=_error_repo(tmp_path / "broken-repo"),
    ):
        result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 0
    assert result.exception is None
    assert "broken-repo" in result.stdout


def test_cli_output_dir_not_writable(tmp_path: Path):
    """Writing to a path whose parent doesn't exist exits non-zero, no traceback."""
    _make_repo_dir(tmp_path / "repo")
    bad_output = str(tmp_path / "nonexistent_dir" / "out.txt")

    with patch("project_monitor.cli.get_repo_status") as mock_status:
        mock_status.return_value = RepoInfo(
            name="repo", path=tmp_path / "repo", branch="main"
        )
        result = runner.invoke(app, [str(tmp_path), "--output", bad_output])

    assert result.exit_code != 0
    # SystemExit is the expected exit mechanism; any other exception type is a bug
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_git_not_installed(tmp_path: Path):
    """If git is not on PATH the CLI prints a helpful message and exits 1."""
    with patch("project_monitor.cli.check_git_available", return_value=False):
        result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 1
    # SystemExit is the expected exit mechanism from typer.Exit()
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "git" in result.stderr.lower()
