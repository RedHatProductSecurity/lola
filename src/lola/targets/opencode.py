"""OpenCode target implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import shutil

import lola.config as config
from .base import (
    BaseAssistantTarget,
    ManagedInstructionsTarget,
    _generate_agent_with_frontmatter,
    _generate_passthrough_command,
)


# =============================================================================
# OpenCode-specific MCP helpers
# =============================================================================


def _convert_env_var_syntax(value: str) -> str:
    """Convert ${VAR} syntax to OpenCode's {env:VAR} syntax."""
    return re.sub(r"\$\{([^}]+)\}", r"{env:\1}", value)


# Lola standard: http and sse only. OpenCode uses "remote" as its canonical type.
REMOTE_MCP_TYPES = ("http", "sse")

# Built-in OpenCode tools. Used to explicitly deny unlisted tools when
# converting from an allowlist, since OpenCode enables tools by default.
KNOWN_OPENCODE_TOOLS = frozenset(
    {
        "bash",
        "edit",
        "glob",
        "grep",
        "fetch",
        "list",
        "patch",
        "read",
        "todoreplace",
        "write",
    }
)

# Claude/Cursor tool names (lowercased) that map to a different OpenCode name.
_TO_OPENCODE_TOOL: dict[str, str] = {
    "webfetch": "fetch",
}


def _normalize_tool_name(name: str) -> str:
    """Lowercase a tool name and translate it to its OpenCode equivalent."""
    lowered = name.strip().lower()
    return _TO_OPENCODE_TOOL.get(lowered, lowered)


def _transform_agent_frontmatter(front: dict) -> dict:
    """Convert agent frontmatter fields to OpenCode's expected format.

    Normalises tools from any input dialect to OpenCode's ``{name: bool}``
    map.  When the input is an allowlist (comma string or list), known
    built-in tools that are **not** in the allowlist are explicitly set to
    ``False`` so that OpenCode does not leave them enabled by default.
    """
    tools = front.get("tools")
    if isinstance(tools, str):
        allowed = {_normalize_tool_name(t) for t in tools.split(",") if t.strip()}
        result = {t: True for t in allowed}
        if "*" not in allowed:
            for t in KNOWN_OPENCODE_TOOLS - allowed:
                result[t] = False
        front["tools"] = result
    elif isinstance(tools, list):
        allowed = {_normalize_tool_name(str(t)) for t in tools if t}
        result = {t: True for t in allowed}
        if "*" not in allowed:
            for t in KNOWN_OPENCODE_TOOLS - allowed:
                result[t] = False
        front["tools"] = result
    return front


def _transform_mcp_to_opencode(server_config: dict[str, Any]) -> dict[str, Any]:
    """Transform Lola MCP config to OpenCode format.

    Local (stdio):
        Input:  {"command": "uv", "args": ["run", "..."], "env": {"VAR": "${VAR}"}}
        Output: {"type": "local", "command": ["uv", "run", "..."], "environment": {"VAR": "{env:VAR}"}}

    Remote (http/sse):
        Input:  {"type": "http", "url": "https://...", "headers": {"Authorization": "Bearer ${TOKEN}"}}
        Output: {"type": "remote", "url": "https://...", "headers": {...}}  # OpenCode uses "remote"
    """
    server_type = server_config.get("type")
    if server_type in REMOTE_MCP_TYPES:
        # Remote server: convert to OpenCode's "remote" type
        url = server_config.get("url")
        if isinstance(url, str):
            url = _convert_env_var_syntax(url)
        remote_result: dict[str, Any] = {
            "type": "remote",
        }
        if url is not None:
            remote_result["url"] = url
        headers = server_config.get("headers", {})
        if headers:
            remote_result["headers"] = {
                k: _convert_env_var_syntax(v) if isinstance(v, str) else v
                for k, v in headers.items()
            }
        return remote_result

    # Local (stdio) server
    result: dict[str, Any] = {"type": "local"}
    command = server_config.get("command", "")
    args = server_config.get("args", [])
    if command:
        result["command"] = [command, *args]

    env = server_config.get("env", {})
    if env:
        result["environment"] = {
            k: _convert_env_var_syntax(v) if isinstance(v, str) else v
            for k, v in env.items()
        }

    return result


def _merge_mcps_into_opencode_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001 - kept for API symmetry, not used
    mcps: dict[str, dict[str, Any]],
) -> bool:
    """Merge MCP servers into OpenCode's config format.

    Server keys are written as-is (no module-name prefix). ``module_name`` is
    unused and retained only for interface symmetry with the remove helper.

    OpenCode uses a different structure from Claude Code:
    - Root key is "mcp" not "mcpServers"
    - Servers need "type": "local"
    - "command" is an array including args
    - "env" becomes "environment"
    - Environment variables use {env:VAR} syntax
    """
    # Read existing config
    if dest_path.exists():
        try:
            existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
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

    # Add servers with transformed config (no prefix)
    for name, server_config in mcps.items():
        existing_config["mcp"][name] = _transform_mcp_to_opencode(server_config)

    # Write back with $schema first
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure $schema is first by rebuilding dict
    ordered_config: dict[str, Any] = {"$schema": existing_config.pop("$schema")}
    ordered_config.update(existing_config)
    dest_path.write_text(json.dumps(ordered_config, indent=2) + "\n", encoding="utf-8")
    return True


