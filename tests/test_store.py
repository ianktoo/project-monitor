"""Tests for TagStore — persistent tag store."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_monitor.store import TagStore


def _store(tmp_path: Path) -> TagStore:
    return TagStore(store_path=tmp_path / "tags.json")


# ---------------------------------------------------------------------------
# Basic add / get


def test_add_and_get_tag(tmp_path: Path):
    s = _store(tmp_path)
    target = tmp_path / "my-project"
    target.mkdir()
    s.add(target, "work")
    assert s.get_tag(target) == "work"


def test_add_overwrites_existing_tag(tmp_path: Path):
    s = _store(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    s.add(target, "old")
    s.add(target, "new")
    assert s.get_tag(target) == "new"


def test_get_tag_unknown_path_returns_none(tmp_path: Path):
    s = _store(tmp_path)
    assert s.get_tag(tmp_path / "nonexistent") is None


def test_add_records_added_at_timestamp(tmp_path: Path):
    s = _store(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    s.add(target, "work")
    added = s.get_added_at(target)
    assert added is not None
    assert "T" in added  # ISO format contains T separator


# ---------------------------------------------------------------------------
# Remove


def test_remove_existing_returns_true(tmp_path: Path):
    s = _store(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    s.add(target, "x")
    assert s.remove(target) is True
    assert s.get_tag(target) is None


def test_remove_nonexistent_returns_false(tmp_path: Path):
    s = _store(tmp_path)
    assert s.remove(tmp_path / "ghost") is False


def test_remove_decrements_count(tmp_path: Path):
    s = _store(tmp_path)
    for name in ("a", "b", "c"):
        d = tmp_path / name
        d.mkdir()
        s.add(d, "tag")
    s.remove(tmp_path / "b")
    assert s.count() == 2


# ---------------------------------------------------------------------------
# get_all / filter_by_tag


def test_get_all_empty(tmp_path: Path):
    s = _store(tmp_path)
    assert s.get_all() == []


def test_get_all_returns_all_entries(tmp_path: Path):
    s = _store(tmp_path)
    for name, tag in [("a", "work"), ("b", "personal"), ("c", "work")]:
        d = tmp_path / name
        d.mkdir()
        s.add(d, tag)
    entries = s.get_all()
    assert len(entries) == 3
    paths = {e["path"] for e in entries}
    assert (tmp_path / "a").resolve() in paths


def test_filter_by_tag(tmp_path: Path):
    s = _store(tmp_path)
    for name, tag in [("a", "work"), ("b", "personal"), ("c", "work")]:
        d = tmp_path / name
        d.mkdir()
        s.add(d, tag)
    work_entries = s.filter_by_tag("work")
    assert len(work_entries) == 2
    assert all(e["tag"] == "work" for e in work_entries)


def test_filter_by_tag_no_match(tmp_path: Path):
    s = _store(tmp_path)
    d = tmp_path / "proj"
    d.mkdir()
    s.add(d, "work")
    assert s.filter_by_tag("missing") == []


# ---------------------------------------------------------------------------
# all_tags / count


def test_all_tags(tmp_path: Path):
    s = _store(tmp_path)
    for name, tag in [("a", "work"), ("b", "personal"), ("c", "work")]:
        d = tmp_path / name
        d.mkdir()
        s.add(d, tag)
    assert s.all_tags() == ["personal", "work"]


def test_count(tmp_path: Path):
    s = _store(tmp_path)
    assert s.count() == 0
    d = tmp_path / "x"
    d.mkdir()
    s.add(d, "t")
    assert s.count() == 1


# ---------------------------------------------------------------------------
# Persistence — reloading from disk


def test_data_persists_across_instances(tmp_path: Path):
    store_file = tmp_path / "tags.json"
    target = tmp_path / "repo"
    target.mkdir()

    s1 = TagStore(store_path=store_file)
    s1.add(target, "persistent")

    s2 = TagStore(store_path=store_file)
    assert s2.get_tag(target) == "persistent"
    assert s2.count() == 1


def test_corrupt_store_file_loads_empty(tmp_path: Path):
    store_file = tmp_path / "tags.json"
    store_file.write_text("not valid json", encoding="utf-8")
    s = TagStore(store_path=store_file)
    assert s.count() == 0


def test_store_file_is_valid_json(tmp_path: Path):
    s = _store(tmp_path)
    d = tmp_path / "proj"
    d.mkdir()
    s.add(d, "label")
    store_file = tmp_path / "tags.json"
    data = json.loads(store_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    key = str(d.resolve())
    assert key in data
    assert data[key]["tag"] == "label"


# ---------------------------------------------------------------------------
# Symlink / resolve robustness


def test_add_resolves_path(tmp_path: Path):
    """Paths with trailing slashes or dotdots resolve to the same key."""
    s = _store(tmp_path)
    target = tmp_path / "proj"
    target.mkdir()
    s.add(target, "x")
    assert s.get_tag(target / ".." / "proj") == "x"


# ---------------------------------------------------------------------------
# Migration from legacy store


def test_migration_from_legacy_store(tmp_path: Path):
    """Tags in the legacy ~/.pmon/tags.json are silently copied to the new store on first use."""
    import json
    import project_monitor.store as store_mod

    legacy = tmp_path / "legacy" / "tags.json"
    new_path = tmp_path / "new" / "tags.json"
    proj = tmp_path / "my-proj"
    proj.mkdir()

    legacy.parent.mkdir()
    legacy.write_text(
        json.dumps({str(proj): {"tag": "work", "name": "my-proj", "added_at": "2024-01-01T00:00:00"}}),
        encoding="utf-8",
    )

    original_default = store_mod.DEFAULT_STORE
    original_legacy = store_mod.LEGACY_STORE
    store_mod.DEFAULT_STORE = new_path
    store_mod.LEGACY_STORE = legacy
    try:
        s = TagStore(store_path=None)  # use default → triggers migration check
    finally:
        store_mod.DEFAULT_STORE = original_default
        store_mod.LEGACY_STORE = original_legacy

    assert new_path.exists(), "new store was not created"
    assert s.get_tag(proj) == "work", "tag was not migrated"
