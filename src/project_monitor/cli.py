"""Command-line interface entry point for pmon."""

from __future__ import annotations

import io
import logging
import random
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console


def _configure_stdout_utf8() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows so Rich can render Unicode."""
    for attr in ("stdout", "stderr"):
        stream = getattr(sys, attr)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, io.UnsupportedOperation):
                pass


_configure_stdout_utf8()

from project_monitor import __version__
from project_monitor.formatters.table import TableFormatter
from project_monitor.formatters.text import TextFormatter
from project_monitor.git_ops import check_git_available, get_repo_status
from project_monitor.scanner import scan_for_repos

app = typer.Typer(
    name="pmon",
    help="Scan a folder for git repos and view their status at a glance.",
    add_completion=False,
)

_stderr = Console(stderr=True)

_TAGLINES = [
    "your repos, at a glance",
    "git status, everywhere",
    "no repo left behind",
    "keep your branches in check",
    "know where you stand",
    "the bird's-eye view of your work",
    "all your branches, one look",
]


def _print_intro(use_color: bool = True) -> None:
    c = Console(stderr=True, highlight=False, no_color=not use_color)
    tagline = random.choice(_TAGLINES)
    c.print(f"  [bold cyan]⎇  pmon[/bold cyan] [dim]v{__version__}[/dim]  [italic dim]{tagline}[/italic dim]")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pmon {__version__}")
        raise typer.Exit()


@app.command()
def main(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan. Defaults to current directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    depth: int = typer.Option(
        2,
        "--depth",
        "-d",
        help="Maximum folder depth to search (1–3).",
        min=1,
        max=3,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write plain-text results to FILE.",
        writable=True,
        resolve_path=True,
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable ANSI color output.",
    ),
    compact: bool = typer.Option(
        False,
        "--compact",
        "-c",
        help="Condensed one-line-per-repo view.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging to stderr.",
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        "--log-file",
        help="Append structured log output to FILE.",
        writable=True,
        resolve_path=True,
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Scan PATH for git repositories and print their status."""
    _print_intro(use_color=not no_color)
    _configure_logging(verbose=verbose, log_file=log_file)
    logger = logging.getLogger("project_monitor")

    if not check_git_available():
        _stderr.print("[red]Error: git is not installed or not found on PATH.[/red]")
        _stderr.print("Install git from https://git-scm.com and ensure it is on your PATH.")
        raise typer.Exit(1)

    root = path or Path.cwd()
    logger.info("pmon %s — root=%s depth=%d", __version__, root, depth)

    start = time.monotonic()
    repo_paths = scan_for_repos(root, max_depth=depth)

    if not repo_paths:
        _stderr.print(f"[yellow]No git repositories found under {root}[/yellow]")
        raise typer.Exit(0)

    repo_infos = [get_repo_status(p) for p in repo_paths]
    elapsed = time.monotonic() - start
    logger.info("Scan complete in %.2fs — %d repo(s)", elapsed, len(repo_infos))

    if output:
        try:
            TextFormatter(output).render(repo_infos)
            _stderr.print(f"Results written to [bold]{output}[/bold]")
        except OSError as exc:
            _stderr.print(f"[red]Error: cannot write to {output}: {exc}[/red]")
            raise typer.Exit(1)
    else:
        fmt = TableFormatter(use_color=not no_color)
        if compact:
            fmt.render_compact(repo_infos)
        else:
            fmt.render(repo_infos)


def _configure_logging(verbose: bool, log_file: Optional[Path]) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )
