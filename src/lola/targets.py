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

import re
import shutil
from pathlib import Path
from typing import Optional, Protocol

import yaml
from rich.console import Console

import lola.config as config
import lola.frontmatter as fm
from lola.models import Installation, InstallationRegistry, Module

console = Console()


# =============================================================================
# AssistantTarget Protocol
# =============================================================================


class AssistantTarget(Protocol):
    """Protocol defining the interface for assistant targets."""

    name: str
    supports_agents: bool

    def get_skill_path(self, project_path: str) -> Path:
        """Get the skill output path for this assistant."""
        ...

    def get_command_path(self, project_path: str) -> Path:
        """Get the command output path for this assistant."""
        ...

    def get_agent_path(self, project_path: str) -> Path | None:
        """Get the agent output path. Returns None if agents not supported."""
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

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove skill file(s) for this assistant."""
        ...

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        """Get the filename for a command."""
        ...

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Get the filename for an agent."""
        ...


# =============================================================================
# BaseAssistantTarget - shared defaults
# =============================================================================


class BaseAssistantTarget:
    """Base class with shared default implementations."""

    name: str = ""
    supports_agents: bool = True

    def get_agent_path(self, project_path: str) -> Path | None:  # noqa: ARG002
        """Default: no agent support. Override in subclasses."""
        return None

    def generate_agent(
        self,
        source_path: Path,  # noqa: ARG002
        dest_dir: Path,  # noqa: ARG002
        agent_name: str,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        """Default: agents not supported."""
        return False

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Default: remove skill directory."""
        skill_dir = dest_path / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            return True
        return False

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        """Default: module-cmd.md"""
        return f"{module_name}-{cmd_name}.md"

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:
        """Default: module-agent.md"""
        return f"{module_name}-{agent_name}.md"


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
# Concrete Target Implementations
# =============================================================================


class ClaudeCodeTarget(BaseAssistantTarget):
    """Target for Claude Code assistant."""

    name = "claude-code"
    supports_agents = True

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "skills"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "commands"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".claude" / "agents"

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
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"model": "inherit"},
        )


class CursorTarget(BaseAssistantTarget):
    """Target for Cursor assistant."""

    name = "cursor"
    supports_agents = False

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "rules"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "commands"

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

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove .mdc file instead of directory."""
        mdc_file = dest_path / f"{skill_name}.mdc"
        if mdc_file.exists():
            mdc_file.unlink()
            return True
        return False


class GeminiTarget(BaseAssistantTarget):
    """Target for Gemini CLI assistant."""

    name = "gemini-cli"
    supports_agents = False

    # Markers for managed section in GEMINI.md
    START_MARKER = "<!-- lola:skills:start -->"
    END_MARKER = "<!-- lola:skills:end -->"
    HEADER = """## Lola Skills

These skills are installed by Lola and provide specialized capabilities.
When a task matches a skill's description, read the skill's SKILL.md file
to learn the detailed instructions and workflows.

**How to use skills:**
1. Check if your task matches any skill description below
2. Use `read_file` to read the skill's SKILL.md for detailed instructions
3. Follow the instructions in the SKILL.md file

"""

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / "GEMINI.md"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".gemini" / "commands"

    def get_agent_path(self, project_path: str) -> None:
        return None

    def generate_skill(
        self,
        source_path: Path,  # noqa: ARG002
        dest_path: Path,  # noqa: ARG002
        skill_name: str,  # noqa: ARG002
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Gemini uses batch skill generation - this should not be called directly."""
        raise NotImplementedError(
            "GeminiTarget.generate_skill should not be called directly. "
            "Use generate_skills_batch() instead."
        )

    def generate_skills_batch(
        self,
        gemini_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],  # (name, description, source_path)
        project_path: str | None,
    ) -> bool:
        """Update GEMINI.md with skill listings for a module."""
        if gemini_file.exists():
            content = gemini_file.read_text()
        else:
            gemini_file.parent.mkdir(parents=True, exist_ok=True)
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

        gemini_file.write_text(content)
        return True

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
        toml_lines = [
            f'description = "{description_escaped}"',
            'prompt = """',
            prompt.rstrip(),
            '"""',
        ]

        filename = self.get_command_filename(module_name, cmd_name)
        (dest_dir / filename).write_text("\n".join(toml_lines))
        return True

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:
        return f"{module_name}-{cmd_name}.toml"

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove a module's skills from GEMINI.md.

        Note: For Gemini, dest_path is the GEMINI.md file and skill_name
        is the module name (skills are grouped by module in GEMINI.md).
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

        # Remove module section (skill_name is actually module_name for Gemini)
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


class OpenCodeTarget(BaseAssistantTarget):
    """Target for OpenCode assistant.

    OpenCode uses AGENTS.md for skills (similar to Gemini's GEMINI.md approach).
    """

    name = "opencode"
    supports_agents = True

    # Markers for managed section in AGENTS.md
    START_MARKER = "<!-- lola:skills:start -->"
    END_MARKER = "<!-- lola:skills:end -->"
    HEADER = """## Lola Skills

These skills are installed by Lola and provide specialized capabilities.
When a task matches a skill's description, read the skill's SKILL.md file
to learn the detailed instructions and workflows.

**How to use skills:**
1. Check if your task matches any skill description below
2. Use `read_file` to read the skill's SKILL.md for detailed instructions
3. Follow the instructions in the SKILL.md file

"""

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / "AGENTS.md"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".opencode" / "commands"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".opencode" / "agent"

    def generate_skill(
        self,
        source_path: Path,  # noqa: ARG002
        dest_path: Path,  # noqa: ARG002
        skill_name: str,  # noqa: ARG002
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """OpenCode uses batch skill generation - this should not be called directly."""
        raise NotImplementedError(
            "OpenCodeTarget.generate_skill should not be called directly. "
            "Use generate_skills_batch() instead."
        )

    def generate_skills_batch(
        self,
        agents_file: Path,
        module_name: str,
        skills: list[tuple[str, str, Path]],  # (name, description, source_path)
        project_path: str | None,
    ) -> bool:
        """Update AGENTS.md with skill listings for a module."""
        if agents_file.exists():
            content = agents_file.read_text()
        else:
            agents_file.parent.mkdir(parents=True, exist_ok=True)
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

        agents_file.write_text(content)
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
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"mode": "subagent"},
        )

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove a module's skills from AGENTS.md.

        Note: For OpenCode, dest_path is the AGENTS.md file and skill_name
        is the module name (skills are grouped by module in AGENTS.md).
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

        # Remove module section (skill_name is actually module_name for OpenCode)
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
# Target Registry
# =============================================================================

