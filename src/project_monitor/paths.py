"""Runtime path constants for the ~/.p-mon/ home directory."""

from __future__ import annotations

from pathlib import Path

PMON_HOME = Path.home() / ".p-mon"
BIN_DIR = PMON_HOME / "bin"
LOGS_DIR = PMON_HOME / "logs"
DOCS_DIR = PMON_HOME / "docs"
DEFAULT_STORE = PMON_HOME / "tags.json"
DEFAULT_LOG = LOGS_DIR / "pmon.log"
LEGACY_STORE = Path.home() / ".pmon" / "tags.json"
