"""
exceptions:
    Custom exception hierarchy for lola.

This module defines a consistent exception hierarchy for error handling.
All lola-specific exceptions inherit from LolaError, making it easy to
catch all lola errors at the CLI layer.

Usage:
    - Raise specific exceptions in library code
    - Catch LolaError at CLI boundaries
    - Convert to user-friendly messages and exit codes at the CLI layer
"""

from pathlib import Path
from typing import Optional


class LolaError(Exception):
    """Base exception for all lola-specific errors.

    All lola exceptions inherit from this class, making it easy to catch
    all lola errors at the CLI layer with a single except clause.
    """

    pass


# =============================================================================
# Module-related exceptions
# =============================================================================


class ModuleNotFoundError(LolaError):
    """Raised when a module cannot be found in the registry."""

    def __init__(self, module_name: str, message: Optional[str] = None):
        self.module_name = module_name
        if message is None:
            message = f"Module '{module_name}' not found"
        super().__init__(message)


class ModuleInvalidError(LolaError):
    """Raised when a module exists but has no valid skills, commands, or agents."""

    def __init__(self, module_name: str, message: Optional[str] = None):
        self.module_name = module_name
        if message is None:
            message = f"Module '{module_name}' is invalid: no skills, commands, or agents found"
        super().__init__(message)


class ValidationError(LolaError):
    """Raised when module validation fails.

    Contains a list of specific validation errors.
    """

    def __init__(self, module_name: str, errors: list[str]):
        self.module_name = module_name
        self.errors = errors
        message = f"Module '{module_name}' has validation errors:\n" + "\n".join(
            f"  - {err}" for err in errors
        )
        super().__init__(message)


# =============================================================================
# Source-related exceptions
# =============================================================================


class SourceError(LolaError):
    """Raised when there's an error fetching or processing a module source."""

    def __init__(self, source: str, message: Optional[str] = None):
        self.source = source
        if message is None:
            message = f"Failed to process source: {source}"
        super().__init__(message)


class UnsupportedSourceError(SourceError):
    """Raised when a source type is not supported."""

    def __init__(self, source: str):
        self.source = source
        message = (
            f"Cannot handle source: {source}\n"
            "Supported sources: git repos, .zip/.tar URLs, local .zip/.tar files, or local folders"
        )
        super().__init__(source, message)


class SecurityError(SourceError):
    """Raised when a security violation is detected (e.g., path traversal)."""

    def __init__(self, message: str, source: Optional[str] = None):
        super().__init__(source or "unknown", message)


class ModuleNameError(LolaError):
    """Raised when a module name is invalid."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        message = f"Invalid module name '{name}': {reason}"
        super().__init__(message)


# =============================================================================
# Installation-related exceptions
# =============================================================================


class InstallationError(LolaError):
    """Raised when an installation operation fails."""

    def __init__(
        self,
        module_name: str,
        assistant: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.module_name = module_name
        self.assistant = assistant
        if message is None:
            if assistant:
                message = f"Failed to install '{module_name}' to {assistant}"
            else:
                message = f"Failed to install '{module_name}'"
        super().__init__(message)


class TargetError(LolaError):
    """Raised when a target operation fails.

    This is raised by target implementations (ClaudeCodeTarget, CursorTarget, etc.)
    when they fail to generate skills, commands, or agents.
    """

    def __init__(
        self,
        operation: str,
        target_name: str,
        source_path: Optional[Path] = None,
        reason: Optional[str] = None,
    ):
        self.operation = operation
        self.target_name = target_name
        self.source_path = source_path
        self.reason = reason

        parts = [f"Failed to {operation} for {target_name}"]
        if source_path:
            parts.append(f"source: {source_path}")
        if reason:
            parts.append(f"reason: {reason}")
        message = " - ".join(parts)
        super().__init__(message)


class SkillGenerationError(TargetError):
    """Raised when skill generation fails."""

    def __init__(
        self,
        skill_name: str,
        target_name: str,
        source_path: Optional[Path] = None,
        reason: Optional[str] = None,
    ):
        self.skill_name = skill_name
        super().__init__(
            f"generate skill '{skill_name}'", target_name, source_path, reason
        )


class CommandGenerationError(TargetError):
    """Raised when command generation fails."""

    def __init__(
        self,
        command_name: str,
        target_name: str,
        source_path: Optional[Path] = None,
        reason: Optional[str] = None,
    ):
        self.command_name = command_name
        super().__init__(
            f"generate command '{command_name}'", target_name, source_path, reason
        )


class AgentGenerationError(TargetError):
    """Raised when agent generation fails."""

    def __init__(
        self,
        agent_name: str,
        target_name: str,
        source_path: Optional[Path] = None,
        reason: Optional[str] = None,
    ):
        self.agent_name = agent_name
        super().__init__(
            f"generate agent '{agent_name}'", target_name, source_path, reason
        )


# =============================================================================
# Path-related exceptions
# =============================================================================


class PathError(LolaError):
    """Raised when there's an error with a file or directory path."""

    def __init__(self, path: Path | str, message: Optional[str] = None):
        self.path = Path(path) if isinstance(path, str) else path
        if message is None:
            message = f"Path error: {path}"
        super().__init__(message)


class PathNotFoundError(PathError):
    """Raised when a required path doesn't exist."""

    def __init__(self, path: Path | str, description: str = "Path"):
        super().__init__(path, f"{description} does not exist: {path}")


class PathExistsError(PathError):
    """Raised when a path already exists but shouldn't."""

    def __init__(self, path: Path | str, description: str = "Path"):
        super().__init__(path, f"{description} already exists: {path}")


# =============================================================================
# Configuration exceptions
# =============================================================================


class ConfigurationError(LolaError):
    """Raised when there's a configuration problem."""

    pass


class UnknownAssistantError(ConfigurationError):
    """Raised when an unknown assistant is specified."""

    def __init__(self, assistant: str, supported: list[str]):
        self.assistant = assistant
        self.supported = supported
        message = f"Unknown assistant: {assistant}. Supported: {supported}"
        super().__init__(message)


