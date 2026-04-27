"""Tests for RepoInfo dataclass properties."""

from __future__ import annotations

from pathlib import Path

from project_monitor.models import RepoInfo


def _repo(**kwargs) -> RepoInfo:
    return RepoInfo(name="test", path=Path("/tmp/test"), branch="main", **kwargs)


# ---------------------------------------------------------------------------
# is_clean
# ---------------------------------------------------------------------------


def test_is_clean_when_all_zero():
    assert _repo().is_clean is True


def test_is_dirty_when_staged():
    assert _repo(staged=1).is_clean is False


def test_is_dirty_when_unstaged():
    assert _repo(unstaged=1).is_clean is False


def test_is_dirty_when_untracked():
    assert _repo(untracked=1).is_clean is False


# ---------------------------------------------------------------------------
# total_changes
# ---------------------------------------------------------------------------


def test_total_changes_sum():
    assert _repo(staged=1, unstaged=2, untracked=3).total_changes == 6


def test_total_changes_zero():
    assert _repo().total_changes == 0
