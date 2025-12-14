"""
config:
    Configuration and paths for the lola package manager
"""

from pathlib import Path
import os

# Base lola directory
LOLA_HOME = Path(os.environ.get("LOLA_HOME", Path.home() / ".lola"))

# Where modules are stored after being added
MODULES_DIR = LOLA_HOME / "modules"

# Installation tracking file
INSTALLED_FILE = LOLA_HOME / "installed.yml"

# Skill definition filename
SKILL_FILE = "SKILL.md"
