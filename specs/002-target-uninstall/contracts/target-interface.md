# Contract: AssistantTarget Interface

**Feature**: 002-target-uninstall
**Date**: 2025-12-18

## Overview

This contract defines the extended `AssistantTarget` interface with new removal methods for commands and agents.

## Interface Definition

### AssistantTarget ABC

```python
from abc import ABC, abstractmethod
from pathlib import Path

class AssistantTarget(ABC):
    """Abstract base class defining the interface for assistant targets."""

    name: str
    supports_agents: bool
    uses_managed_section: bool

    # ==========================================================================
    # Path Methods (existing)
    # ==========================================================================

    @abstractmethod
    def get_skill_path(self, project_path: str) -> Path: ...

    @abstractmethod
    def get_command_path(self, project_path: str) -> Path: ...

    @abstractmethod
    def get_agent_path(self, project_path: str) -> Path | None: ...

    @abstractmethod
    def get_instructions_path(self, project_path: str) -> Path: ...

    @abstractmethod
    def get_mcp_path(self, project_path: str) -> Path | None: ...

    # ==========================================================================
    # Filename Methods (existing)
    # ==========================================================================

    @abstractmethod
    def get_command_filename(self, module_name: str, cmd_name: str) -> str: ...

    @abstractmethod
    def get_agent_filename(self, module_name: str, agent_name: str) -> str: ...

    # ==========================================================================
    # Generation Methods (existing)
    # ==========================================================================

    @abstractmethod
    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,
    ) -> bool: ...

    @abstractmethod
    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool: ...

    @abstractmethod
    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool: ...

    @abstractmethod
    def generate_instructions(
        self,
        source_path: Path,
        dest_path: Path,
        module_name: str,
    ) -> bool: ...

    @abstractmethod
    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool: ...

    @abstractmethod
    def generate_skills_batch(
        self,
        dest_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],
        project_path: str | None,
    ) -> bool: ...

    # ==========================================================================
    # Removal Methods (existing)
    # ==========================================================================

    @abstractmethod
    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove skill file(s) for this assistant.

        Args:
            dest_path: Path to skill directory or managed file
            skill_name: Name of skill to remove (or module name for managed sections)

        Returns:
            True if removed or didn't exist, False on error
        """
        ...

    @abstractmethod
    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's instructions from the instruction file.

        Args:
            dest_path: Path to instructions file
            module_name: Name of module whose instructions to remove

        Returns:
            True if removed or didn't exist, False on error
        """
        ...

    @abstractmethod
    def remove_mcps(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's MCP servers from the config file.

        Args:
            dest_path: Path to MCP config file
            module_name: Name of module whose MCPs to remove

        Returns:
            True if removed or didn't exist, False on error
        """
        ...

    # ==========================================================================
    # NEW: Removal Methods for Commands and Agents (FR-001, FR-002)
    # ==========================================================================

    @abstractmethod
    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Remove a command file for this assistant.

        Args:
            dest_dir: Directory containing commands (e.g., .claude/commands/)
            cmd_name: Unprefixed command name (e.g., "review-pr")
            module_name: Module name for filename construction

        Returns:
            True if removed or didn't exist (idempotent), False on error

        Note:
            Uses get_command_filename() to determine the actual filename.
            Must be idempotent - returning True when file doesn't exist.
        """
        ...

    @abstractmethod
    def remove_agent(
        self,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Remove an agent file for this assistant.

        Args:
            dest_dir: Directory containing agents (e.g., .claude/agents/)
            agent_name: Unprefixed agent name (e.g., "code-reviewer")
            module_name: Module name for filename construction

        Returns:
            True if removed or didn't exist (idempotent), False on error

        Note:
            Uses get_agent_filename() to determine the actual filename.
            Must be idempotent - returning True when file doesn't exist.
            Returns True immediately if supports_agents is False.
        """
        ...
```

## Default Implementations (BaseAssistantTarget)

```python
class BaseAssistantTarget(AssistantTarget):
    """Base class with shared default implementations."""

    # ... existing defaults ...

    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Default: delete command file at expected path."""
        filename = self.get_command_filename(module_name, cmd_name)
        cmd_file = dest_dir / filename
        if cmd_file.exists():
            cmd_file.unlink()
        return True

    def remove_agent(
        self,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Default: delete agent file at expected path."""
        if not self.supports_agents:
            return True
        filename = self.get_agent_filename(module_name, agent_name)
        agent_file = dest_dir / filename
        if agent_file.exists():
            agent_file.unlink()
        return True
```

## Behavioral Contract

### Idempotency (FR-007)

All removal methods MUST be idempotent:

| State Before | Operation | Result | Return |
|--------------|-----------|--------|--------|
| File exists | remove_*() | File deleted | True |
| File does not exist | remove_*() | No change | True |
| Directory does not exist | remove_*() | No change | True |
| Error during deletion | remove_*() | Partial state | False |

### Error Handling

- File permission errors: Return `False`, do not raise
- Path not found: Return `True` (idempotent)
- I/O errors: Return `False`, do not raise

### Thread Safety

Not guaranteed. Callers should not invoke removal methods concurrently on the same files.

## Target-Specific Overrides

Most targets inherit defaults. Document any overrides here:

| Target | Method | Override Reason |
|--------|--------|-----------------|
| (none currently) | - | - |

Future targets may override if they use managed sections for commands/agents.
