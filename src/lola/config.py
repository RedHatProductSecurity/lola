"""
config:
    Configuration and paths for the lola package manager
"""

from pathlib import Path
import os

# Base lola directory
LOLA_HOME = Path(os.environ.get('LOLA_HOME', Path.home() / '.lola'))

# Where modules are stored after being added
MODULES_DIR = LOLA_HOME / 'modules'

# Installation tracking file
INSTALLED_FILE = LOLA_HOME / 'installed.yml'

# Module manifest filename (inside each module)
MODULE_MANIFEST = '.lola/module.yml'

# Skill definition filename
SKILL_FILE = 'SKILL.md'

# Supported AI assistants and their skill directories
ASSISTANTS = {
    'claude-code': {
        'user': Path.home() / '.claude' / 'skills',
        'project': lambda path: Path(path) / '.claude' / 'skills',
    },
    'gemini-cli': {
        # Gemini uses a single GEMINI.md file, not a skills directory
        'user': Path.home() / '.gemini' / 'GEMINI.md',
        'project': lambda path: Path(path) / 'GEMINI.md',
    },
    'cursor': {
        'user': Path.home() / '.cursor' / 'rules',
        'project': lambda path: Path(path) / '.cursor' / 'rules',
    },
}

# Supported source types
SOURCE_TYPES = ['git', 'zip', 'tar', 'folder']


def get_assistant_skill_path(assistant: str, scope: str, project_path: str = None) -> Path:
    """
    Get the skill installation path for an assistant.

    Args:
        assistant: Name of the AI assistant
        scope: 'user' or 'project'
        project_path: Path to project (required if scope is 'project')

    Returns:
        Path to the skills directory
    """
    if assistant not in ASSISTANTS:
        raise ValueError(f"Unknown assistant: {assistant}. Supported: {list(ASSISTANTS.keys())}")

    if scope == 'project':
        if not project_path:
            raise ValueError("Project path required for project scope")
        return ASSISTANTS[assistant]['project'](project_path)

    return ASSISTANTS[assistant]['user']
