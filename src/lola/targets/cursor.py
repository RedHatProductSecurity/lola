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
from typing import Any

import lola.config as config
from lola.models import Module
from .base import (
    MCPSupportMixin,
    BaseAssistantTarget,
    PluginLayout,
    PluginManifest,
    _convert_env_var_to_cursor_vscode,
    _generate_passthrough_command,
    _generate_agent_with_frontmatter,
    _merge_mcps_into_file,
    _transform_claude_agent_frontmatter,
    _transform_mcp_env_vars,
    unlink_symlink_if_present,
)


class CursorTarget(MCPSupportMixin, BaseAssistantTarget):
    """Target for Cursor assistant."""

    name = "cursor"
    supports_agents = True

    def get_plugin_layout(
        self,
        scope: str = "project",
    ) -> PluginLayout | None:
        if scope == "project":
            return None
        # Uses the Agent Plugin (global spec) format with plugin.json at root,
        # not Cursor's own format (.cursor-plugin/plugin.json).
        return PluginLayout(
            plugin_root_template="~/.cursor/plugins/local/{name}",
            manifest_path=None,
            mcp_path="mcp.json",
        )

    def build_plugin_manifest(self, module: Module) -> PluginManifest:
        existing = PluginManifest.from_file(module.content_path / "plugin.json")
        if existing is not None:
            return existing
        return PluginManifest(name=module.name)

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".cursor" / "skills"

    def get_command_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".cursor" / "commands"

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".cursor" / "agents"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".cursor" / "rules"

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path:
        base = Path.home() if scope == "user" else Path(project_path)
        return base / ".cursor" / "mcp.json"

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Merge MCP servers, converting env var refs to Cursor's ${env:VAR} syntax."""
        if not mcps:
            return False
        transformed = {
            name: _transform_mcp_env_vars(cfg, _convert_env_var_to_cursor_vscode)
            for name, cfg in mcps.items()
        }
        return _merge_mcps_into_file(dest_path, module_name, transformed)

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

        # Validate the source before replacing any existing destination link.
        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

        skill_dest = dest_path / skill_name
        # Never mkdir or write through a pre-existing symlink; unlink first so
        # a manual ln -s into an external checkout is replaced with a real dir.
        unlink_symlink_if_present(skill_dest)
        skill_dest.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        skill_file_dest = skill_dest / "SKILL.md"
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
                # copy2 follows a pre-existing symlink; unlink first.
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
            frontmatter_transforms=_transform_claude_agent_frontmatter,
        )

    def generate_instructions(
        self,
        source: Path | str | list[str],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate .mdc file with alwaysApply: true for module instructions."""
        from .base import _resolve_source_content

        content = _resolve_source_content(source)
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
