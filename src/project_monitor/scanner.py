"""Locate git repositories inside a directory tree."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def scan_for_repos(root: Path, max_depth: int = 2) -> list[Path]:
    """Find git repositories inside *root*, up to *max_depth* levels deep.

    If *root* itself is a git repository it is returned immediately without
    recursing further. Otherwise every subdirectory is visited up to
    *max_depth* levels. Symlinks are never followed to avoid loops on
    Windows junctions or Unix symlinks.

    Args:
        root: Directory to start scanning from.
        max_depth: Maximum folder depth to traverse (1–3).

    Returns:
        Sorted list of absolute paths to discovered repository roots.
    """
    root = root.resolve()
    logger.debug("Scanning %s (max_depth=%d)", root, max_depth)

    if not root.is_dir():
        logger.warning("Root path is not a directory: %s", root)
        return []

    if (root / ".git").exists():
        logger.debug("Root itself is a git repo: %s", root)
        return [root]

    found: list[Path] = []
    _walk(root, current_depth=0, max_depth=max_depth, found=found)
    found.sort()
    logger.info("Found %d git repo(s) under %s", len(found), root)
    return found


def _walk(
    directory: Path,
    current_depth: int,
    max_depth: int,
    found: list[Path],
) -> None:
    if current_depth >= max_depth:
        return
    try:
        entries = list(os.scandir(directory))
    except OSError as exc:
        logger.debug("Cannot read directory %s: %s", directory, exc)
        return

    for entry in entries:
        if entry.is_symlink():
            logger.debug("Skipping symlink: %s", entry.path)
            continue
        if not entry.is_dir():
            continue
        child = Path(entry.path)
        if (child / ".git").exists():
            logger.debug("Found repo: %s", child)
            found.append(child)
        else:
            _walk(child, current_depth + 1, max_depth, found)
