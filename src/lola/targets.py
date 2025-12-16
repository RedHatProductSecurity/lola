"""
targets:
    Target assistants + installation logic for lola.

This module provides:
- AssistantTarget protocol defining the interface for assistant targets
- Concrete implementations for each supported assistant
- TARGETS registry for looking up targets by name
- Installation orchestration (install_to_assistant, copy_module_to_local)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Optional, Protocol

import yaml
from rich.console import Console

import lola.config as config
import lola.frontmatter as fm
from lola.exceptions import ConfigurationError, UnknownAssistantError
from lola.models import Installation, InstallationRegistry, Module

console = Console()


# =============================================================================
# AssistantTarget Protocol
# =============================================================================


class AssistantTarget(Protocol):
    """Protocol defining the interface for assistant targets."""

    name: str
    supports_agents: bool
    uses_managed_section: bool  # True if skills go into a managed section (e.g., GEMINI.md)

    def get_skill_path(self, project_path: str) -> Path:
        """Get the skill output path for this assistant."""
        ...

    def get_command_path(self, project_path: str) -> Path:
        """Get the command output path for this assistant."""
        ...

    def get_agent_path(self, project_path: str) -> Path | None:
        """Get the agent output path. Returns None if agents not supported."""
        ...

    def get_instructions_path(self, project_path: str) -> Path:
        """Get the instructions file path for this assistant."""
        ...

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,
    ) -> bool:
        """Generate skill file(s) for this assistant."""
        ...

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Generate command file for this assistant."""
        ...

    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Generate agent file for this assistant."""
        ...

    def generate_instructions(
        self,
        source_path: Path,
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in the assistant's instruction file."""
        ...

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove skill file(s) for this assistant."""
        ...

    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's instructions from the instruction file."""
        ...

    def generate_skills_batch(
        self,
        dest_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],
        project_path: str | None,
    ) -> bool:
        """Generate skills as a batch (for managed section targets)."""
        ...

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        """Get the filename for a command."""
        ...

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Get the filename for an agent."""
        ...

    def get_mcp_path(self, project_path: str) -> Path | None:
        """Get the MCP config file path for this assistant. Returns None if not supported."""
        ...

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/merge MCP servers into the config file."""
        ...

    def remove_mcps(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's MCP servers from the config file."""
        ...


# =============================================================================
# BaseAssistantTarget - shared defaults
# =============================================================================


class BaseAssistantTarget:
    """Base class with shared default implementations."""

    name: str = ""
    supports_agents: bool = True
    uses_managed_section: bool = False

    def get_agent_path(self, project_path: str) -> Path | None:  # noqa: ARG002
        """Default: no agent support. Override in subclasses."""
        return None

    def get_instructions_path(self, project_path: str) -> Path:  # noqa: ARG002
        """Default: no instructions path. Override in subclasses."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement get_instructions_path()")

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
        """Default: module-cmd.md"""
        return f"{module_name}-{cmd_name}.md"

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Default: module-agent.md"""
        return f"{module_name}-{agent_name}.md"

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
            skills_block += f"**Instructions:** Read `{skill_md_path}` for detailed guidance.\n\n"

        # Update or create managed section
        if self.START_MARKER in content and self.END_MARKER in content:
            start_idx = content.index(self.START_MARKER)
            end_idx = content.index(self.END_MARKER) + len(self.END_MARKER)
            existing_section = content[start_idx:end_idx]
            section_content = existing_section[len(self.START_MARKER) : -len(self.END_MARKER)]

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

            new_section = self.START_MARKER + "\n".join(new_lines) + skills_block + self.END_MARKER
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
        section_content = existing_section[len(self.START_MARKER) : -len(self.END_MARKER)]

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
                len(self.INSTRUCTIONS_START_MARKER) : -len(
                    self.INSTRUCTIONS_END_MARKER
                )
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
        import re

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

        new_section = (
            self.INSTRUCTIONS_START_MARKER
            + section_content
            + self.INSTRUCTIONS_END_MARKER
        )
        content = content[:start_idx] + new_section + content[end_idx:]
        dest_path.write_text(content)
        return True


# =============================================================================
# Private helpers
# =============================================================================


def _rewrite_relative_paths(content: str, assets_path: str) -> str:
    """Rewrite relative paths in content to point to the assets location."""
    patterns = [
        (r'(\s|^|"|\x27|\(|`)(\.\./[^\s"\x27)\]`]+)', r"\1" + assets_path + r"/\2"),
        (r'(\s|^|"|\x27|\(|`)(\./([^\s"\x27)\]`]+))', r"\1" + assets_path + r"/\3"),
    ]
    result = content
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    result = re.sub(r"(?<!:)//+", "/", result)
    return result


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

    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    (dest_dir / filename).write_text(content)
    return True


def _convert_to_gemini_args(content: str) -> str:
    """Convert argument placeholders for Gemini CLI format."""
    result = content.replace("$ARGUMENTS", "{{args}}")
    if fm.has_positional_args(result):
        result = f"Arguments: {{{{args}}}}\n\n{result}"
    return result


def _skill_source_dir(local_module_path: Path, skill_name: str) -> Path:
    """Find the source directory for a skill."""
    preferred = local_module_path / "skills" / skill_name
    if preferred.exists():
        return preferred
    return local_module_path / skill_name


# =============================================================================
# MCP helpers
# =============================================================================


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
# Concrete Target Implementations
# =============================================================================


class ClaudeCodeTarget(MCPSupportMixin, ManagedInstructionsTarget, BaseAssistantTarget):
    """Target for Claude Code assistant."""

    name = "claude-code"
    supports_agents = True
    INSTRUCTIONS_FILE = "CLAUDE.md"

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "skills"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "commands"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "agents"

    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str) -> Path:
        return Path(project_path) / ".mcp.json"

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Copy skill directory with SKILL.md and supporting files."""
        if not source_path.exists():
            return False

        skill_dest = dest_path / skill_name
        skill_dest.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_file = source_path / config.SKILL_FILE
        if skill_file.exists():
            (skill_dest / "SKILL.md").write_text(skill_file.read_text())

        # Copy supporting files
        for item in source_path.iterdir():
            if item.name == "SKILL.md":
                continue
            dest_item = skill_dest / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)
        return True

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_command_filename(module_name, cmd_name)
        return _generate_passthrough_command(source_path, dest_dir, filename)

    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_agent_filename(module_name, agent_name)
        # Claude Code requires 'name' field in agent frontmatter
        agent_full_name = filename.removesuffix(".md")
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"name": agent_full_name, "model": "inherit"},
        )


class CursorTarget(MCPSupportMixin, BaseAssistantTarget):
    """Target for Cursor assistant.

    Cursor uses .mdc rule files with alwaysApply: true for instructions,
    avoiding inconsistent AGENTS.md loading behavior.
    """

    name = "cursor"
    supports_agents = False

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "rules"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "commands"

    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "rules"

    def get_mcp_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "mcp.json"

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,
    ) -> bool:
        """Convert skill to Cursor MDC format."""
        if not source_path.exists():
            return False

        dest_path.mkdir(parents=True, exist_ok=True)

        # Calculate assets path for relative path rewriting
        if project_path:
            try:
                relative_source = source_path.relative_to(Path(project_path))
                assets_path = str(relative_source)
            except ValueError:
                assets_path = str(source_path)
        else:
            assets_path = str(source_path)

        # Convert SKILL.md to MDC format
        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

        content = skill_file.read_text()
        frontmatter, body = fm.parse(content)

        if assets_path:
            body = _rewrite_relative_paths(body, assets_path)

        mdc_lines = ["---"]
        mdc_lines.append(f"description: {frontmatter.get('description', '')}")
        mdc_lines.append("globs:")
        mdc_lines.append("alwaysApply: false")
        mdc_lines.append("---")
        mdc_lines.append("")
        mdc_lines.append(body)

        (dest_path / f"{skill_name}.mdc").write_text("\n".join(mdc_lines))
        return True

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_command_filename(module_name, cmd_name)
        return _generate_passthrough_command(source_path, dest_dir, filename)

    def generate_instructions(
        self,
        source_path: Path,
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate .mdc file with alwaysApply: true for module instructions."""
        if not source_path.exists():
            return False

        content = source_path.read_text().strip()
        if not content:
            return False

        dest_path.mkdir(parents=True, exist_ok=True)

        mdc_lines = [
            "---",
            f"description: {module_name} module instructions",
            "globs:",
            "alwaysApply: true",
            "---",
            "",
            content,
        ]

        mdc_file = dest_path / f"{module_name}-instructions.mdc"
        mdc_file.write_text("\n".join(mdc_lines))
        return True

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove .mdc file instead of directory."""
        mdc_file = dest_path / f"{skill_name}.mdc"
        if mdc_file.exists():
            mdc_file.unlink()
            return True
        return False

    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove the module's instructions .mdc file."""
        mdc_file = dest_path / f"{module_name}-instructions.mdc"
        if mdc_file.exists():
            mdc_file.unlink()
            return True
        return False


