# project-monitor (`pmon`)

Scan a folder for git repositories and view their commit status at a glance — in one table, in your terminal.

```
╭──────────────────┬───────────────┬──────────────────────┬──────────────────────────┬──────────────╮
│ Project          │ Branch        │ Status               │ Last Commit              │ Remote       │
├──────────────────┼───────────────┼──────────────────────┼──────────────────────────┼──────────────┤
│ api-service      │ main          │ ✓ Clean              │ a1b2c3d fix auth flow    │ In sync      │
│ dashboard        │ feature/dark  │ ✗ 2 staged, 1 mod.   │ e4f5a6b add chart comp   │ ↑3 ahead     │
│ mobile-app       │ main          │ ✓ Clean              │ 9f8e7d6 update deps      │ In sync      │
│ old-prototype    │ dev           │ ✗ 5 untracked        │ 1234abc initial commit   │ No remote    │
╰──────────────────┴───────────────┴──────────────────────┴──────────────────────────┴──────────────╯
  Found 4 repo(s) · 2 clean · 2 need attention
```

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Uninstallation](#uninstallation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Reading the output](#reading-the-output)
- [Troubleshooting](#troubleshooting)
- [Debug and logs](#debug-and-logs)
- [Extending pmon](#extending-pmon)
- [Contributing](#contributing)
- [License](#license)

---

## Requirements

- **Python 3.9 or later**
- **git** installed and available on your PATH

Check both with:

```bash
python --version
git --version
```

---

## Installation

### Recommended — pipx (isolated, global install)

[pipx](https://pipx.pypa.io) installs CLI tools in their own isolated environment so they never interfere with your other Python projects. This is the recommended way to install `pmon`.

```bash
pipx install project-monitor
```

To upgrade later:

```bash
pipx upgrade project-monitor
```

### Standard — pip

```bash
pip install project-monitor
```

> **Windows note:** if `pmon` is not found after installing, the Python Scripts folder may not be on your PATH. Run `python -m project_monitor` as a fallback, or add the Scripts folder to your PATH. pip will print the folder path in a warning if this is the case.

### From source

```bash
git clone https://github.com/CompassPoint-Mentorship/project-monitor
cd project-monitor
pip install .
```

---

## Uninstallation

### If installed with pipx

```bash
pipx uninstall project-monitor
```

### If installed with pip

```bash
pip uninstall project-monitor
```

This removes the package and the `pmon` command. It does not touch any log files or output files you created.

---

## Quick start

```bash
# Scan your current folder
pmon

# Scan a specific folder
pmon C:\Users\you\Projects

# Scan only one level deep
pmon C:\Users\you\Projects --depth 1

# Save results to a text file
pmon C:\Users\you\Projects --output status.txt
```

---

## CLI reference

```
pmon [PATH] [OPTIONS]
```

| Argument / Option     | Default            | Description                                       |
|-----------------------|--------------------|---------------------------------------------------|
| `PATH`                | current directory  | Directory to scan                                 |
| `--depth INT` / `-d`  | `2`                | Max folder depth to search (1–3)                  |
| `--output FILE` / `-o`| —                  | Write plain-text results to FILE instead of terminal |
| `--no-color`          | off                | Disable colour output (useful in CI or scripts)   |
| `--verbose` / `-v`    | off                | Print debug log lines to stderr                   |
| `--log-file FILE`     | —                  | Append structured log output to FILE              |
| `--version`           | —                  | Show version and exit                             |
| `--help`              | —                  | Show help and exit                                |

### Examples

```bash
# Scan your projects at default depth (2 levels)
pmon ~/Projects

# Only look one level deep
pmon ~/Projects --depth 1

# Go three levels deep (e.g. org/team/repo)
pmon ~/Projects --depth 3

# Export to a plain-text file (no colour codes)
pmon ~/Projects --output status.txt

# Combine: scan, export, and save a debug log
pmon ~/Projects --output status.txt --log-file pmon.log

# Disable colour for piping or non-colour terminals
pmon ~/Projects --no-color

# Show live debug output while scanning
pmon ~/Projects --verbose

# Check version
pmon --version
```

---

## Reading the output

Each row in the table represents one git repository.

| Column      | What it shows |
|-------------|---------------|
| **Project** | The folder name of the repository |
| **Branch**  | The currently checked-out branch. Shows `(detached)` if HEAD is detached |
| **Status**  | `✓ Clean` — nothing to commit. `✗ N staged, N modified, N untracked` — work in progress |
| **Last Commit** | Abbreviated hash and the first line of the most recent commit message |
| **Remote**  | `In sync` — matches the remote. `↑N` — N commits ahead. `↓N` — N commits behind. `No remote` — no upstream configured |

The summary line below the table counts total repos, how many are clean, and how many need attention.

### Status breakdown

| Status term  | Meaning |
|--------------|---------|
| `staged`     | Files added to the index (`git add`) but not yet committed |
| `modified`   | Tracked files changed but not staged |
| `untracked`  | New files not yet added to git |

---

## Troubleshooting

### `pmon: command not found` / `pmon is not recognised`

The Python Scripts folder is not on your PATH.

**Option 1 — use pipx** (recommended, handles PATH automatically):
```bash
pipx install project-monitor
```

**Option 2 — run as a module** (always works):
```bash
python -m project_monitor
```

**Option 3 — add Scripts to PATH** (Windows):

Find the Scripts folder pip printed during install (e.g. `C:\Users\you\AppData\Roaming\Python\Python312\Scripts`), then add it to your PATH in System Settings → Environment Variables.

---

### `Error: git is not installed or not found on PATH`

`pmon` requires git. Install it from [https://git-scm.com](https://git-scm.com) and ensure `git --version` works in your terminal before running `pmon` again.

On Windows, you may need to restart your terminal after installing git.

---

### No repositories found

```
No git repositories found under C:\your\folder
```

This means `pmon` did not find a `.git` folder within the scan depth.

- Check that the folder actually contains git repos (`ls -a` / `dir /a` inside a project should show `.git`).
- Try increasing the depth: `pmon . --depth 3`
- If the repos are nested more than 3 levels deep, `pmon` does not support that at present.

---

### Output looks garbled or has `?` characters

This is a terminal encoding issue. `pmon` outputs UTF-8. If your terminal is configured for a legacy encoding (common on older Windows cmd):

```bash
# Windows — set UTF-8 for the current session
chcp 65001

# Then run pmon
pmon .
```

Or use `--no-color` which also avoids Unicode symbols in the Status column:

```bash
pmon . --no-color
```

---

### A repo shows `Error` in the Status column

`pmon` ran `git status` inside that repository and git returned a non-zero exit code. Common causes:

- The `.git` folder is corrupted — try `git status` manually inside the repo.
- The repo is a git submodule or worktree with a missing parent.
- git timed out (default timeout is 5 seconds) — this can happen on network-mounted drives.

Run `pmon --verbose` to see the exact error message for that repo.

---

### Results are missing some repos

- They may be more than 2 levels deep. Try `--depth 3`.
- Symlinked directories are intentionally not followed.
- Directories that return a permission error are silently skipped.

---

### Slow scan on a large folder

Each repo requires two `git` calls (5-second timeout each). If you have many repos or are scanning a network drive, the scan can take a moment. Use `--depth 1` to limit the scan area, or target a more specific subfolder.

---

## Debug and logs

### Enable verbose output

Prints one debug log line per action (repo found, git call made, result parsed) to stderr:

```bash
pmon ~/Projects --verbose
```

### Save logs to a file

Logs are appended (not overwritten) so you can keep a history:

```bash
pmon ~/Projects --log-file pmon.log
```

You can combine both — verbose to stderr and a persistent file:

```bash
pmon ~/Projects --verbose --log-file pmon.log
```

### Log format

```
2026-04-27 09:50:30,136 project_monitor.scanner DEBUG Found repo: C:\Projects\my-app
2026-04-27 09:50:30,201 project_monitor INFO Scan complete in 0.48s — 22 repo(s)
```

Fields: `timestamp  logger_name  LEVEL  message`

All loggers live under the `project_monitor` namespace, so you can filter them with any standard logging tool.

---

## Extending pmon

`pmon` is designed to be extended without modifying the core. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full developer guide.

### Using pmon as a library

```python
from pathlib import Path
from project_monitor.scanner import scan_for_repos
from project_monitor.git_ops import get_repo_status
from project_monitor.formatters.table import TableFormatter

paths = scan_for_repos(Path.home() / "Projects", max_depth=2)
repos = [get_repo_status(p) for p in paths]
TableFormatter().render(repos)
```

### Writing a custom formatter

Any object with a `render(self, repos)` method works:

```python
from project_monitor.formatters import OutputFormatter
from project_monitor.models import RepoInfo

class CsvFormatter:
    def render(self, repos: list[RepoInfo]) -> None:
        print("name,branch,clean,staged,unstaged,untracked")
        for r in repos:
            print(f"{r.name},{r.branch},{r.is_clean},{r.staged},{r.unstaged},{r.untracked}")
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, architecture notes, how to add formatters, run tests, and publish a release.

---

## License

MIT — see [LICENSE](LICENSE).
