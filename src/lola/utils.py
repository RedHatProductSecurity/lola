"""
utils:
    Utility functions for lola package manager
"""

from pathlib import Path
from typing import Optional

from lola.config import LOLA_HOME, MODULES_DIR


def ensure_lola_dirs():
    """Ensure the lola directories exist."""
    LOLA_HOME.mkdir(parents=True, exist_ok=True)
    MODULES_DIR.mkdir(parents=True, exist_ok=True)


def get_local_modules_path(project_path: Optional[str]) -> Path:
    """
    Get the path to .lola/modules/ for a given scope.

    Args:
        project_path: Project path for project scope, None for user scope

    Returns:
        Path to .lola/modules/
    """
    if project_path:
        return Path(project_path) / ".lola" / "modules"
    return Path.home() / ".lola" / "modules"