class GeminiTarget(MCPSupportMixin, ManagedInstructionsTarget, ManagedSectionTarget):
    """Target for Gemini CLI assistant."""

    name = "gemini-cli"
    supports_agents = False
    MANAGED_FILE = "GEMINI.md"
    INSTRUCTIONS_FILE = "GEMINI.md"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".gemini" / "commands"

    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str) -> Path:
        return Path(project_path) / ".gemini" / "settings.json"

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Convert command to Gemini TOML format."""
        if not source_path.exists():
            return False
        dest_dir.mkdir(parents=True, exist_ok=True)

        content = source_path.read_text()
        frontmatter, body = fm.parse(content)
        description = frontmatter.get("description", "")
        prompt = _convert_to_gemini_args(body)

        description_escaped = description.replace("\\", "\\\\").replace('"', '\\"')
        # Escape """ sequences in prompt to avoid breaking TOML multi-line strings
        prompt_escaped = prompt.rstrip().replace('"""', r'\"""')
        toml_lines = [
            f'description = "{description_escaped}"',
            'prompt = """',
            prompt_escaped,
            '"""',
        ]

        filename = self.get_command_filename(module_name, cmd_name)
        (dest_dir / filename).write_text("\n".join(toml_lines))
        return True

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        return f"{module_name}-{cmd_name}.toml"


