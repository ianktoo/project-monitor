"""Rich colored terminal table formatter."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import IO

from rich import box
from rich.console import Console
from rich.table import Table

from project_monitor.models import RepoInfo

logger = logging.getLogger(__name__)


class TableFormatter:
    """Renders repository status as a colored terminal table using Rich.

    Args:
        file: Optional writable file-like object. Defaults to stdout.
        use_color: When False, ANSI color codes are suppressed.
        ascii_only: When True, uses ASCII box-drawing characters (for file export).
    """

    def __init__(
        self,
        file: IO[str] | None = None,
        use_color: bool = True,
        ascii_only: bool = False,
    ) -> None:
        # legacy_windows=False forces VT100/ANSI mode on Windows 10+.
        # When writing to an explicit file (export / tests) use a wide fixed width
        # so column content is never truncated by Rich's 80-char non-TTY default.
        self._console = Console(
            file=file,
            highlight=False,
            no_color=not use_color,
            legacy_windows=False,
            width=200 if file is not None else None,
        )
        self._box_style = box.ASCII2 if ascii_only else box.ROUNDED

    # ------------------------------------------------------------------
    # Full table view (default)

    def render(self, repos: list[RepoInfo]) -> None:
        """Print a colored table to the console."""
        if not repos:
            self._console.print("[yellow]No git repositories found.[/yellow]")
            return

        show_tag = any(r.tag for r in repos)

        table = Table(box=self._box_style, show_lines=False, expand=False)
        table.add_column("Project", style="bold", min_width=12)
        table.add_column("Branch", min_width=10)
        table.add_column("Status", min_width=22)
        table.add_column("Last Commit", min_width=22)
        table.add_column("Remote", min_width=12)
        if show_tag:
            table.add_column("Tag", min_width=8)

        for repo in repos:
            row = [
                repo.name,
                _branch_cell(repo),
                _status_cell(repo),
                _commit_cell(repo),
                _remote_cell(repo),
            ]
            if show_tag:
                row.append(_tag_cell(repo))
            table.add_row(*row)

        self._console.print(table)
        self._console.print(_summary_line(repos))

        for repo in repos:
            if repo.error:
                logger.warning("Error reading repo %s: %s", repo.name, repo.error)
                self._console.print(f"[red]  ! {repo.name}: {repo.error}[/red]")

    # ------------------------------------------------------------------
    # Compact view

    def render_compact(self, repos: list[RepoInfo]) -> None:
        """Print a condensed one-line-per-repo list."""
        if not repos:
            self._console.print("[yellow]No git repositories found.[/yellow]")
            return

        name_w = max(len(r.name) for r in repos) + 2
        branch_w = max((len(r.branch or "") for r in repos), default=6) + 2
        show_tag = any(r.tag for r in repos)
        tag_w = max((len(r.tag or "") for r in repos), default=4) + 2 if show_tag else 0

        for repo in repos:
            icon = "[green]✓[/green]" if (repo.is_clean and not repo.error) else "[red]✗[/red]"
            name = f"[bold]{repo.name:<{name_w}}[/bold]"
            branch = f"[cyan]{(repo.branch or '—'):<{branch_w}}[/cyan]"
            # Use Text.assemble-friendly approach: tag label without [] to avoid
            # being interpreted as Rich markup tags
            tag_part = f"[dim]{(repo.tag or ''):<{tag_w}}[/dim]  " if show_tag else ""
            if repo.error:
                extra = f"[red]{repo.error}[/red]"
            elif not repo.is_clean:
                extra = _compact_details(repo)
            else:
                extra = ""
            self._console.print(f"  {icon}  {name}  {tag_part}{branch}  {extra}")

        self._console.print(_summary_line(repos))

    # ------------------------------------------------------------------
    # Local scan view (no remote column)

    def render_local(self, repos: list[RepoInfo]) -> None:
        """Print local-only view: branch/status/tag/path, no remote column."""
        if not repos:
            self._console.print("[yellow]No git repositories found.[/yellow]")
            return

        table = Table(box=self._box_style, show_lines=False, expand=False)
        table.add_column("Project", style="bold", min_width=12)
        table.add_column("Branch", min_width=10)
        table.add_column("Status", min_width=22)
        table.add_column("Tag", min_width=8)
        table.add_column("Path", min_width=20, overflow="fold")
        table.add_column("Date", min_width=10)

        for repo in repos:
            table.add_row(
                repo.name,
                _branch_cell(repo),
                _status_cell(repo),
                _tag_cell(repo),
                _path_cell(repo),
                _date_cell(repo),
            )

        self._console.print(table)
        self._console.print(_summary_line(repos))

        for repo in repos:
            if repo.error:
                logger.warning("Error reading repo %s: %s", repo.name, repo.error)
                self._console.print(f"[red]  ! {repo.name}: {repo.error}[/red]")

    # ------------------------------------------------------------------
    # Global tagged-projects view

    def render_global(self, repos: list[RepoInfo]) -> None:
        """Print the global tagged-projects view (from the pmon store)."""
        if not repos:
            self._console.print("[yellow]No tagged projects found.[/yellow]")
            return

        table = Table(box=self._box_style, show_lines=False, expand=False)
        table.add_column("Project", style="bold", min_width=12)
        table.add_column("Tag", min_width=8)
        table.add_column("Branch", min_width=10)
        table.add_column("Status", min_width=22)
        table.add_column("Path", min_width=24, overflow="fold")
        table.add_column("Added", min_width=10)

        for repo in repos:
            table.add_row(
                repo.name,
                _tag_cell(repo),
                _branch_cell(repo),
                _status_cell(repo),
                _path_cell(repo),
                f"[dim]{(repo.date_added or '—')[:10]}[/dim]",
            )

        self._console.print(table)

        tags = sorted({r.tag for r in repos if r.tag})
        tag_label = (
            "  · tags: " + " ".join(f"[cyan]{t}[/cyan]" for t in tags)
            if tags
            else ""
        )
        self._console.print(
            f"  [bold]{len(repos)} tagged project(s)[/bold]{tag_label}"
        )

        for repo in repos:
            if repo.error:
                self._console.print(f"[red]  ! {repo.name}: {repo.error}[/red]")

    def render_global_local(self, entries: list[dict]) -> None:
        """Print global view without running git — store data only."""
        if not entries:
            self._console.print("[yellow]No tagged projects found.[/yellow]")
            return

        table = Table(box=self._box_style, show_lines=False, expand=False)
        table.add_column("Project", style="bold", min_width=12)
        table.add_column("Tag", min_width=8)
        table.add_column("Path", min_width=24, overflow="fold")
        table.add_column("Added", min_width=10)
        table.add_column("Exists", min_width=6)

        for entry in entries:
            p: Path = entry["path"]
            exists = p.exists()
            exists_cell = "[green]✓[/green]" if exists else "[red]✗[/red]"
            path_str = _shorten_path(p)
            added = (entry.get("added_at") or "—")[:10]
            tag_str = entry.get("tag") or "—"
            table.add_row(
                entry.get("name") or p.name,
                f"[cyan]{tag_str}[/cyan]",
                f"[dim]{path_str}[/dim]",
                f"[dim]{added}[/dim]",
                exists_cell,
            )

        self._console.print(table)
        tags = sorted({e.get("tag", "") for e in entries if e.get("tag")})
        tag_label = (
            "  · tags: " + " ".join(f"[cyan]{t}[/cyan]" for t in tags)
            if tags
            else ""
        )
        self._console.print(
            f"  [bold]{len(entries)} tagged project(s)[/bold]{tag_label}"
        )


# ---------------------------------------------------------------------------
# Cell helpers


def _branch_cell(repo: RepoInfo) -> str:
    if repo.error:
        return "[dim]—[/dim]"
    return f"[cyan]{repo.branch}[/cyan]"


def _status_cell(repo: RepoInfo) -> str:
    if repo.error:
        return "[red]Error[/red]"
    if repo.is_clean:
        return "[green]✓ Clean[/green]"
    parts: list[str] = []
    if repo.staged:
        parts.append(f"{repo.staged} staged")
    if repo.unstaged:
        parts.append(f"{repo.unstaged} modified")
    if repo.untracked:
        parts.append(f"{repo.untracked} untracked")
    return f"[red]✗[/red] {', '.join(parts)}"


def _commit_cell(repo: RepoInfo) -> str:
    if repo.error or not repo.last_commit_hash:
        return "[dim]—[/dim]"
    return f"[dim]{repo.last_commit_hash}[/dim] {repo.last_commit_msg}"


def _remote_cell(repo: RepoInfo) -> str:
    if repo.error:
        return "[dim]—[/dim]"
    if not repo.has_remote:
        return "[dim]No remote[/dim]"
    if repo.ahead == 0 and repo.behind == 0:
        return "[green]In sync[/green]"
    parts: list[str] = []
    if repo.ahead:
        parts.append(f"[yellow]↑{repo.ahead}[/yellow]")
    if repo.behind:
        parts.append(f"[red]↓{repo.behind}[/red]")
    return " ".join(parts)


def _tag_cell(repo: RepoInfo) -> str:
    if not repo.tag:
        return "[dim]—[/dim]"
    return f"[cyan]{repo.tag}[/cyan]"


def _path_cell(repo: RepoInfo) -> str:
    return f"[dim]{_shorten_path(repo.path)}[/dim]"


def _date_cell(repo: RepoInfo) -> str:
    if repo.date_added:
        return f"[dim]{repo.date_added[:10]}[/dim]"
    try:
        ts = repo.path.stat().st_mtime
        return f"[dim]{datetime.fromtimestamp(ts).strftime('%Y-%m-%d')}[/dim]"
    except OSError:
        return "[dim]—[/dim]"


def _shorten_path(p: Path) -> str:
    """Return path with home directory replaced by ~."""
    try:
        return "~/" + str(p.relative_to(Path.home()))
    except ValueError:
        return str(p)


def _compact_details(repo: RepoInfo) -> str:
    parts: list[str] = []
    if repo.staged:
        parts.append(f"[yellow]{repo.staged} staged[/yellow]")
    if repo.unstaged:
        parts.append(f"[red]{repo.unstaged} modified[/red]")
    if repo.untracked:
        parts.append(f"[dim]{repo.untracked} untracked[/dim]")
    if repo.has_remote:
        if repo.ahead:
            parts.append(f"[yellow]↑{repo.ahead}[/yellow]")
        if repo.behind:
            parts.append(f"[red]↓{repo.behind}[/red]")
    else:
        parts.append("[dim]no remote[/dim]")
    return " · ".join(parts)


def _summary_line(repos: list[RepoInfo]) -> str:
    clean = sum(1 for r in repos if r.is_clean and not r.error)
    dirty = sum(1 for r in repos if not r.is_clean and not r.error)
    errors = sum(1 for r in repos if r.error)
    parts = [f"[bold]Found {len(repos)} repo(s)[/bold]"]
    if clean:
        parts.append(f"[green]{clean} clean[/green]")
    if dirty:
        parts.append(f"[red]{dirty} need attention[/red]")
    if errors:
        parts.append(f"[red]{errors} error(s)[/red]")
    return "  " + " · ".join(parts)
