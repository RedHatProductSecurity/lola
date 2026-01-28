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
from pathlib import Path
from typing import Any

import yaml

import lola.frontmatter as fm


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
    def get_skill_path(self, project_path: str) -> Path:
        """Get the skill output path for this assistant."""
        ...

    @abstractmethod
    def get_command_path(self, project_path: str) -> Path:
        """Get the command output path for this assistant."""
        ...

    @abstractmethod
    def get_agent_path(self, project_path: str) -> Path | None:
        """Get the agent output path. Returns None if agents not supported."""
        ...

    @abstractmethod
    def get_instructions_path(self, project_path: str) -> Path:
        """Get the instructions file path for this assistant."""
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
        source_path: Path,
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in the assistant's instruction file."""
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
    def get_mcp_path(self, project_path: str) -> Path | None:
        """Get the MCP config file path for this assistant. Returns None if not supported."""
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
    def remove_mcps(self, dest_path: Path, module_name: str) -> bool:
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

    def get_agent_path(self, project_path: str) -> Path | None:  # noqa: ARG002
        """Default: no agent support. Override in subclasses."""
        return None

    def get_instructions_path(self, project_path: str) -> Path:  # noqa: ARG002
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
        source_path: Path,  # noqa: ARG002
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

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        """Default: module.cmd.md (dot-separated)"""
        return f"{module_name}.{cmd_name}.md"

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Default: module.agent.md (dot-separated)"""
        return f"{module_name}.{agent_name}.md"

    def generate_skills_batch(
        self,
        dest_file: Path,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
        skills: list[tuple[str, str, Path]],  # noqa: ARG002
        project_path: str | None,  # noqa: ARG002
    ) -> bool:
        """Default: batch generation not supported."""
        return False

    def get_mcp_path(self, project_path: str) -> Path | None:  # noqa: ARG002
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
    ) -> bool:
        """Default: MCP removal not supported. Override in subclasses."""
        return False

    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Default: delete command file at expected path.

        Returns True if removed or didn't exist (idempotent).
        """
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
        """Default: delete agent file at expected path.

        Returns True if removed or didn't exist (idempotent).
        Returns True immediately if supports_agents is False.
        """
        if not self.supports_agents:
            return True
        filename = self.get_agent_filename(module_name, agent_name)
        agent_file = dest_dir / filename
        if agent_file.exists():
            agent_file.unlink()
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

    def get_skill_path(self, project_path: str) -> Path:
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
            content = dest_file.read_text()
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

        dest_file.write_text(content)
        return True

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove a module's skills from the managed markdown file.

        Note: For managed section targets, dest_path is the markdown file and
        skill_name is the module name (skills are grouped by module).
        """
        if not dest_path.exists():
            return True

        content = dest_path.read_text()
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
        dest_path.write_text(content)
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
        source_path: Path,
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in a managed section."""
        if not source_path.exists():
            return False

        instructions_content = source_path.read_text().strip()
        if not instructions_content:
            return False

        # Read existing file content
        if dest_path.exists():
            content = dest_path.read_text()
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

        dest_path.write_text(content)
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

        content = dest_path.read_text()
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

        dest_path.write_text(content)
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

    def remove_mcps(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's MCP servers from the config file."""
        return _remove_mcps_from_file(dest_path, module_name)


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
    """Generate command by copying content as-is."""
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text()
    (dest_dir / filename).write_text(content)
    return True


def _generate_agent_with_frontmatter(
    source_path: Path,
    dest_dir: Path,
    filename: str,
    frontmatter_additions: dict,
) -> bool:
    """Generate agent file with additional frontmatter fields."""
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)

    content = source_path.read_text()
    frontmatter, body = fm.parse(content)
    frontmatter.update(frontmatter_additions)

    frontmatter_str = yaml.dump(
        frontmatter, default_flow_style=False, sort_keys=False
    ).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    (dest_dir / filename).write_text(content)
    return True


def _get_content_path(local_module_path: Path) -> Path:
    """Get the content path for a local module (handles module/ subdirectory).

    If the module has a module/ subdirectory, returns that path.
    Otherwise, returns the root module path.
    """
    module_subdir = local_module_path / "module"
    if module_subdir.exists() and module_subdir.is_dir():
        return module_subdir
    return local_module_path


def _skill_source_dir(local_module_path: Path, skill_name: str) -> Path:
    """Find the source directory for a skill.

    Handles both module/ subdirectory structure and legacy root structure.
    """
    content_path = _get_content_path(local_module_path)
    preferred = content_path / "skills" / skill_name
    if preferred.exists():
        return preferred
    # Fallback for legacy structure
    return local_module_path / skill_name


def _merge_mcps_into_file(
    dest_path: Path,
    module_name: str,
    mcps: dict[str, dict[str, Any]],
) -> bool:
    """Merge MCP servers into a config file.

    Args:
        dest_path: Path to config file
        module_name: Module name for prefixing servers
        mcps: Dict of server_name -> server_config
    """
    # Read existing config
    if dest_path.exists():
        try:
            existing_config = json.loads(dest_path.read_text())
        except json.JSONDecodeError:
            existing_config = {}
    else:
        existing_config = {}

    # Ensure mcpServers exists
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}

    # Add prefixed servers
    for name, server_config in mcps.items():
        prefixed_name = f"{module_name}-{name}"
        existing_config["mcpServers"][prefixed_name] = server_config

    # Write back
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(existing_config, indent=2) + "\n")
    return True


def _remove_mcps_from_file(
    dest_path: Path,
    module_name: str,
) -> bool:
    """Remove a module's MCP servers from a config file."""
    if not dest_path.exists():
        return True

    try:
        existing_config = json.loads(dest_path.read_text())
    except json.JSONDecodeError:
        return True

    if "mcpServers" not in existing_config:
        return True

    # Remove servers with module prefix
    prefix = f"{module_name}-"
    existing_config["mcpServers"] = {
        k: v
        for k, v in existing_config["mcpServers"].items()
        if not k.startswith(prefix)
    }

    # Write back (or delete if mcpServers is empty and no other keys)
    if not existing_config["mcpServers"] and len(existing_config) == 1:
        dest_path.unlink()
    else:
        dest_path.write_text(json.dumps(existing_config, indent=2) + "\n")
    return True