class OpenCodeTarget(MCPSupportMixin, ManagedInstructionsTarget, ManagedSectionTarget):
    """Target for OpenCode assistant.

    OpenCode uses AGENTS.md for both skills and instructions (similar to Gemini's GEMINI.md approach).
    """

    name = "opencode"
    supports_agents = True
    MANAGED_FILE = "AGENTS.md"
    INSTRUCTIONS_FILE = "AGENTS.md"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".opencode" / "command"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".opencode" / "agent"

    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str) -> Path:
        return Path(project_path) / ".opencode" / "mcp.json"

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_command_filename(module_name, cmd_name)
        return _generate_passthrough_command(source_path, dest_dir, filename)

    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_agent_filename(module_name, agent_name)
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"mode": "subagent"},
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


# =============================================================================
# Registry
# =============================================================================


def get_registry() -> InstallationRegistry:
    return InstallationRegistry(config.INSTALLED_FILE)


# =============================================================================
# Install helpers
# =============================================================================


def copy_module_to_local(module: Module, local_modules_path: Path) -> Path:
    """Copy module to local .lola/modules directory."""
    dest = local_modules_path / module.name
    if dest.resolve() == module.path.resolve():
        return dest

    local_modules_path.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    shutil.copytree(module.path, dest)
    return dest


