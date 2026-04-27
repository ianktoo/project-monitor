"""project-monitor: scan a folder for git repos and view their status at a glance."""

from project_monitor.models import RepoInfo
from project_monitor.formatters import OutputFormatter

__version__ = "0.1.0"
__all__ = ["RepoInfo", "OutputFormatter", "__version__"]
