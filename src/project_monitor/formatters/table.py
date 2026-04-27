"""Rich colored terminal table formatter."""

from __future__ import annotations

import logging
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
        # legacy_windows=False forces VT100/ANSI mode on Windows 10+, which
        # supports Unicode. The legacy Windows console API is limited to cp1252.
        self._console = Console(
            file=file,
            highlight=False,
            no_color=not use_color,
            legacy_windows=False,
        )
        self._box_style = box.ASCII2 if ascii_only else box.ROUNDED

    def render_compact(self, repos: list[RepoInfo]) -> None:
        """Print a condensed one-line-per-repo list."""
        if not repos:
            self._console.print("[yellow]No git repositories found.[/yellow]")
            return

        name_w = max(len(r.name) for r in repos) + 2
        branch_w = max((len(r.branch or "") for r in repos), default=6) + 2

        for repo in repos:
            icon = "[green]✓[/green]" if (repo.is_clean and not repo.error) else "[red]✗[/red]"
            name = f"[bold]{repo.name:<{name_w}}[/bold]"
            branch = f"[cyan]{(repo.branch or '—'):<{branch_w}}[/cyan]"
            if repo.error:
                extra = f"[red]{repo.error}[/red]"
            elif not repo.is_clean:
                extra = _compact_details(repo)
            else:
                extra = ""
            self._console.print(f"  {icon}  {name}  {branch}  {extra}")

        self._console.print(_summary_line(repos))

    def render(self, repos: list[RepoInfo]) -> None:
        """Print a colored table to the console."""
        if not repos:
            self._console.print("[yellow]No git repositories found.[/yellow]")
            return

        table = Table(box=self._box_style, show_lines=False, expand=False)
        table.add_column("Project", style="bold", min_width=12)
        table.add_column("Branch", min_width=10)
        table.add_column("Status", min_width=22)
        table.add_column("Last Commit", min_width=22)
        table.add_column("Remote", min_width=12)

        for repo in repos:
            table.add_row(
                repo.name,
                _branch_cell(repo),
                _status_cell(repo),
                _commit_cell(repo),
                _remote_cell(repo),
            )

        self._console.print(table)
        self._console.print(_summary_line(repos))

        for repo in repos:
            if repo.error:
                logger.warning("Error reading repo %s: %s", repo.name, repo.error)
                self._console.print(f"[red]  ! {repo.name}: {repo.error}[/red]")


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
