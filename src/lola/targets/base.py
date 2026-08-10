"""
base:
    ABC, base classes, mixins, and shared helpers for assistant targets.

This module provides:
- AssistantTarget ABC defining the interface for assistant targets
- BaseAssistantTarget with shared default implementations
- ManagedSectionTarget for targets using managed markdown sections
- ManagedInstructionsTarget mixin for managed instructions sections
- MCPSupportMixin for MCP support
- Shared helper functions used by multiple targets
"""

from __future__ import annotations

import json
import re
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import yaml

import lola.frontmatter as fm


_CLAUDE_TOOL_NAME_MAP: dict[str, str] = {
    "lsp": "LSP",
    "webfetch": "WebFetch",
    "websearch": "WebSearch",
    "notebookedit": "NotebookEdit",
    "askuserquestion": "AskUserQuestion",
    "enterplanmode": "EnterPlanMode",
    "exitplanmode": "ExitPlanMode",
    "enterworktree": "EnterWorktree",
    "exitworktree": "ExitWorktree",
    "taskcreate": "TaskCreate",
    "taskget": "TaskGet",
    "tasklist": "TaskList",
    "taskupdate": "TaskUpdate",
    "taskoutput": "TaskOutput",
    "taskstop": "TaskStop",
    "croncreate": "CronCreate",
    "crondelete": "CronDelete",
    "cronlist": "CronList",
    "schedulewakeup": "ScheduleWakeup",
}


OPENCODE_ONLY_FIELDS = ("mode", "temperature")


def _transform_claude_agent_frontmatter(front: dict) -> dict:
    """Convert agent frontmatter fields to Claude/Cursor expected format.

    Normalises tools from any input dialect to a comma-separated string and
    strips fields that are foreign to Claude Code and Cursor (e.g. OpenCode's
    ``mode`` and ``temperature``).
    """
    tools = front.get("tools")
    if isinstance(tools, dict):
        enabled = [k for k, v in tools.items() if v]
        front["tools"] = ", ".join(_to_claude_tool_name(t) for t in enabled)
    elif isinstance(tools, list):
        front["tools"] = ", ".join(_to_claude_tool_name(str(t)) for t in tools if t)

    for field in OPENCODE_ONLY_FIELDS:
        front.pop(field, None)

    return front


def _to_claude_tool_name(name: str) -> str:
    """Map a lowercased tool name to its canonical Claude Code casing.

    Multi-word tools like ``webfetch`` must become ``WebFetch``, not
    ``Webfetch``.  Falls back to capitalising the first letter for
    single-word tools not in the map.
    """
    lowered = name.strip().lower()
    if lowered in _CLAUDE_TOOL_NAME_MAP:
        return _CLAUDE_TOOL_NAME_MAP[lowered]
    if lowered == "*":
        return "*"
    return lowered[0].upper() + lowered[1:] if lowered else lowered


def _resolve_source_content(source: Path | str | list[str]) -> str | None:
    """Resolve source to string content. Returns None if Path doesn't exist.

    Accepts a Path (read file), a str (use directly), or a list[str] (join as lines).
    """
    if isinstance(source, list):
        joined = "\n".join(source)
        return joined.strip() if joined else None
    if isinstance(source, Path):
        if not source.exists():
            return None
        return source.read_text(encoding="utf-8-sig").strip()
    elif isinstance(source, str):
        return source.strip()
    return None


# =============================================================================
# AssistantTarget ABC
# =============================================================================