def _install_skills(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install skills for a target. Returns (installed, failed) lists."""
    if not module.skills:
        return [], []

    installed: list[str] = []
    failed: list[str] = []
    skill_dest = target.get_skill_path(project_path) if project_path else None

    if not skill_dest:
        return [], []

    # Batch updates for managed section targets (Gemini, OpenCode)
    if target.uses_managed_section:
        batch_skills: list[tuple[str, str, Path]] = []
        for skill in module.skills:
            source = _skill_source_dir(local_module_path, skill)
            prefixed = f"{module.name}-{skill}"
            if source.exists():
                batch_skills.append((skill, _get_skill_description(source), source))
                installed.append(prefixed)
            else:
                failed.append(skill)
        if batch_skills:
            target.generate_skills_batch(skill_dest, module.name, batch_skills, project_path)
    else:
        for skill in module.skills:
            source = _skill_source_dir(local_module_path, skill)
            prefixed = f"{module.name}-{skill}"
            if target.generate_skill(source, skill_dest, prefixed, project_path):
                installed.append(prefixed)
            else:
                failed.append(skill)

    return installed, failed


def _install_commands(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install commands for a target. Returns (installed, failed) lists."""
    if not module.commands:
        return [], []

    installed: list[str] = []
    failed: list[str] = []
    command_dest = target.get_command_path(project_path) if project_path else None

    if not command_dest:
        return [], []

    commands_dir = local_module_path / "commands"
    for cmd in module.commands:
        source = commands_dir / f"{cmd}.md"
        if target.generate_command(source, command_dest, cmd, module.name):
            installed.append(cmd)
        else:
            failed.append(cmd)

    return installed, failed


def _install_agents(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install agents for a target. Returns (installed, failed) lists."""
    if not module.agents or not target.supports_agents:
        return [], []

    agent_dest = target.get_agent_path(project_path) if project_path else None
    if not agent_dest:
        return [], []

    installed: list[str] = []
    failed: list[str] = []

    agents_dir = local_module_path / "agents"
    for agent in module.agents:
        source = agents_dir / f"{agent}.md"
        if target.generate_agent(source, agent_dest, agent, module.name):
            installed.append(agent)
        else:
            failed.append(agent)

    return installed, failed


def _install_instructions(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> bool:
    """Install module instructions for a target. Returns True if installed."""
    from lola.models import INSTRUCTIONS_FILE

    if not module.has_instructions or not project_path:
        return False

    instructions_source = local_module_path / INSTRUCTIONS_FILE
    if not instructions_source.exists():
        return False

    instructions_dest = target.get_instructions_path(project_path)
    return target.generate_instructions(instructions_source, instructions_dest, module.name)


def _install_mcps(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install MCPs for a target. Returns (installed, failed) lists."""
    if not module.mcps or not project_path:
        return [], []

    mcp_dest = target.get_mcp_path(project_path)
    if not mcp_dest:
        return [], []

    # Load mcps.json from local module
    mcps_file = local_module_path / config.MCPS_FILE
    if not mcps_file.exists():
        return [], list(module.mcps)

    try:
        mcps_data = json.loads(mcps_file.read_text())
        servers = mcps_data.get("mcpServers", {})
    except json.JSONDecodeError:
        return [], list(module.mcps)

    # Generate MCPs
    if target.generate_mcps(servers, mcp_dest, module.name):
        installed = [f"{module.name}-{name}" for name in servers.keys()]
        return installed, []

    return [], list(module.mcps)


def _print_summary(
    assistant: str,
    installed_skills: list[str],
    installed_commands: list[str],
    installed_agents: list[str],
    installed_mcps: list[str],
    has_instructions: bool,
    failed_skills: list[str],
    failed_commands: list[str],
    failed_agents: list[str],
    failed_mcps: list[str],
    module_name: str,
    verbose: bool,
) -> None:
    """Print installation summary."""
    if not (installed_skills or installed_commands or installed_agents or installed_mcps or has_instructions):
        return

    parts: list[str] = []
    if installed_skills:
        parts.append(f"{len(installed_skills)} skill{'s' if len(installed_skills) != 1 else ''}")
    if installed_commands:
        parts.append(f"{len(installed_commands)} command{'s' if len(installed_commands) != 1 else ''}")
    if installed_agents:
        parts.append(f"{len(installed_agents)} agent{'s' if len(installed_agents) != 1 else ''}")
    if installed_mcps:
        parts.append(f"{len(installed_mcps)} MCP{'s' if len(installed_mcps) != 1 else ''}")
    if has_instructions:
        parts.append("instructions")

    console.print(f"  [green]{assistant}[/green] [dim]({', '.join(parts)})[/dim]")

    if verbose:
        for skill in installed_skills:
            console.print(f"    [green]{skill}[/green]")
        for cmd in installed_commands:
            console.print(f"    [green]/{module_name}-{cmd}[/green]")
        for agent in installed_agents:
            console.print(f"    [green]@{module_name}-{agent}[/green]")
        for mcp in installed_mcps:
            console.print(f"    [green]mcp:{mcp}[/green]")
        if has_instructions:
            console.print("    [green]instructions[/green]")

    if failed_skills or failed_commands or failed_agents or failed_mcps:
        for skill in failed_skills:
            console.print(f"    [red]{skill}[/red] [dim](source not found)[/dim]")
        for cmd in failed_commands:
            console.print(f"    [red]{cmd}[/red] [dim](source not found)[/dim]")
        for agent in failed_agents:
            console.print(f"    [red]{agent}[/red] [dim](source not found)[/dim]")
        for mcp in failed_mcps:
            console.print(f"    [red]{mcp}[/red] [dim](source not found)[/dim]")


def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
    verbose: bool = False,
) -> int:
    """Install module to a specific assistant."""
    target = get_target(assistant)

    if scope != "project":
        raise ConfigurationError("Only project scope is supported")

    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills, failed_skills = _install_skills(target, module, local_module_path, project_path)
    installed_commands, failed_commands = _install_commands(target, module, local_module_path, project_path)
    installed_agents, failed_agents = _install_agents(target, module, local_module_path, project_path)
    installed_mcps, failed_mcps = _install_mcps(target, module, local_module_path, project_path)
    instructions_installed = _install_instructions(target, module, local_module_path, project_path)

    _print_summary(
        assistant,
        installed_skills,
        installed_commands,
        installed_agents,
        installed_mcps,
        instructions_installed,
        failed_skills,
        failed_commands,
        failed_agents,
        failed_mcps,
        module.name,
        verbose,
    )

    if installed_skills or installed_commands or installed_agents or installed_mcps or instructions_installed:
        registry.add(
            Installation(
                module_name=module.name,
                assistant=assistant,
                scope=scope,
                project_path=project_path,
                skills=installed_skills,
                commands=installed_commands,
                agents=installed_agents,
                mcps=installed_mcps,
                has_instructions=instructions_installed,
            )
        )

    return len(installed_skills) + len(installed_commands) + len(installed_agents) + len(installed_mcps) + (1 if instructions_installed else 0)