def _remove_mcps_from_opencode_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001
    mcp_names: list[str] | None = None,
) -> bool:
    """Remove a module's MCP servers from OpenCode's config file."""
    if not mcp_names:  # handles None and empty list — nothing to remove
        return True

    if not dest_path.exists():
        return True

    try:
        existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return True

    if "mcp" not in existing_config:
        return True

    for name in mcp_names:
        existing_config["mcp"].pop(name, None)

    # Write back (or delete if mcp is empty and only $schema remains)
    remaining_keys = {k for k in existing_config.keys() if k != "$schema"}
    if not existing_config["mcp"] and remaining_keys == {"mcp"}:
        dest_path.unlink()
    else:
        dest_path.write_text(json.dumps(existing_config, indent=2) + "\n", encoding="utf-8")
    return True


# =============================================================================
# OpenCodeTarget
# =============================================================================


class OpenCodeTarget(ManagedInstructionsTarget, BaseAssistantTarget):
    """Target for OpenCode assistant.

    OpenCode supports file-based skills in .opencode/skills/<name>/SKILL.md
    and uses AGENTS.md for module instructions.

    Note: OpenCodeTarget does NOT use MCPSupportMixin because it has its own MCP format.
    """

    name = "opencode"
    supports_agents = True
    INSTRUCTIONS_FILE = "AGENTS.md"

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return config.get_user_config_dir() / "skills"
        return Path(project_path) / ".opencode" / "skills"

    def get_command_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return config.get_user_config_dir() / "commands"
        return Path(project_path) / ".opencode" / "commands"

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return config.get_user_config_dir() / "agents"
        return Path(project_path) / ".opencode" / "agents"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return config.get_user_config_dir() / self.INSTRUCTIONS_FILE
        return Path(project_path) / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return config.get_user_config_dir() / "opencode.json"
        return Path(project_path) / "opencode.json"

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Copy skill directory with SKILL.md and supporting files.

        OpenCode uses the Agent Skills standard with SKILL.md files
        at .opencode/skills/<skill-name>/SKILL.md.
        """
        if not source_path.exists():
            return False

        # Verify SKILL.md exists before creating destination directory
        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

        skill_dest = dest_path / skill_name
        skill_dest.mkdir(parents=True, exist_ok=True)

        # Copy SKILL.md
        shutil.copy2(skill_file, skill_dest / config.SKILL_FILE)

        # Copy supporting files (scripts, references, assets, etc.)
        for item in source_path.iterdir():
            if item.name == config.SKILL_FILE:
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
            {"mode": "subagent"},
            frontmatter_transforms=_transform_agent_frontmatter,
        )

    def remove_command(self, dest_dir: Path, cmd_name: str, module_name: str) -> bool:
        """Remove command file, also cleaning up legacy .opencode/command/ directory.

        This PR renamed .opencode/command/ → .opencode/commands/ and
        .opencode/agent/ → .opencode/agents/. The legacy fallback ensures
        files installed before that rename are not left orphaned.
        """
        result = super().remove_command(dest_dir, cmd_name, module_name)
        legacy_dir = dest_dir.parent / "command"
        if legacy_dir.is_dir():
            filename = self.get_command_filename(module_name, cmd_name)
            ext = Path(filename).suffix
            for name in (filename, f"{module_name}.{cmd_name}{ext}"):
                legacy_file = legacy_dir / name
                if legacy_file.exists():
                    legacy_file.unlink()
        return result

    def remove_agent(self, dest_dir: Path, agent_name: str, module_name: str) -> bool:
        """Remove agent file, also cleaning up legacy .opencode/agent/ directory."""
        result = super().remove_agent(dest_dir, agent_name, module_name)
        legacy_dir = dest_dir.parent / "agent"
        if legacy_dir.is_dir():
            filename = self.get_agent_filename(module_name, agent_name)
            ext = Path(filename).suffix
            for name in (filename, f"{module_name}.{agent_name}{ext}"):
                legacy_file = legacy_dir / name
                if legacy_file.exists():
                    legacy_file.unlink()
        return result

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

    def remove_mcps(
        self,
        dest_path: Path,
        module_name: str,
        mcp_names: list[str] | None = None,
    ) -> bool:
        """Remove a module's MCP servers from OpenCode's config file."""
        return _remove_mcps_from_opencode_file(dest_path, module_name, mcp_names)
