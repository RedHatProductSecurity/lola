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
    PluginLayout,
    _convert_env_var_to_cursor_vscode,
    _convert_env_var_to_opencode,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
    _get_content_path,
    _get_skill_description,
    _merge_mcps_into_file,
    _remove_mcps_from_file,
    _skill_source_dir,
    _transform_mcp_env_vars,
)

# Concrete target implementations
from lola.targets.claude_code import ClaudeCodeTarget
from lola.targets.copilot import CopilotCliTarget, CopilotVSCodeTarget
from lola.targets.cursor import CursorTarget
from lola.targets.gemini import GeminiTarget, _convert_to_gemini_args
from lola.targets.openclaw import OpenClawTarget
from lola.targets.opencode import OpenCodeTarget

# Install functions and console (for test mocking)
from lola.targets.install import (
    console,
    copy_module_to_local,
    get_registry,
    install_to_assistant,
    uninstall_from_assistant,
)

# =============================================================================
# Target Registry
# =============================================================================

TARGETS: dict[str, AssistantTarget] = {
    "claude-code": ClaudeCodeTarget(),
    "copilot-cli": CopilotCliTarget(),
    "copilot-vscode": CopilotVSCodeTarget(),
    "cursor": CursorTarget(),
    "gemini-cli": GeminiTarget(),
    "openclaw": OpenClawTarget(),
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


# Targets skipped when expanding to "all assistants" implicitly (sync, or a
# non-interactive install with no -a). copilot-cli and copilot-vscode write the
# same project-scope .github/ files and differ only in MCP handling, so an
# implicit install of both collides. We prefer the project-granular
# copilot-vscode; copilot-cli remains explicitly selectable via -a.
_IMPLICIT_ALL_EXCLUDE = {"copilot-cli"}


def default_assistants() -> list[str]:
    """Assistant names to use when none is explicitly selected.

    Excludes targets that would collide with a more granular sibling when
    installed implicitly (see ``_IMPLICIT_ALL_EXCLUDE``).
    """
    return [name for name in TARGETS if name not in _IMPLICIT_ALL_EXCLUDE]


__all__ = [
    # ABC and base classes
    "AssistantTarget",
    "BaseAssistantTarget",
    "ManagedInstructionsTarget",
    "ManagedSectionTarget",
    "MCPSupportMixin",
    "PluginLayout",
    # Concrete targets
    "ClaudeCodeTarget",
    "CopilotCliTarget",
    "CopilotVSCodeTarget",
    "CursorTarget",
    "GeminiTarget",
    "OpenClawTarget",
    "OpenCodeTarget",
    # Registry
    "TARGETS",
    "get_target",
    "get_registry",
    "default_assistants",
    # Install functions
    "console",
    "copy_module_to_local",
    "install_to_assistant",
    "uninstall_from_assistant",
    # Helpers (used by tests and cli/install.py)
    "_get_content_path",
    "_get_skill_description",
    "_skill_source_dir",
    "_convert_to_gemini_args",
    "_generate_passthrough_command",
    "_generate_agent_with_frontmatter",
    "_merge_mcps_into_file",
    "_remove_mcps_from_file",
    "_convert_env_var_to_cursor_vscode",
    "_convert_env_var_to_opencode",
    "_transform_mcp_env_vars",
]
