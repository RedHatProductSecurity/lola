"""
layout defines the display format of parsed data

This module re-exports the console from ui.py for backward compatibility.
New code should import from lola.ui directly.
"""

from lola.ui import console

__all__ = ["console"]
