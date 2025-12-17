"""OpenCode target implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .base import (
    ManagedInstructionsTarget,
    ManagedSectionTarget,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
)


# =============================================================================
# OpenCode-specific MCP helpers
# =============================================================================


def _convert_env_var_syntax(value: str) -> str:
    """Convert ${VAR} syntax to OpenCode's {env:VAR} syntax."""
    return re.sub(r"\$\{([^}]+)\}", r"{env:\1}", value)


def _transform_mcp_to_opencode(server_config: dict[str, Any]) -> dict[str, Any]:
    """Transform Claude Code MCP config to OpenCode format.

    Claude Code format:
        {"command": "uv", "args": ["run", "..."], "env": {"VAR": "${VAR}"}}

    OpenCode format:
        {"type": "local", "command": ["uv", "run", "..."], "environment": {"VAR": "{env:VAR}"}}
    """
    result: dict[str, Any] = {"type": "local"}

    # Combine command and args into a single array
    command = server_config.get("command", "")
    args = server_config.get("args", [])
    if command:
        result["command"] = [command, *args]

    # Transform env to environment with converted syntax
    env = server_config.get("env", {})
    if env:
        result["environment"] = {
            k: _convert_env_var_syntax(v) if isinstance(v, str) else v
            for k, v in env.items()
        }

    return result


def _merge_mcps_into_opencode_file(
    dest_path: Path,
    module_name: str,
    mcps: dict[str, dict[str, Any]],
) -> bool:
    """Merge MCP servers into OpenCode's config format.

    OpenCode uses a different structure:
    - Root key is "mcp" not "mcpServers"
    - Servers need "type": "local"
    - "command" is an array including args
    - "env" becomes "environment"
    - Environment variables use {env:VAR} syntax
    """
    # Read existing config
    if dest_path.exists():
        try:
            existing_config = json.loads(dest_path.read_text())
        except json.JSONDecodeError:
            existing_config = {}
    else:
        existing_config = {}

    # Add schema if not present
    if "$schema" not in existing_config:
        existing_config["$schema"] = "https://opencode.ai/config.json"

    # Ensure mcp key exists
    if "mcp" not in existing_config:
        existing_config["mcp"] = {}

    # Add prefixed servers with transformed config
    for name, server_config in mcps.items():
        prefixed_name = f"{module_name}-{name}"
        existing_config["mcp"][prefixed_name] = _transform_mcp_to_opencode(
            server_config
        )

    # Write back with $schema first
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure $schema is first by rebuilding dict
    ordered_config: dict[str, Any] = {"$schema": existing_config.pop("$schema")}
    ordered_config.update(existing_config)
    dest_path.write_text(json.dumps(ordered_config, indent=2) + "\n")
    return True


def _remove_mcps_from_opencode_file(
    dest_path: Path,
    module_name: str,
) -> bool:
    """Remove a module's MCP servers from OpenCode's config file."""
    if not dest_path.exists():
        return True

    try:
        existing_config = json.loads(dest_path.read_text())
    except json.JSONDecodeError:
        return True

    if "mcp" not in existing_config:
        return True

    # Remove servers with module prefix
    prefix = f"{module_name}-"
    existing_config["mcp"] = {
        k: v for k, v in existing_config["mcp"].items() if not k.startswith(prefix)
    }

    # Write back (or delete if mcp is empty and only $schema remains)
    remaining_keys = {k for k in existing_config.keys() if k != "$schema"}
    if not existing_config["mcp"] and remaining_keys == {"mcp"}:
        dest_path.unlink()
    else:
        dest_path.write_text(json.dumps(existing_config, indent=2) + "\n")
    return True


# =============================================================================
# OpenCodeTarget
# =============================================================================


class OpenCodeTarget(ManagedInstructionsTarget, ManagedSectionTarget):
    """Target for OpenCode assistant.

    OpenCode uses AGENTS.md for both skills and instructions (similar to Gemini's GEMINI.md approach).

    Note: OpenCodeTarget does NOT use MCPSupportMixin because it has its own MCP format.
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
        return Path(project_path) / "opencode.json"

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

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Generate/merge MCP servers using OpenCode's config format."""
        if not mcps:
            return False
        return _merge_mcps_into_opencode_file(dest_path, module_name, mcps)

    def remove_mcps(self, dest_path: Path, module_name: str) -> bool:
        """Remove a module's MCP servers from OpenCode's config file."""
        return _remove_mcps_from_opencode_file(dest_path, module_name)
