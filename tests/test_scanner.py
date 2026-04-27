"""Tests for scanner.scan_for_repos."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from project_monitor.scanner import scan_for_repos


def _make_repo(base: Path, *parts: str) -> Path:
    """Create a fake git repo at base/parts by making a .git directory."""
    repo = base.joinpath(*parts)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir()
    return repo


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_root_is_a_repo(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    result = scan_for_repos(tmp_path)
    assert result == [tmp_path.resolve()]


def test_finds_repos_depth_1(tmp_path: Path):
    repo = _make_repo(tmp_path, "proj-a")
    result = scan_for_repos(tmp_path)
    assert repo.resolve() in result


def test_finds_repos_depth_2(tmp_path: Path):
    repo = _make_repo(tmp_path, "org", "proj-b")
    result = scan_for_repos(tmp_path, max_depth=2)
    assert repo.resolve() in result


def test_depth_limit_respected(tmp_path: Path):
    _make_repo(tmp_path, "org", "proj-b")
    result = scan_for_repos(tmp_path, max_depth=1)
    assert result == []


def test_results_sorted(tmp_path: Path):
    zebra = _make_repo(tmp_path, "zebra")
    alpha = _make_repo(tmp_path, "alpha")
    result = scan_for_repos(tmp_path)
    assert result == sorted([alpha.resolve(), zebra.resolve()])


def test_empty_folder_returns_empty(tmp_path: Path):
    assert scan_for_repos(tmp_path) == []


def test_does_not_recurse_into_repos(tmp_path: Path):
    repo = _make_repo(tmp_path, "proj")
    _make_repo(tmp_path, "proj", "sub")  # nested inside proj/
    result = scan_for_repos(tmp_path)
    assert result == [repo.resolve()]  # only the outer repo


def test_non_directory_root_returns_empty(tmp_path: Path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    assert scan_for_repos(f) == []


def test_skips_symlinks(tmp_path: Path):
    real = _make_repo(tmp_path, "real")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform/user")

    result = scan_for_repos(tmp_path)
    # real repo found once; symlink must not add a duplicate
    assert result == [real.resolve()]


# ---------------------------------------------------------------------------
# Error-handling tests
# ---------------------------------------------------------------------------


def test_permission_denied_dir_skipped(tmp_path: Path):
    """A PermissionError on a subdirectory is silently skipped."""
    good = _make_repo(tmp_path, "good-repo")

    original_scandir = __import__("os").scandir

    def selective_scandir(path):
        if Path(path) == tmp_path / "locked":
            raise PermissionError("access denied")
        return original_scandir(path)

    (tmp_path / "locked").mkdir()
    with patch("project_monitor.scanner.os.scandir", side_effect=selective_scandir):
        result = scan_for_repos(tmp_path)

    assert good.resolve() in result  # good repo still found


def test_oserror_on_scandir_skipped(tmp_path: Path):
    """Any OSError (e.g. too many open files) on a directory is silently skipped."""
    with patch("project_monitor.scanner.os.scandir", side_effect=OSError("too many open files")):
        result = scan_for_repos(tmp_path)
    assert result == []


def test_git_as_file_counts_as_repo(tmp_path: Path):
    """.git as a plain file (worktree / submodule) is still recognised as a repo."""
    child = tmp_path / "submodule"
    child.mkdir()
    (child / ".git").write_text("gitdir: ../.git/modules/submodule")
    result = scan_for_repos(tmp_path)
    assert child.resolve() in result


def test_nonexistent_path_returns_empty(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    assert scan_for_repos(missing) == []