class AssistantTarget(ABC):
    """Abstract base class defining the interface for assistant targets."""

    name: str
    supports_agents: bool
    uses_managed_section: (
        bool  # True if skills go into a managed section (e.g., GEMINI.md)
    )

    @abstractmethod
    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        """Get the skill output path for this assistant.

        Args:
            project_path: Project directory path (ignored for user scope)
            scope: "project" for project-local, "user" for user-global
        """
        ...

    @abstractmethod
    def get_command_path(
        self, project_path: str, scope: str = "project"
    ) -> Path | None:
        """Get the command output path for this assistant.

        Returns None if commands are not supported for the given scope.

        Args:
            project_path: Project directory path (ignored for user scope)
            scope: "project" for project-local, "user" for user-global
        """
        ...

    @abstractmethod
    def get_agent_path(self, project_path: str, scope: str = "project") -> Path | None:
        """Get the agent output path. Returns None if agents not supported.

        Args:
            project_path: Project directory path (ignored for user scope)
            scope: "project" for project-local, "user" for user-global
        """
        ...

    @abstractmethod
    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        """Get the instructions file path for this assistant.

        Args:
            project_path: Project directory path (ignored for user scope)
            scope: "project" for project-local, "user" for user-global
        """
        ...

    @abstractmethod
    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,
    ) -> bool:
        """Generate skill file(s) for this assistant."""
        ...

    @abstractmethod
    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Generate command file for this assistant."""
        ...

    @abstractmethod
    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Generate agent file for this assistant."""
        ...

    @abstractmethod
    def generate_instructions(
        self,
        source: Path | str | list[str],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in the assistant's instruction file.

        Args:
            source: Path to read content from, string content directly,
                    or list[str] of reference lines (for --append-context).
        """
        ...

    @abstractmethod
    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove skill file(s) for this assistant."""
        ...

    @abstractmethod
    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's instructions from the instruction file."""
        ...

    @abstractmethod
    def generate_skills_batch(
        self,
        dest_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],
        project_path: str | None,
    ) -> bool:
        """Generate skills as a batch (for managed section targets)."""
        ...

    @abstractmethod
    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        """Get the filename for a command."""
        ...

    @abstractmethod
    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Get the filename for an agent."""
        ...

    @abstractmethod
    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path | None:
        """Get the MCP config file path for this assistant. Returns None if not supported.

        Args:
            project_path: Project directory path (ignored for user scope)
            scope: "project" for project-local, "user" for user-global
        """
        ...

    @abstractmethod
    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/merge MCP servers into the config file."""
        ...

    @abstractmethod
    def remove_mcps(
        self,
        dest_path: Path,
        module_name: str,
        mcp_names: list[str] | None = None,
    ) -> bool:
        """Remove a module's MCP servers from the config file."""
        ...

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
            Returns True immediately if supports_agents is False.
        """
        ...


# =============================================================================
# BaseAssistantTarget - shared defaults
# =============================================================================


class BaseAssistantTarget(AssistantTarget):
    """Base class with shared default implementations."""

    name: str = ""
    supports_agents: bool = True
    uses_managed_section: bool = False

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path | None:  # noqa: ARG002
        """Default: no agent support. Override in subclasses."""
        return None

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:  # noqa: ARG002
        """Default: no instructions path. Override in subclasses."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_instructions_path()"
        )

    def generate_agent(
        self,
        source_path: Path,  # noqa: ARG002
        dest_dir: Path,  # noqa: ARG002
        agent_name: str,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        """Default: agents not supported."""
        return False

    def generate_instructions(
        self,
        source: Path | str | list[str],  # noqa: ARG002
        dest_path: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        """Default: instructions not supported. Override in subclasses."""
        return False

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Default: remove skill directory."""
        skill_dir = dest_path / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            return True
        return False

    def remove_instructions(
        self,
        dest_path: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        """Default: instructions removal not supported. Override in subclasses."""
        return False

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:  # noqa: ARG002
        """Default: cmd.md (no prefix)"""
        return f"{cmd_name}.md"

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:  # noqa: ARG002
        """Default: agent.md (no prefix)"""
        return f"{agent_name}.md"

    def generate_skills_batch(
        self,
        dest_file: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
        skills: list[tuple[str, str, Path]],  # noqa: ARG002
        project_path: str | None,  # noqa: ARG002
    ) -> bool:
        """Default: batch generation not supported."""
        return False

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path | None:  # noqa: ARG002
        """Default: MCP not supported. Override in subclasses."""
        return None

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],  # noqa: ARG002
        dest_path: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        """Default: MCP not supported. Override in subclasses."""
        return False

    def remove_mcps(
        self,
        dest_path: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
        mcp_names: list[str] | None = None,  # noqa: ARG002
    ) -> bool:
        """Default: MCP removal not supported. Override in subclasses."""
        return False

    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Delete command file and co-named sidecar directory at expected path.

        Removes the current unprefixed file and, when present alongside it,
        also removes the legacy prefixed file ({module_name}.{cmd_name}.ext)
        left over from pre-prefix-removal installs.  Any co-named sidecar
        directory (e.g. ``deploy/`` next to ``deploy.md``) is also removed.

        Returns True if removed or didn't exist (idempotent).
        """
        filename = self.get_command_filename(module_name, cmd_name)
        cmd_file = dest_dir / filename
        if cmd_file.exists():
            cmd_file.unlink()
        # Remove co-named sidecar directory (e.g. deploy/ next to deploy.md)
        sidecar_dir = dest_dir / Path(filename).stem
        if sidecar_dir.is_dir():
            shutil.rmtree(sidecar_dir)
        # Always clean up legacy prefixed file too (e.g. module.cmd.md)
        ext = Path(filename).suffix
        legacy_file = dest_dir / f"{module_name}.{cmd_name}{ext}"
        if legacy_file.exists():
            legacy_file.unlink()
        return True

    def remove_agent(
        self,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Delete agent file at expected path.

        Removes the current unprefixed file and, when present alongside it,
        also removes the legacy prefixed file ({module_name}.{agent_name}.ext)
        left over from pre-prefix-removal installs.

        Returns True if removed or didn't exist (idempotent).
        Returns True immediately if supports_agents is False.
        """
        if not self.supports_agents:
            return True
        filename = self.get_agent_filename(module_name, agent_name)
        agent_file = dest_dir / filename
        if agent_file.exists():
            agent_file.unlink()
        # Always clean up legacy prefixed file too (e.g. module.agent.md)
        ext = Path(filename).suffix
        legacy_file = dest_dir / f"{module_name}.{agent_name}{ext}"
        if legacy_file.exists():
            legacy_file.unlink()
        return True


# =============================================================================
# ManagedSectionTarget - base for targets using managed markdown sections
# =============================================================================


class ManagedSectionTarget(BaseAssistantTarget):
    """Base class for targets that write skills to a managed section in a markdown file.

    Subclasses must define:
    - MANAGED_FILE: name of the file (e.g., "GEMINI.md", "AGENTS.md")
    - START_MARKER, END_MARKER: markers for the managed section
    - HEADER: header text for the managed section
    """

    uses_managed_section: bool = True

    # Subclasses must override these
    MANAGED_FILE: str = ""
    START_MARKER: str = "<!-- lola:skills:start -->"
    END_MARKER: str = "<!-- lola:skills:end -->"
    HEADER: str = """## Lola Skills

These skills are installed by Lola and provide specialized capabilities.
When a task matches a skill's description, read the skill's SKILL.md file
to learn the detailed instructions and workflows.

**How to use skills:**
1. Check if your task matches any skill description below
2. Use `read_file` to read the skill's SKILL.md for detailed instructions
3. Follow the instructions in the SKILL.md file

"""

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / self.MANAGED_FILE
        return Path(project_path) / self.MANAGED_FILE

    def generate_skill(
        self,
        source_path: Path,  # noqa: ARG002
        dest_path: Path,  # noqa: ARG002
        skill_name: str,  # noqa: ARG002
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Managed section targets use batch generation - this should not be called directly."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.generate_skill should not be called directly. "
            "Use generate_skills_batch() instead."
        )

    def generate_skills_batch(
        self,
        dest_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],
        project_path: str | None,
    ) -> bool:
        """Update managed markdown file with skill listings for a module."""
        if dest_file.exists():
            content = dest_file.read_text(encoding="utf-8-sig")
        else:
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            content = ""

        project_root = Path(project_path) if project_path else None

        # Build skills block for this module
        skills_block = f"\n### {module_name}\n\n"
        for skill_name, description, skill_path in skills:
            if project_root:
                try:
                    relative_path = skill_path.relative_to(project_root)
                    skill_md_path = relative_path / "SKILL.md"
                except ValueError:
                    skill_md_path = skill_path / "SKILL.md"
            else:
                skill_md_path = skill_path / "SKILL.md"
            skills_block += f"#### {skill_name}\n"
            skills_block += f"**When to use:** {description}\n"
            skills_block += (
                f"**Instructions:** Read `{skill_md_path}` for detailed guidance.\n\n"
            )

        # Update or create managed section
        if self.START_MARKER in content and self.END_MARKER in content:
            start_idx = content.index(self.START_MARKER)
            end_idx = content.index(self.END_MARKER) + len(self.END_MARKER)
            existing_section = content[start_idx:end_idx]
            section_content = existing_section[
                len(self.START_MARKER) : -len(self.END_MARKER)
            ]

            # Remove existing module section if present
            lines = section_content.split("\n")
            new_lines: list[str] = []
            skip_until_next_module = False
            for line in lines:
                if line.startswith("### "):
                    if line == f"### {module_name}":
                        skip_until_next_module = True
                        continue
                    skip_until_next_module = False
                if not skip_until_next_module:
                    new_lines.append(line)

            new_section = (
                self.START_MARKER
                + "\n".join(new_lines)
                + skills_block
                + self.END_MARKER
            )
            content = content[:start_idx] + new_section + content[end_idx:]
        else:
            lola_section = f"\n\n{self.HEADER}{self.START_MARKER}\n{skills_block}{self.END_MARKER}\n"
            content = content.rstrip() + lola_section

        dest_file.write_text(content, encoding="utf-8")
        return True

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove a module's skills from the managed markdown file.

        Note: For managed section targets, dest_path is the markdown file and
        skill_name is the module name (skills are grouped by module).
        """
        if not dest_path.exists():
            return True

        content = dest_path.read_text(encoding="utf-8-sig")
        if self.START_MARKER not in content or self.END_MARKER not in content:
            return True

        start_idx = content.index(self.START_MARKER)
        end_idx = content.index(self.END_MARKER) + len(self.END_MARKER)
        existing_section = content[start_idx:end_idx]
        section_content = existing_section[
            len(self.START_MARKER) : -len(self.END_MARKER)
        ]

        # Remove module section (skill_name is actually module_name)
        module_name = skill_name
        lines = section_content.split("\n")
        new_lines: list[str] = []
        skip_until_next_module = False
        for line in lines:
            if line.startswith("### "):
                if line == f"### {module_name}":
                    skip_until_next_module = True
                    continue
                skip_until_next_module = False
            if not skip_until_next_module:
                new_lines.append(line)

        new_section = self.START_MARKER + "\n".join(new_lines) + self.END_MARKER
        content = content[:start_idx] + new_section + content[end_idx:]
        dest_path.write_text(content, encoding="utf-8")
        return True


# =============================================================================
# ManagedInstructionsTarget - mixin for managed instructions sections
# =============================================================================


class ManagedInstructionsTarget:
    """Mixin for targets that use managed sections for module instructions.

    This provides shared logic for inserting/removing module instructions
    into markdown files like CLAUDE.md, GEMINI.md, AGENTS.md.
    """

    INSTRUCTIONS_START_MARKER: str = "<!-- lola:instructions:start -->"
    INSTRUCTIONS_END_MARKER: str = "<!-- lola:instructions:end -->"
    MODULE_START_MARKER_FMT: str = "<!-- lola:module:{module_name}:start -->"
    MODULE_END_MARKER_FMT: str = "<!-- lola:module:{module_name}:end -->"

    def _get_module_markers(self, module_name: str) -> tuple[str, str]:
        """Get the start/end markers for a specific module."""
        start = self.MODULE_START_MARKER_FMT.format(module_name=module_name)
        end = self.MODULE_END_MARKER_FMT.format(module_name=module_name)
        return start, end

    def generate_instructions(
        self,
        source: Path | str | list[str],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in a managed section."""
        instructions_content = _resolve_source_content(source)
        if not instructions_content:
            return False

        # Read existing file content
        if dest_path.exists():
            content = dest_path.read_text(encoding="utf-8-sig")
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            content = ""

        module_start, module_end = self._get_module_markers(module_name)

        # Build the module block
        module_block = f"{module_start}\n{instructions_content}\n{module_end}"

        # Check if managed section exists
        if (
            self.INSTRUCTIONS_START_MARKER in content
            and self.INSTRUCTIONS_END_MARKER in content
        ):
            start_idx = content.index(self.INSTRUCTIONS_START_MARKER)
            end_idx = content.index(self.INSTRUCTIONS_END_MARKER) + len(
                self.INSTRUCTIONS_END_MARKER
            )
            existing_section = content[start_idx:end_idx]
            section_content = existing_section[
                len(self.INSTRUCTIONS_START_MARKER) : -len(self.INSTRUCTIONS_END_MARKER)
            ]

            # Remove existing module section if present
            if module_start in section_content:
                mod_start_idx = section_content.index(module_start)
                mod_end_idx = section_content.index(module_end) + len(module_end)
                section_content = (
                    section_content[:mod_start_idx] + section_content[mod_end_idx:]
                )

            # Collect all module blocks and sort them alphabetically
            module_blocks = self._extract_module_blocks(section_content)
            module_blocks[module_name] = module_block

            # Build new section with sorted modules
            sorted_blocks = [
                module_blocks[name] for name in sorted(module_blocks.keys())
            ]
            new_section_content = "\n\n".join(sorted_blocks)
            if new_section_content:
                new_section_content = "\n" + new_section_content + "\n"

            new_section = (
                self.INSTRUCTIONS_START_MARKER
                + new_section_content
                + self.INSTRUCTIONS_END_MARKER
            )
            content = content[:start_idx] + new_section + content[end_idx:]
        else:
            # Create new managed section at the end
            new_section = (
                f"\n\n{self.INSTRUCTIONS_START_MARKER}\n{module_block}\n"
                f"{self.INSTRUCTIONS_END_MARKER}\n"
            )
            content = content.rstrip() + new_section

        dest_path.write_text(content, encoding="utf-8")
        return True

    def _extract_module_blocks(self, section_content: str) -> dict[str, str]:
        """Extract individual module blocks from section content."""
        blocks: dict[str, str] = {}
        pattern = r"<!-- lola:module:([^:]+):start -->(.*?)<!-- lola:module:\1:end -->"
        for match in re.finditer(pattern, section_content, re.DOTALL):
            module_name = match.group(1)
            full_block = match.group(0)
            blocks[module_name] = full_block.strip()
        return blocks

    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's instructions from the managed section."""
        if not dest_path.exists():
            return True

        content = dest_path.read_text(encoding="utf-8-sig")
        if (
            self.INSTRUCTIONS_START_MARKER not in content
            or self.INSTRUCTIONS_END_MARKER not in content
        ):
            return True

        module_start, module_end = self._get_module_markers(module_name)

        start_idx = content.index(self.INSTRUCTIONS_START_MARKER)
        end_idx = content.index(self.INSTRUCTIONS_END_MARKER) + len(
            self.INSTRUCTIONS_END_MARKER
        )
        existing_section = content[start_idx:end_idx]
        section_content = existing_section[
            len(self.INSTRUCTIONS_START_MARKER) : -len(self.INSTRUCTIONS_END_MARKER)
        ]

        # Remove module section if present
        if module_start in section_content:
            mod_start_idx = section_content.index(module_start)
            mod_end_idx = section_content.index(module_end) + len(module_end)
            section_content = (
                section_content[:mod_start_idx] + section_content[mod_end_idx:]
            )
            # Clean up extra newlines
            section_content = re.sub(r"\n{3,}", "\n\n", section_content)

        # Check if any module blocks remain
        remaining_blocks = self._extract_module_blocks(section_content)
        if remaining_blocks:
            new_section = (
                self.INSTRUCTIONS_START_MARKER
                + section_content
                + self.INSTRUCTIONS_END_MARKER
            )
            content = content[:start_idx] + new_section + content[end_idx:]
        else:
            # No modules left - remove the entire managed section and leading newlines
            prefix = content[:start_idx].rstrip("\n")
            suffix = content[end_idx:]
            content = prefix + suffix

        dest_path.write_text(content, encoding="utf-8")
        return True


# =============================================================================
# MCPSupportMixin
# =============================================================================


class MCPSupportMixin:
    """Mixin for targets that support MCP servers.

    Subclasses must define get_mcp_path().
    """

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/merge MCP servers into the config file."""
        if not mcps:
            return False
        return _merge_mcps_into_file(dest_path, module_name, mcps)

    def remove_mcps(
        self,
        dest_path: Path,
        module_name: str,
        mcp_names: list[str] | None = None,
    ) -> bool:
        """Remove a module's MCP servers from the config file."""
        return _remove_mcps_from_file(dest_path, module_name, mcp_names)


# =============================================================================
# Shared helper functions
# =============================================================================


def _get_skill_description(source_path: Path) -> str:
    """Extract description from SKILL.md frontmatter."""
    skill_file = source_path / "SKILL.md"
    if not skill_file.exists():
        return ""
    return fm.get_description(skill_file) or ""


def _generate_passthrough_command(
    source_path: Path,
    dest_dir: Path,
    filename: str,
) -> bool:
    """Generate command by copying content as-is.

    Also copies a co-named sidecar directory if present.  For example,
    if ``source_path`` is ``commands/deploy.md`` and a directory
    ``commands/deploy/`` exists, the entire directory is copied next to
    the generated command file.
    """
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text(encoding="utf-8-sig")
    (dest_dir / filename).write_text(content, encoding="utf-8")

    # Copy co-named sidecar directory (e.g. commands/deploy/ alongside
    # commands/deploy.md).
    sidecar_src = source_path.with_suffix("")
    if sidecar_src.is_dir():
        sidecar_dest = dest_dir / Path(filename).stem
        if sidecar_dest.exists():
            shutil.rmtree(sidecar_dest)
        shutil.copytree(sidecar_src, sidecar_dest)

    return True


def _generate_agent_with_frontmatter(
    source_path: Path,
    dest_dir: Path,
    filename: str,
    frontmatter_additions: dict,
    frontmatter_transforms: Callable[[dict], dict] | None = None,
) -> bool:
    """Generate agent file with additional frontmatter fields.

    Args:
        frontmatter_transforms: Optional callback applied after merging
            frontmatter_additions. Receives the merged dict, returns the
            final dict to write. Use for target-specific field conversions.
    """
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)

    content = source_path.read_text(encoding="utf-8-sig")
    frontmatter, body = fm.parse(content)
    frontmatter.update(frontmatter_additions)

    if frontmatter_transforms is not None:
        frontmatter = frontmatter_transforms(frontmatter)

    frontmatter_str = yaml.dump(
        frontmatter, default_flow_style=False, sort_keys=False
    ).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    (dest_dir / filename).write_text(content, encoding="utf-8")
    return True


def _get_content_path(
    local_module_path: Path, content_dirname: Optional[str] = None
) -> Path:
    """Get the content path for a local module.

    Args:
        local_module_path: Path to the copied module in .lola/modules/
        content_dirname: Subdirectory containing module content (e.g., "lola-module", "module")
                        None = auto-detect using standard candidates

    Returns:
        Path to the content directory
    """
    # If explicit content_dirname provided, use it
    if content_dirname:
        content_path = local_module_path / content_dirname
        if content_path.exists() and content_path.is_dir():
            return content_path

    # Standard content directory names to try (in order of preference)
    # Add new standard directory names here to support additional conventions
    CONTENT_DIR_CANDIDATES = ["module", "lola-module"]

    for candidate in CONTENT_DIR_CANDIDATES:
        candidate_path = local_module_path / candidate
        if candidate_path.exists() and candidate_path.is_dir():
            return candidate_path

    # Fallback: use root module path
    return local_module_path


def _skill_source_dir(
    local_module_path: Path, skill_name: str, content_dirname: Optional[str] = None
) -> Path:
    """Find the source directory for a skill.

    Handles:
    1. Single skill (agentskills.io standard): SKILL.md at content_path root
    2. Skill bundle: skills/ subdirectory
    3. Legacy: skill at module root
    """
    content_path = _get_content_path(local_module_path, content_dirname)

    # Check for single skill at content_path root
    from lola.config import SKILL_FILE

    single_skill_file = content_path / SKILL_FILE
    if single_skill_file.exists() and single_skill_file.is_file():
        return content_path

    # Check for skill bundle
    bundle_skill_dir = content_path / "skills" / skill_name
    if bundle_skill_dir.exists():
        return bundle_skill_dir

    # Legacy fallback
    return local_module_path / skill_name


def _merge_mcps_into_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001 - kept for API symmetry, not used
    mcps: dict[str, dict[str, Any]],
) -> bool:
    """Merge MCP servers into a config file.

    Args:
        dest_path: Path to config file
        module_name: Unused; retained for interface symmetry with remove helper
        mcps: Dict of server_name -> server_config (keys written as-is, no prefix)
    """
    # Read existing config
    if dest_path.exists():
        try:
            existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            existing_config = {}
    else:
        existing_config = {}

    # Ensure mcpServers exists
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}

    # Add servers (no prefix)
    for name, server_config in mcps.items():
        existing_config["mcpServers"][name] = server_config

    # Write back
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(existing_config, indent=2) + "\n", encoding="utf-8")
    return True


def _remove_mcps_from_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001 - kept for API symmetry, not used
    mcp_names: list[str] | None = None,
) -> bool:
    """Remove specific MCP servers by name from a config file.

    The ``mcp_names`` list determines which entries under ``mcpServers`` are
    removed from the JSON config at ``dest_path``. If ``mcp_names`` is ``None``
    or empty, the file is left unchanged.

    ``module_name`` is currently unused and retained only for interface
    symmetry with the merge helper.
    """
    if not mcp_names:  # handles None and empty list — nothing to remove
        return True

    if not dest_path.exists():
        return True

    try:
        existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return True

    if "mcpServers" not in existing_config:
        return True

    for name in mcp_names:
        existing_config["mcpServers"].pop(name, None)

    # Write back (or delete if mcpServers is empty and only $schema remains)
    remaining_keys = {k for k in existing_config.keys() if k != "$schema"}
    if not existing_config["mcpServers"] and remaining_keys == {"mcpServers"}:
        dest_path.unlink()
    else:
        dest_path.write_text(
            json.dumps(existing_config, indent=2) + "\n", encoding="utf-8"
        )
    return True
