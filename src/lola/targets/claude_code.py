"""Claude Code target implementation."""

from __future__ import annotations

import shutil
from pathlib import Path

import lola.config as config
from .base import (
    BaseAssistantTarget,
    ManagedInstructionsTarget,
    MCPSupportMixin,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
)


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
