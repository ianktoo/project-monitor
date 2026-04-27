"""Shared fixtures for the project-monitor test suite."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from project_monitor.formatters.table import TableFormatter
from project_monitor.models import RepoInfo


# ---------------------------------------------------------------------------
# RepoInfo fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_repo(tmp_path: Path) -> RepoInfo:
    return RepoInfo(
        name="clean-repo",
        path=tmp_path,
        branch="main",
        last_commit_hash="abc1234",
        last_commit_msg="initial commit",
        has_remote=True,
    )


@pytest.fixture
def dirty_repo(tmp_path: Path) -> RepoInfo:
    return RepoInfo(
        name="dirty-repo",
        path=tmp_path,
        branch="feature/x",
        staged=1,
        unstaged=2,
        untracked=3,
        last_commit_hash="def5678",
        last_commit_msg="wip changes",
        has_remote=True,
        ahead=1,
    )


@pytest.fixture
def error_repo(tmp_path: Path) -> RepoInfo:
    return RepoInfo(
        name="error-repo",
        path=tmp_path,
        branch="?",
        error="git command timed out after 5s",
    )


# ---------------------------------------------------------------------------
# Formatter capture helper
# ---------------------------------------------------------------------------


def capture_table(repos: list[RepoInfo], **kwargs) -> str:
    """Render repos to a string using TableFormatter (no color, ASCII boxes)."""
    buf = io.StringIO()
    TableFormatter(file=buf, use_color=False, ascii_only=True, **kwargs).render(repos)
    return buf.getvalue()
