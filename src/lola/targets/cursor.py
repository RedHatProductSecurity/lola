"""
Cursor target implementation for lola.

Cursor uses .mdc rule files with alwaysApply: true for instructions,
avoiding inconsistent AGENTS.md loading behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

import lola.config as config
import lola.frontmatter as fm
from .base import MCPSupportMixin, BaseAssistantTarget, _generate_passthrough_command


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
