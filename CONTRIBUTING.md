# Contributing to project-monitor

This document is for developers who want to contribute to `pmon`, build on top of it, or publish their own formatter packages.

---

## Table of contents

- [Development setup](#development-setup)
- [Running tests](#running-tests)
- [Project architecture](#project-architecture)
- [Public API](#public-api)
- [Adding a formatter](#adding-a-formatter)
- [Code style](#code-style)
- [Building and publishing to PyPI](#building-and-publishing-to-pypi)

---

## Development setup

### Requirements

- Python 3.9 or later
- git

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/CompassPoint-Mentorship/project-monitor
cd project-monitor

# 2. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 3. Verify the CLI works
pmon --version

# 4. Run the tests
python -m pytest
```

`pip install -e .` installs the package in editable mode — changes to the source files take effect immediately without reinstalling.

---

## Running tests

```bash
# Run all tests
python -m pytest

# Run with verbose output (shows each test name)
python -m pytest -v

# Run a single test file
python -m pytest tests/test_git_ops.py -v

# Run a single test by name
python -m pytest -k "test_parse_status_clean"

# Stop on the first failure
python -m pytest -x
```

### Test layout

| File | What it covers |
|------|----------------|
| `tests/test_models.py` | `RepoInfo` properties (`is_clean`, `total_changes`) |
| `tests/test_scanner.py` | `scan_for_repos` — filesystem traversal, depth limits, symlinks, error handling |
| `tests/test_git_ops.py` | `_parse_status`, `_parse_log`, `_run_git`, `get_repo_status`, `check_git_available` |
| `tests/test_formatters.py` | Cell helper functions, `TableFormatter`, `TextFormatter` |
| `tests/test_cli.py` | End-to-end CLI via `typer.testing.CliRunner` |

No test hits the real filesystem beyond `tmp_path`. All `subprocess` calls are mocked. Tests run offline.

---

## Project architecture

```
src/project_monitor/
├── __init__.py          # Package version; re-exports RepoInfo and OutputFormatter
├── __main__.py          # Enables python -m project_monitor
├── py.typed             # PEP 561 marker — full type hint support
│
├── models.py            # RepoInfo dataclass — the stable public data contract
├── scanner.py           # Walk a directory tree and find .git repos
├── git_ops.py           # Run git commands → populate RepoInfo
├── cli.py               # typer CLI entry point; wires everything together
│
└── formatters/
    ├── __init__.py      # OutputFormatter protocol (the extension point)
    ├── table.py         # Rich coloured terminal table (default formatter)
    └── text.py          # Plain-text file export (used by --output)
```

### Data flow

```
cli.py
  │
  ├─► scanner.scan_for_repos(root, depth)
  │     └─► returns list[Path]  (sorted, deduplicated)
  │
  ├─► git_ops.get_repo_status(path)  — called once per repo
  │     └─► returns RepoInfo
  │
  └─► formatter.render(list[RepoInfo])
        ├─► TableFormatter  — writes coloured table to stdout
        └─► TextFormatter   — writes plain-text table to a file
```

### Key design decisions

- **`RepoInfo` is the only shared interface.** The scanner, git layer, and all formatters are decoupled from each other. They communicate only through `RepoInfo`.
- **No `shell=True`.** Every `subprocess.run` call uses a list of arguments, preventing command injection.
- **Errors stay inside `RepoInfo`.** A failing `git` call sets `RepoInfo.error` rather than raising. The formatter decides how to display it.
- **No recursion into repos.** Once a `.git` folder is found, the scanner stops descending into that directory.

---

## Public API

The following symbols are part of the stable public API. They are re-exported from `project_monitor.__init__` and should remain backward-compatible across minor versions.

### `RepoInfo` (`project_monitor.models`)

The data contract between the scanning layer and all formatters.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Folder name of the repository |
| `path` | `Path` | Absolute path to the repository root |
| `branch` | `str` | Current branch. `"(detached)"` if HEAD is detached |
| `staged` | `int` | Files staged for the next commit |
| `unstaged` | `int` | Tracked files with unstaged modifications |
| `untracked` | `int` | New files not yet tracked by git |
| `last_commit_hash` | `str` | 7-char abbreviated commit hash |
| `last_commit_msg` | `str` | Commit subject line, max 40 chars |
| `ahead` | `int` | Commits ahead of the upstream remote |
| `behind` | `int` | Commits behind the upstream remote |
| `has_remote` | `bool` | Whether an upstream remote branch is configured |
| `error` | `str \| None` | Set if any git call failed |
| `is_clean` *(property)* | `bool` | `True` when staged + unstaged + untracked == 0 |
| `total_changes` *(property)* | `int` | staged + unstaged + untracked |

### `OutputFormatter` (`project_monitor.formatters`)

A `Protocol`. Any class that implements `render(self, repos: list[RepoInfo]) -> None` satisfies it. No subclassing required.

---

## Adding a formatter

### In this repository

1. Create a file under `src/project_monitor/formatters/`, e.g. `json_fmt.py`.
2. Implement the `render` method.
3. Add a test in `tests/test_formatters.py`.

```python
# src/project_monitor/formatters/json_fmt.py
from __future__ import annotations
import json
import sys
from project_monitor.models import RepoInfo


class JsonFormatter:
    """Outputs repository status as a JSON array to stdout."""

    def render(self, repos: list[RepoInfo]) -> None:
        data = [
            {
                "name": r.name,
                "branch": r.branch,
                "clean": r.is_clean,
                "staged": r.staged,
                "unstaged": r.unstaged,
                "untracked": r.untracked,
                "last_commit": f"{r.last_commit_hash} {r.last_commit_msg}".strip(),
                "ahead": r.ahead,
                "behind": r.behind,
                "has_remote": r.has_remote,
            }
            for r in repos
        ]
        json.dump(data, sys.stdout, indent=2)
        print()
```

### As a standalone package

You can publish a formatter as its own PyPI package. Depend only on `project-monitor` and import from `project_monitor.models`:

```python
# your_package/slack_formatter.py
import requests
from project_monitor.models import RepoInfo

class SlackFormatter:
    def __init__(self, webhook_url: str) -> None:
        self._webhook = webhook_url

    def render(self, repos: list[RepoInfo]) -> None:
        lines = [f"{'✓' if r.is_clean else '✗'} *{r.name}* [{r.branch}]" for r in repos]
        requests.post(self._webhook, json={"text": "\n".join(lines)})
```

Use it programmatically:

```python
from pathlib import Path
from project_monitor.scanner import scan_for_repos
from project_monitor.git_ops import get_repo_status
from your_package.slack_formatter import SlackFormatter

repos = [get_repo_status(p) for p in scan_for_repos(Path("~/Projects").expanduser())]
SlackFormatter("https://hooks.slack.com/...").render(repos)
```

---

## Code style

- **Type hints required** on all public functions and methods. Use `from __future__ import annotations` at the top of each file.
- **Docstrings** on all public symbols. Google style: one-line summary, then `Args:` / `Returns:` sections when non-obvious.
- **No bare `except:`** — always name the exception type.
- **No `shell=True`** in any `subprocess` call.
- **`models.py` must stay dependency-free** — no third-party imports there.
- **Logging** — use `logging.getLogger(__name__)` in each module. Debug for per-item noise, info for summaries, warning for recoverable problems.

---

## Building and publishing to PyPI

### 1. Bump the version

Edit `src/project_monitor/__init__.py` and `pyproject.toml` — update `__version__` and `version` to match (e.g. `"0.2.0"`).

### 2. Build the distribution

```bash
pip install build
python -m build
```

This produces `dist/project_monitor-X.Y.Z.tar.gz` and `dist/project_monitor-X.Y.Z-py3-none-any.whl`.

### 3. Publish to PyPI

```bash
pip install twine
twine upload dist/*
```

You will be prompted for your PyPI username and password (or use an API token — recommended).

### 4. Verify

```bash
pip install --upgrade project-monitor
pmon --version
```

### Test release on TestPyPI first (optional but recommended)

```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ project-monitor
```
