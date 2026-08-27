"""OpenClaw target implementation."""

from __future__ import annotations

import shutil
from pathlib import Path

import lola.config as config
from .base import BaseAssistantTarget, unlink_symlink_if_present


class OpenClawTarget(BaseAssistantTarget):
    """Target for OpenClaw assistant.

    Skills are installed to <workspace>/skills/<name>/SKILL.md, which is
    OpenClaw's highest-priority auto-discovery path. No CLI command is needed
    after install — OpenClaw picks up new skills on the next session start.

    Commands, agents, and MCP are not supported in this version.
    Plugin-based support (commands, agents) is tracked separately.
    """

    name = "openclaw"
    supports_agents = False

    @staticmethod
    def resolve_workspace(workspace: str | None) -> Path:
        """Resolve a workspace argument to an absolute Path.

        - None        → ~/.openclaw/workspace  (default)
        - path        → expanded and resolved (contains / or \\, e.g. ./foo, ~/foo)
        - name        → ~/.openclaw/workspace-{name}  (e.g. foo → workspace-foo)
        """
        if workspace is None:
            return Path.home() / ".openclaw" / "workspace"
        if "/" in workspace or "\\" in workspace:
            return Path(workspace).expanduser().absolute()
        return Path.home() / ".openclaw" / f"workspace-{workspace}"

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return self.resolve_workspace(None) / "skills"
        return Path(project_path) / "skills"

    def get_command_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return self.resolve_workspace(None) / "commands"
        return Path(project_path) / ".openclaw" / "commands"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return self.resolve_workspace(None) / "instructions.md"
        return Path(project_path) / ".openclaw" / "instructions.md"

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
        # Never mkdir or write through a pre-existing symlink; unlink first so
        # a manual ln -s into an external checkout is replaced with a real dir.
        unlink_symlink_if_present(skill_dest)
        skill_dest.mkdir(parents=True, exist_ok=True)

        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

        skill_file_dest = skill_dest / "SKILL.md"
        unlink_symlink_if_present(skill_file_dest)
        skill_file_dest.write_text(skill_file.read_text())

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
        source_path: Path,  # noqa: ARG002
        dest_dir: Path,  # noqa: ARG002
        cmd_name: str,  # noqa: ARG002
        module_name: str,  # noqa: ARG002
    ) -> bool:
        return False