TARGETS: dict[str, AssistantTarget] = {
    "claude-code": ClaudeCodeTarget(),
    "cursor": CursorTarget(),
    "gemini-cli": GeminiTarget(),
    "opencode": OpenCodeTarget(),
}


def get_target(assistant: str) -> AssistantTarget:
    """Get a target by name. Raises ValueError if not found."""
    if assistant not in TARGETS:
        raise ValueError(f"Unknown assistant: {assistant}. Supported: {list(TARGETS.keys())}")
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

    # Special handling for Gemini and OpenCode batch updates
    if isinstance(target, (GeminiTarget, OpenCodeTarget)):
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


def _print_summary(
    assistant: str,
    installed_skills: list[str],
    installed_commands: list[str],
    installed_agents: list[str],
    failed_skills: list[str],
    failed_commands: list[str],
    failed_agents: list[str],
    module_name: str,
    verbose: bool,
) -> None:
    """Print installation summary."""
    if not (installed_skills or installed_commands or installed_agents):
        return

    parts: list[str] = []
    if installed_skills:
        parts.append(f"{len(installed_skills)} skill{'s' if len(installed_skills) != 1 else ''}")
    if installed_commands:
        parts.append(f"{len(installed_commands)} command{'s' if len(installed_commands) != 1 else ''}")
    if installed_agents:
        parts.append(f"{len(installed_agents)} agent{'s' if len(installed_agents) != 1 else ''}")

    console.print(f"  [green]{assistant}[/green] [dim]({', '.join(parts)})[/dim]")

    if verbose:
        for skill in installed_skills:
            console.print(f"    [green]{skill}[/green]")
        for cmd in installed_commands:
            console.print(f"    [green]/{module_name}-{cmd}[/green]")
        for agent in installed_agents:
            console.print(f"    [green]@{module_name}-{agent}[/green]")

    if failed_skills or failed_commands or failed_agents:
        for skill in failed_skills:
            console.print(f"    [red]{skill}[/red] [dim](source not found)[/dim]")
        for cmd in failed_commands:
            console.print(f"    [red]{cmd}[/red] [dim](source not found)[/dim]")
        for agent in failed_agents:
            console.print(f"    [red]{agent}[/red] [dim](source not found)[/dim]")


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
        raise ValueError("Only project scope is supported")

    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills, failed_skills = _install_skills(target, module, local_module_path, project_path)
    installed_commands, failed_commands = _install_commands(target, module, local_module_path, project_path)
    installed_agents, failed_agents = _install_agents(target, module, local_module_path, project_path)

    _print_summary(
        assistant,
        installed_skills,
        installed_commands,
        installed_agents,
        failed_skills,
        failed_commands,
        failed_agents,
        module.name,
        verbose,
    )

    if installed_skills or installed_commands or installed_agents:
        registry.add(
            Installation(
                module_name=module.name,
                assistant=assistant,
                scope=scope,
                project_path=project_path,
                skills=installed_skills,
                commands=installed_commands,
                agents=installed_agents,
            )
        )

    return len(installed_skills) + len(installed_commands) + len(installed_agents)
