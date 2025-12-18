"""Gemini CLI target implementation."""

from __future__ import annotations

from pathlib import Path

import lola.frontmatter as fm
from .base import (
    ManagedInstructionsTarget,
    ManagedSectionTarget,
    MCPSupportMixin,
)


def _convert_to_gemini_args(content: str) -> str:
    """Convert argument placeholders for Gemini CLI format."""
    result = content.replace("$ARGUMENTS", "{{args}}")
    if fm.has_positional_args(result):
        result = f"Arguments: {{{{args}}}}\n\n{result}"
    return result


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
        return f"{module_name}.{cmd_name}.toml"
