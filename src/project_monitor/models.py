"""Public data model shared across scanner, git_ops, and formatters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoInfo:
    """All status information for a single git repository.

    This is the stable public contract between the data layer (scanner + git_ops)
    and the presentation layer (formatters). Third-party formatters should depend
    only on this dataclass.

    Args:
        name: Folder name of the repository.
        path: Absolute path to the repository root.
        branch: Current branch name (e.g. "main", "feature/x"). "HEAD" if detached.
        staged: Number of files staged for the next commit.
        unstaged: Number of tracked files with unstaged modifications.
        untracked: Number of untracked (new) files.
        last_commit_hash: Abbreviated commit hash (7 chars), or "" if no commits.
        last_commit_msg: Commit subject line, truncated to 40 chars.
        ahead: Commits ahead of the upstream remote branch.
        behind: Commits behind the upstream remote branch.
        has_remote: True if an upstream remote tracking branch is configured.
        error: Non-None if any git command failed; contains the error message.
        tag: Optional user-assigned label from the pmon tag store.
        date_added: ISO timestamp when this path was tagged, from the store.
    """

    name: str
    path: Path
    branch: str
    staged: int = 0
    unstaged: int = 0
    untracked: int = 0
    last_commit_hash: str = ""
    last_commit_msg: str = ""
    ahead: int = 0
    behind: int = 0
    has_remote: bool = False
    error: str | None = None
    tag: str | None = None
    date_added: str | None = None

    @property
    def is_clean(self) -> bool:
        """True when there are no staged, unstaged, or untracked changes."""
        return self.staged == 0 and self.unstaged == 0 and self.untracked == 0

    @property
    def total_changes(self) -> int:
        """Total number of changed files (staged + unstaged + untracked)."""
        return self.staged + self.unstaged + self.untracked
