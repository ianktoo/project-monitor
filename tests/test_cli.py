"""End-to-end CLI tests using typer's CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from project_monitor.cli import app
from project_monitor.models import RepoInfo
from project_monitor.store import TagStore

runner = CliRunner()


def _make_repo_dir(base: Path) -> Path:
    """Create a minimal fake git repo directory."""
    (base / ".git").mkdir(parents=True, exist_ok=True)
    return base


def _error_repo(path: Path) -> RepoInfo:
    return RepoInfo(name=path.name, path=path, branch="?", error="git timed out")


def _clean_repo(path: Path, tag: str | None = None) -> RepoInfo:
    return RepoInfo(name=path.name, path=path, branch="main", tag=tag)


# ---------------------------------------------------------------------------
# Happy paths


def test_cli_no_repos_exits_zero(tmp_path: Path):
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 0
    assert result.exception is None


def test_cli_default_path_is_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert result.exception is None


def test_cli_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.3.2" in result.output


# ---------------------------------------------------------------------------
# Error-handling paths


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
    assert "broken-repo" in result.output


def test_cli_output_dir_not_writable(tmp_path: Path):
    _make_repo_dir(tmp_path / "repo")
    bad_output = str(tmp_path / "nonexistent_dir" / "out.txt")

    with patch("project_monitor.cli.get_repo_status") as mock_status:
        mock_status.return_value = RepoInfo(
            name="repo", path=tmp_path / "repo", branch="main"
        )
        result = runner.invoke(app, [str(tmp_path), "--output", bad_output])

    assert result.exit_code != 0
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_git_not_installed(tmp_path: Path):
    with patch("project_monitor.cli.check_git_available", return_value=False):
        result = runner.invoke(app, [str(tmp_path)])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "git" in result.output.lower()


# ---------------------------------------------------------------------------
# --tag: single project tagging


def test_cli_tag_current_dir(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    store_path = tmp_path / "store.json"

    with patch("project_monitor.cli.TagStore") as MockStore:
        instance = MockStore.return_value
        result = runner.invoke(app, ["--tag", "work"])

    assert result.exit_code == 0
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_tag_explicit_path(tmp_path: Path):
    target = tmp_path / "my-project"
    target.mkdir()
    (target / ".git").mkdir()
    store_path = tmp_path / "store.json"
    store = TagStore(store_path=store_path)

    with patch("project_monitor.cli.TagStore", return_value=store):
        result = runner.invoke(app, ["--tag", "personal", "--path", str(target)])

    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    assert store.get_tag(target) == "personal"


def test_cli_tag_nonexistent_path_exits_nonzero(tmp_path: Path):
    ghost = str(tmp_path / "does-not-exist")
    result = runner.invoke(app, ["--tag", "x", "--path", ghost])
    assert result.exit_code != 0


def test_cli_tag_empty_string_exits_nonzero(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    result = runner.invoke(app, ["--tag", "   "])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# --tag + --folder: bulk tagging


def test_cli_bulk_tag_folder(tmp_path: Path):
    for name in ("repo-a", "repo-b", "repo-c"):
        _make_repo_dir(tmp_path / name)
    store_path = tmp_path / "store.json"
    store = TagStore(store_path=store_path)

    with patch("project_monitor.cli.TagStore", return_value=store):
        result = runner.invoke(app, ["--tag", "myteam", "--folder", str(tmp_path)])

    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    assert store.filter_by_tag("myteam")


def test_cli_bulk_tag_empty_folder_exits_zero(tmp_path: Path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["--tag", "x", "--folder", str(empty)])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --global: view tagged projects


def test_cli_global_no_tagged_projects(tmp_path: Path):
    store = TagStore(store_path=tmp_path / "store.json")
    with patch("project_monitor.cli.TagStore", return_value=store):
        result = runner.invoke(app, ["--global"])
    assert result.exit_code == 0
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_global_shows_tagged_projects(tmp_path: Path):
    repo = _make_repo_dir(tmp_path / "my-app")
    store = TagStore(store_path=tmp_path / "store.json")
    store.add(repo, "work")

    with patch("project_monitor.cli.TagStore", return_value=store), patch(
        "project_monitor.cli.get_repo_status",
        return_value=_clean_repo(repo, tag="work"),
    ), patch("project_monitor.cli.check_git_available", return_value=True):
        result = runner.invoke(app, ["--global"])

    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    assert "my-app" in result.output


def test_cli_global_local_mode_no_git_needed(tmp_path: Path):
    repo = tmp_path / "my-app"
    repo.mkdir()
    store = TagStore(store_path=tmp_path / "store.json")
    store.add(repo, "work")

    with patch("project_monitor.cli.TagStore", return_value=store):
        result = runner.invoke(app, ["--global", "--local"])

    assert result.exit_code == 0 or isinstance(result.exception, SystemExit)
    assert "my-app" in result.output


# ---------------------------------------------------------------------------
# --local: local scan view


def test_cli_local_flag_renders_without_remote(tmp_path: Path):
    _make_repo_dir(tmp_path / "my-repo")

    with patch(
        "project_monitor.cli.get_repo_status",
        return_value=_clean_repo(tmp_path / "my-repo"),
    ), patch("project_monitor.cli.check_git_available", return_value=True):
        result = runner.invoke(app, [str(tmp_path), "--local"])

    assert result.exit_code == 0
    assert "my-repo" in result.output
    assert "Remote" not in result.output


# ---------------------------------------------------------------------------
# --all: merge tagged + scanned


def test_cli_all_includes_tagged_repos(tmp_path: Path):
    scanned = _make_repo_dir(tmp_path / "scanned")
    ext = tmp_path / "extrepo"
    ext.mkdir()
    (ext / ".git").mkdir()

    store = TagStore(store_path=tmp_path / "store.json")
    store.add(ext, "external")

    def fake_status(p: Path) -> RepoInfo:
        return _clean_repo(p)

    with patch("project_monitor.cli.TagStore", return_value=store), patch(
        "project_monitor.cli.get_repo_status", side_effect=fake_status
    ), patch("project_monitor.cli.check_git_available", return_value=True):
        result = runner.invoke(app, [str(tmp_path), "--all"])

    assert result.exit_code == 0
    # Both repos found (tagged extra is inside tmp_path so also caught by scan)
    assert "Found 2 repo(s)" in result.output
    assert "scanned" in result.output
