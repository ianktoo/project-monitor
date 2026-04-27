"""Output formatter protocol and public API.

To create a custom formatter, implement the OutputFormatter protocol:

    from project_monitor.formatters import OutputFormatter
    from project_monitor.models import RepoInfo

    class MyFormatter:
        def render(self, repos: list[RepoInfo]) -> None:
            for repo in repos:
                print(f"{'OK' if repo.is_clean else 'DIRTY'} {repo.name}")

Any object with a ``render(self, repos: list[RepoInfo]) -> None`` method
satisfies the protocol.  No registration or subclassing is required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from project_monitor.models import RepoInfo

__all__ = ["OutputFormatter"]


@runtime_checkable
class OutputFormatter(Protocol):
    """Protocol that all output formatters must satisfy.

    Implement this single method to create a custom formatter. The formatter
    receives the complete list of scanned RepoInfo objects and is responsible
    for all output (print to terminal, write to file, POST to a webhook, etc).
    """

    def render(self, repos: list[RepoInfo]) -> None:
        """Render the repository list.

        Args:
            repos: All discovered repositories, in scan order.
        """
        ...
