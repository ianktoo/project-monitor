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
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn


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
from project_monitor.models import RepoInfo
from project_monitor.paths import DEFAULT_LOG
from project_monitor.scanner import scan_for_repos
from project_monitor.store import TagStore

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


def _fetch_with_progress(repo_paths: list[Path], no_color: bool) -> list[RepoInfo]:
    """Run get_repo_status on each path, showing a Rich progress bar on stderr."""
    progress_console = Console(stderr=True, highlight=False, no_color=no_color)
    infos: list[RepoInfo] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=progress_console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Checking {len(repo_paths)} repo(s)…", total=len(repo_paths)
        )
        for p in repo_paths:
            infos.append(get_repo_status(p))
            progress.advance(task)
    return infos


def _handle_tagging(
    tag: str,
    folder: Optional[Path],
    proj_path: Optional[Path],
    scan_path: Optional[Path],
    depth: int,
    store: TagStore,
) -> None:
    """Tag one or many repos and exit."""
    if not tag.strip():
        _stderr.print("[red]Error: tag name cannot be empty.[/red]")
        raise typer.Exit(1)

    if folder:
        repo_paths = scan_for_repos(folder.resolve(), max_depth=depth)
        if not repo_paths:
            _stderr.print(f"[yellow]No git repos found in {folder}[/yellow]")
            raise typer.Exit(0)
        for rp in repo_paths:
            try:
                store.add(rp, tag)
                _stderr.print(
                    f"  [green]✓[/green] Tagged [bold]{rp.name}[/bold] → [cyan]{tag}[/cyan]"
                )
            except OSError as exc:
                _stderr.print(f"  [red]✗[/red] Could not tag {rp.name}: {exc}")
        _stderr.print(
            f"\n  [bold]{len(repo_paths)} repo(s) tagged as '[cyan]{tag}[/cyan]'[/bold]"
        )
        raise typer.Exit(0)

    target = (proj_path or scan_path or Path.cwd()).resolve()
    if not target.exists():
        _stderr.print(f"[red]Error: path does not exist: {target}[/red]")
        raise typer.Exit(1)
    if not target.is_dir():
        _stderr.print(f"[red]Error: path is not a directory: {target}[/red]")
        raise typer.Exit(1)

    if not (target / ".git").exists():
        _stderr.print(f"  [yellow]![/yellow] {target} does not appear to be a git repo")

    try:
        store.add(target, tag)
    except OSError as exc:
        _stderr.print(f"[red]Error: could not save tag: {exc}[/red]")
        raise typer.Exit(1)

    _stderr.print(
        f"  [green]✓[/green] Tagged [bold]{target.name}[/bold] → [cyan]{tag}[/cyan]"
    )
    _stderr.print(f"  [dim]{target}[/dim]")
    raise typer.Exit(0)


def _handle_global(
    store: TagStore,
    tag_filter: Optional[str],
    local: bool,
    no_color: bool,
    compact: bool,
) -> None:
    """Show all tagged projects (or those matching tag_filter)."""
    entries = store.filter_by_tag(tag_filter) if tag_filter else store.get_all()

    if not entries:
        if tag_filter:
            _stderr.print(f"[yellow]No projects tagged '{tag_filter}'.[/yellow]")
        else:
            _stderr.print(
                "[yellow]No tagged projects yet.[/yellow] "
                "Use [bold]p-mon --tag <label>[/bold] to tag a project."
            )
        raise typer.Exit(0)

    fmt = TableFormatter(use_color=not no_color)

    if local:
        fmt.render_global_local(entries)
        raise typer.Exit(0)

    # Run git status on each accessible tagged path
    accessible = [e for e in entries if e["path"].exists()]
    missing = [e for e in entries if not e["path"].exists()]

    for e in missing:
        _stderr.print(
            f"  [yellow]![/yellow] [bold]{e['name']}[/bold]: path not found — {e['path']}"
        )

    if not accessible:
        _stderr.print("[yellow]None of the tagged paths are accessible.[/yellow]")
        raise typer.Exit(0)

    if not check_git_available():
        _stderr.print("[red]Error: git is not installed or not found on PATH.[/red]")
        raise typer.Exit(1)

    repo_infos = _fetch_with_progress([e["path"] for e in accessible], no_color=no_color)

    for info in repo_infos:
        info.tag = store.get_tag(info.path)
        info.date_added = store.get_added_at(info.path)

    if compact:
        fmt.render_compact(repo_infos)
    else:
        fmt.render_global(repo_infos)

    raise typer.Exit(0)


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
    # ── Tag & track ─────────────────────────────────────────────────────
    tag: Optional[str] = typer.Option(
        None,
        "--tag",
        "-t",
        help="Tag the target repo with a label. Used alone tags cwd/--path; with --folder bulk-tags.",
    ),
    proj_path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Specific path to tag (use with --tag) or scan.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    folder: Optional[Path] = typer.Option(
        None,
        "--folder",
        help="Folder to scan and bulk-tag (requires --tag).",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    show_global: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Show all tagged projects from the pmon store.",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Local view — skip remote/GitHub details, show path and tag.",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        help="Include tagged store projects alongside the current scan.",
    ),
) -> None:
    """Scan PATH for git repositories and print their status."""
    _print_intro(use_color=not no_color)
    _configure_logging(verbose=verbose, log_file=log_file)
    logger = logging.getLogger("project_monitor")

    store = TagStore()

    # ── Tagging mode ────────────────────────────────────────────────────
    if tag and not show_global:
        _handle_tagging(
            tag=tag,
            folder=folder,
            proj_path=proj_path,
            scan_path=path,
            depth=depth,
            store=store,
        )
        return  # _handle_tagging always raises typer.Exit

    # ── Global view ─────────────────────────────────────────────────────
    if show_global:
        _handle_global(
            store=store,
            tag_filter=tag,
            local=local,
            no_color=no_color,
            compact=compact,
        )
        return

    # ── Scan mode ────────────────────────────────────────────────────────
    if not check_git_available():
        _stderr.print("[red]Error: git is not installed or not found on PATH.[/red]")
        _stderr.print("Install git from https://git-scm.com and ensure it is on your PATH.")
        raise typer.Exit(1)

    root = proj_path or path or Path.cwd()
    logger.info("pmon %s — root=%s depth=%d", __version__, root, depth)

    start = time.monotonic()
    repo_paths = scan_for_repos(root, max_depth=depth)

    # --all: merge in any tagged repos not found by the scan
    if show_all:
        scanned_set = {p.resolve() for p in repo_paths}
        for entry in store.get_all():
            ep = entry["path"].resolve()
            if ep not in scanned_set and ep.exists():
                repo_paths.append(ep)
                scanned_set.add(ep)
        repo_paths.sort()

    if not repo_paths:
        _stderr.print(f"[yellow]No git repositories found under {root}[/yellow]")
        raise typer.Exit(0)

    repo_infos = _fetch_with_progress(repo_paths, no_color=no_color)

    # Attach tags from store
    for info in repo_infos:
        info.tag = store.get_tag(info.path)
        info.date_added = store.get_added_at(info.path)

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
        if local:
            fmt.render_local(repo_infos)
        elif compact:
            fmt.render_compact(repo_infos)
        else:
            fmt.render(repo_infos)


def _configure_logging(verbose: bool, log_file: Optional[Path]) -> None:
    from logging.handlers import RotatingFileHandler

    console_level = logging.DEBUG if verbose else logging.WARNING
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)

    log_path = log_file or DEFAULT_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        handlers: list[logging.Handler] = [console_handler, file_handler]
    except OSError:
        handlers = [console_handler]

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
