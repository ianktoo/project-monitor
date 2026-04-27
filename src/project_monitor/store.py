"""Persistent tag store — maps project paths to user-defined labels."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_STORE = Path.home() / ".pmon" / "tags.json"


class TagStore:
    """JSON-backed store at ~/.pmon/tags.json.

    Each entry maps an absolute path string to metadata:
      { "tag": "...", "name": "...", "added_at": "ISO-timestamp" }
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self._path = store_path if store_path is not None else _DEFAULT_STORE
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as fh:
                raw = json.load(fh)
            self._data = raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read tag store %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, default=str)
        except OSError as exc:
            logger.error("Failed to save tag store %s: %s", self._path, exc)
            raise

    def add(self, path: Path, tag: str) -> None:
        """Tag *path* with *tag*, overwriting any existing tag."""
        key = str(path.resolve())
        self._data[key] = {
            "tag": tag,
            "name": path.resolve().name,
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save()

    def remove(self, path: Path) -> bool:
        """Remove the tag for *path*. Returns True if an entry existed."""
        key = str(path.resolve())
        if key not in self._data:
            return False
        del self._data[key]
        self._save()
        return True

    def get_tag(self, path: Path) -> str | None:
        """Return the tag for *path*, or None if not tagged."""
        entry = self._data.get(str(path.resolve()))
        return entry["tag"] if entry else None

    def get_added_at(self, path: Path) -> str | None:
        """Return the ISO timestamp when *path* was tagged, or None."""
        entry = self._data.get(str(path.resolve()))
        return entry.get("added_at") if entry else None

    def get_all(self) -> list[dict]:
        """All entries as dicts with path/tag/name/added_at keys."""
        return [
            {
                "path": Path(k),
                "tag": v.get("tag", ""),
                "name": v.get("name", Path(k).name),
                "added_at": v.get("added_at", ""),
            }
            for k, v in self._data.items()
        ]

    def filter_by_tag(self, tag: str) -> list[dict]:
        """Return only entries whose tag exactly matches *tag*."""
        return [e for e in self.get_all() if e["tag"] == tag]

    def all_tags(self) -> list[str]:
        """Sorted list of all distinct tag names in the store."""
        return sorted({v.get("tag", "") for v in self._data.values() if v.get("tag")})

    def count(self) -> int:
        return len(self._data)
