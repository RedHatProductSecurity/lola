"""Claude Code target implementation."""

from __future__ import annotations

import shutil
from pathlib import Path

import lola.config as config
from lola.models import Module
from .base import (
    BaseAssistantTarget,
    ManagedInstructionsTarget,
    MCPSupportMixin,
    PluginLayout,
    PluginManifest,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
    _transform_claude_agent_frontmatter,
    unlink_symlink_if_present,
)


class ClaudeCodeTarget(MCPSupportMixin, ManagedInstructionsTarget, BaseAssistantTarget):
    """Target for Claude Code assistant."""

    name = "claude-code"
    supports_agents = True
    INSTRUCTIONS_FILE = "CLAUDE.md"

    def get_plugin_layout(
        self,
        scope: str = "project",
    ) -> PluginLayout | None:
        template = (
            "~/.claude/skills/{name}" if scope == "user" else ".claude/skills/{name}"
        )
        return PluginLayout(
            plugin_root_template=template,
            manifest_path=".claude-plugin",
            mcp_path=".mcp.json",
        )

    def build_plugin_manifest(self, module: Module) -> PluginManifest:
        existing = PluginManifest.from_file(module.content_path / "plugin.json")
        if existing is not None:
            return existing
        return PluginManifest(name=module.name)

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".claude" / "skills"

    def get_command_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".claude" / "commands"

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".claude" / "agents"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".claude" / self.INSTRUCTIONS_FILE
        return Path(project_path) / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".mcp.json"

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
        # Replace a pre-existing symlink (e.g. a user's manual ln -s into a
        # separate checkout) with a real directory instead of writing through
        # it or failing to create a directory over a file symlink.
        unlink_symlink_if_present(skill_dest)
        skill_dest.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_file = source_path / config.SKILL_FILE
        if skill_file.exists():
            skill_file_dest = skill_dest / "SKILL.md"
            # Write must not follow a symlink that shadows the skill file
            # (written before by a manual ln -s or a previous target): the
            # link points at an external file Lola should not overwrite.
            unlink_symlink_if_present(skill_file_dest)
            skill_file_dest.write_text(skill_file.read_text())

        # Copy supporting files
        for item in source_path.iterdir():
            if item.name == "SKILL.md":
                continue
            dest_item = skill_dest / item.name
            if item.is_dir():
                if dest_item.is_symlink():
                    dest_item.unlink()
                elif dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                # Regular file: copy2 follows a pre-existing symlink and
                # rewrites its target, so unlink the link first.
                unlink_symlink_if_present(dest_item)
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
        agent_full_name = filename.removesuffix(".md")
        return _generate_agent_with_frontmatter(
            source_path,
            dest_dir,
            filename,
            {"name": agent_full_name, "model": "inherit"},
            frontmatter_transforms=_transform_claude_agent_frontmatter,
        )
