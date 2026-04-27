"""Plain-text formatter for file export."""

from __future__ import annotations

import logging
from pathlib import Path

from project_monitor.formatters.table import TableFormatter
from project_monitor.models import RepoInfo

logger = logging.getLogger(__name__)


class TextFormatter:
    """Writes a plain-text (no ANSI) table to a file.

    Reuses TableFormatter with color disabled and directs output to the
    given file, so the column layout stays identical to the terminal view.

    Args:
        output_path: Path to the file to write (created or overwritten).
    """

    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path

    def render(self, repos: list[RepoInfo]) -> None:
        """Write a plain-text table to the configured output file."""
        logger.info("Writing plain-text output to %s", self._output_path)
        with open(self._output_path, "w", encoding="utf-8") as fh:
            TableFormatter(file=fh, use_color=False, ascii_only=True).render(repos)
        logger.info("Output written to %s (%d repos)", self._output_path, len(repos))
