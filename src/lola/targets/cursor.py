"""
Cursor target implementation for lola.

Cursor 2.4+ supports:
- Skills in .cursor/skills/<skill-name>/SKILL.md (Agent Skills standard)
- Subagents in .cursor/agents/<name>.md
- Rules in .cursor/rules/*.mdc for always-on instructions
"""

from __future__ import annotations

import shutil
from pathlib import Path

import lola.config as config
from .base import (
    MCPSupportMixin,
    BaseAssistantTarget,
    _generate_passthrough_command,
    _generate_agent_with_frontmatter,
)


class CursorTarget(MCPSupportMixin, BaseAssistantTarget):
    """Target for Cursor assistant."""

    name = "cursor"
    supports_agents = True

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "skills"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "commands"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "agents"

    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "rules"

    def get_mcp_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "mcp.json"

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Copy skill directory with SKILL.md and supporting files.

        Cursor 2.4+ uses the Agent Skills standard with SKILL.md files.
        """
        if not source_path.exists():
            return False

        skill_dest = dest_path / skill_name
        skill_dest.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

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
        """Generate agent file with Cursor-compatible frontmatter.

        Cursor subagents use:
        - name: unique identifier (defaults to filename)
        - description: when to use this agent
        - model: "fast", "inherit", or specific model ID
        """
        filename = self.get_agent_filename(module_name, agent_name)
        agent_full_name = filename.removesuffix(".md")
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"name": agent_full_name, "model": "inherit"},
        )

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

    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        """Remove the module's instructions .mdc file."""
        mdc_file = dest_path / f"{module_name}-instructions.mdc"
        if mdc_file.exists():
            mdc_file.unlink()
            return True
        return False
