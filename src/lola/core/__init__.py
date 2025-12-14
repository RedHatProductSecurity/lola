"""
Core business logic for lola.

This package contains the core operations:
- installer: Installation and uninstallation logic
- generator: File generation for all assistants
"""

from lola.core.installer import (
    copy_module_to_local,
    install_to_assistant,
    get_registry,
)
from lola.core.generator import (
    generate_claude_skill,
    generate_cursor_rule,
    generate_claude_command,
    generate_cursor_command,
    generate_gemini_command,
    get_skill_description,
    update_gemini_md,
    remove_gemini_skills,
)

__all__ = [
    # Installer
    "copy_module_to_local",
    "install_to_assistant",
    "get_registry",
    # Generator
    "generate_claude_skill",
    "generate_cursor_rule",
    "generate_claude_command",
    "generate_cursor_command",
    "generate_gemini_command",
    "get_skill_description",
    "update_gemini_md",
    "remove_gemini_skills",
]
