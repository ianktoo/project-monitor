"""Run git commands and return RepoInfo dataclasses."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from project_monitor.models import RepoInfo

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 5  # seconds per subprocess call


def get_repo_status(path: Path) -> RepoInfo:
    """Query git for the full status of a repository at *path*.

    Uses two subprocess calls (no shell=True, 5s timeout each):
      1. git status --porcelain=v2 --branch  →  branch, ahead/behind, file counts
      2. git log --oneline -1                →  last commit hash and message

    Args:
        path: Absolute path to a git repository root.

    Returns:
        A populated RepoInfo. If any git call fails, RepoInfo.error is set
        and numeric fields default to 0.
    """
    logger.debug("Getting status for repo: %s", path)
    name = path.name

    status_raw, status_err = _run_git(["status", "--porcelain=v2", "--branch"], path)
    if status_err:
        logger.warning("git status failed for %s: %s", path, status_err)
        return RepoInfo(name=name, path=path, branch="?", error=status_err)

    branch, ahead, behind, has_remote, staged, unstaged, untracked = _parse_status(status_raw)

    commit_raw, commit_err = _run_git(["log", "--oneline", "-1"], path)
    if commit_err:
        logger.debug("git log failed for %s (possibly no commits): %s", path, commit_err)
        commit_hash, commit_msg = "", "(no commits)"
    else:
        commit_hash, commit_msg = _parse_log(commit_raw)

    logger.debug(
        "Repo %s: branch=%s staged=%d unstaged=%d untracked=%d ahead=%d behind=%d",
        name,
        branch,
        staged,
        unstaged,
        untracked,
        ahead,
        behind,
    )

    return RepoInfo(
        name=name,
        path=path,
        branch=branch,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        last_commit_hash=commit_hash,
        last_commit_msg=commit_msg,
        ahead=ahead,
        behind=behind,
        has_remote=has_remote,
    )


def _run_git(args: list[str], cwd: Path) -> tuple[str, str]:
    """Run a git command and return (stdout, error_message).

    Never raises — errors are returned as the second element of the tuple.
    """
    cmd = ["git", "-C", str(cwd)] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT,
        )
        if result.returncode != 0:
            return "", result.stderr.strip()
        return result.stdout, ""
    except FileNotFoundError:
        return "", "git executable not found"
    except PermissionError:
        return "", "git permission denied"
    except subprocess.TimeoutExpired:
        return "", f"git command timed out after {_GIT_TIMEOUT}s"
    except OSError as exc:
        return "", f"OS error running git: {exc}"


def _parse_status(raw: str) -> tuple[str, int, int, bool, int, int, int]:
    """Parse git status --porcelain=v2 --branch output.

    Returns:
        (branch, ahead, behind, has_remote, staged, unstaged, untracked)
    """
    branch = "?"
    ahead = 0
    behind = 0
    has_remote = False
    staged = 0
    unstaged = 0
    untracked = 0

    for line in raw.splitlines():
        if line.startswith("# branch.head "):
            branch = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            # format: +<ahead> -<behind>
            parts = line.split(" ")
            try:
                ahead = int(parts[2].lstrip("+"))
                behind = abs(int(parts[3].lstrip("-")))
                has_remote = True
            except (IndexError, ValueError):
                pass
        elif line.startswith("# branch.upstream "):
            has_remote = True
        elif line.startswith("1 ") or line.startswith("2 "):
            # ordinary changed and renamed/copied entries; field[1] is XY flags
            xy = line.split(" ")[1]
            if xy[0] != ".":
                staged += 1
            if xy[1] != ".":
                unstaged += 1
        elif line.startswith("? "):
            untracked += 1

    return branch, ahead, behind, has_remote, staged, unstaged, untracked


def _parse_log(raw: str) -> tuple[str, str]:
    """Parse the first line of git log --oneline output into (hash, message)."""
    line = raw.strip()
    if not line:
        return "", "(no commits)"
    parts = line.split(" ", 1)
    commit_hash = parts[0][:7]
    commit_msg = parts[1][:40] if len(parts) > 1 else ""
    return commit_hash, commit_msg


def check_git_available() -> bool:
    """Return True if git is installed and reachable on PATH.

    Runs ``git --version`` with a short timeout.  Any failure — missing
    binary, permission error, timeout — returns False.
    """
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, OSError, subprocess.TimeoutExpired):
        return False
