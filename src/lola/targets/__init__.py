"""
targets:
    Target assistants + installation logic for lola.

This module provides:
- AssistantTarget ABC defining the interface for assistant targets
- Concrete implementations for each supported assistant
- TARGETS registry for looking up targets by name
- Installation orchestration (install_to_assistant, copy_module_to_local)
"""

from lola.exceptions import UnknownAssistantError

# Base classes and shared helpers
from lola.targets.base import (
    AssistantTarget,
    BaseAssistantTarget,
    ManagedInstructionsTarget,
    ManagedSectionTarget,
    MCPSupportMixin,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
    _get_content_path,
    _get_skill_description,
    _merge_mcps_into_file,
    _remove_mcps_from_file,
    _skill_source_dir,
)

# Concrete target implementations
from lola.targets.claude_code import ClaudeCodeTarget
from lola.targets.cursor import CursorTarget, _rewrite_relative_paths
from lola.targets.gemini import GeminiTarget, _convert_to_gemini_args
from lola.targets.opencode import OpenCodeTarget

# Install functions and console (for test mocking)
from lola.targets.install import (
    console,
    copy_module_to_local,
    get_registry,
    install_to_assistant,
)

# =============================================================================
# Target Registry
# =============================================================================

TARGETS: dict[str, AssistantTarget] = {
    "claude-code": ClaudeCodeTarget(),
    "cursor": CursorTarget(),
    "gemini-cli": GeminiTarget(),
    "opencode": OpenCodeTarget(),
}


def get_target(assistant: str) -> AssistantTarget:
    """Get a target by name.

    Raises:
        UnknownAssistantError: If the assistant is not supported.
    """
    if assistant not in TARGETS:
        raise UnknownAssistantError(assistant, list(TARGETS.keys()))
    return TARGETS[assistant]


__all__ = [
    # ABC and base classes
    "AssistantTarget",
    "BaseAssistantTarget",
    "ManagedInstructionsTarget",
    "ManagedSectionTarget",
    "MCPSupportMixin",
    # Concrete targets
    "ClaudeCodeTarget",
    "CursorTarget",
    "GeminiTarget",
    "OpenCodeTarget",
    # Registry
    "TARGETS",
    "get_target",
    "get_registry",
    # Install functions
    "console",
    "copy_module_to_local",
    "install_to_assistant",
    # Helpers (used by tests and cli/install.py)
    "_get_content_path",
    "_get_skill_description",
    "_skill_source_dir",
    "_rewrite_relative_paths",
    "_convert_to_gemini_args",
    "_generate_passthrough_command",
    "_generate_agent_with_frontmatter",
    "_merge_mcps_into_file",
    "_remove_mcps_from_file",
]
