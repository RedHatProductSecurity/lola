"""
CLI commands for lola.

This package contains all Click command definitions.
"""

from lola.cli.install import (
    install_cmd,
    uninstall_cmd,
    update_cmd,
    list_installed_cmd,
)
from lola.cli.mod import mod

__all__ = [
    "install_cmd",
    "uninstall_cmd",
    "update_cmd",
    "list_installed_cmd",
    "mod",
]
