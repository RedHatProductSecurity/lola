"""GitHub Copilot target implementations (CLI and VS Code)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lola.config as config
import lola.frontmatter as fm
from .base import (
    BaseAssistantTarget,
    ManagedInstructionsTarget,
    MCPSupportMixin,
    _convert_env_var_to_cursor_vscode,
    _generate_passthrough_command,
    _transform_mcp_env_vars,
)


class CopilotCliTarget(MCPSupportMixin, ManagedInstructionsTarget, BaseAssistantTarget):
    """Target for GitHub Copilot CLI.

    Copilot CLI supports:
    - Skills in ~/.copilot/skills/<name>/SKILL.md (with name+description frontmatter)
    - Prompt files in .github/prompts/*.prompt.md
    - Agents in .github/agents/*.agent.md
    - Global instructions in .github/copilot-instructions.md
    - MCP servers in ~/.copilot/mcp-config.json (user) / .vscode/mcp.json (project),
      using the "mcpServers" key
    """

    name = "copilot-cli"
    supports_agents = True
    INSTRUCTIONS_FILE = "copilot-instructions.md"

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".copilot" / "skills"
        return Path(project_path) / ".github" / "skills"

    def get_command_path(
        self, project_path: str, scope: str = "project"
    ) -> Path | None:
        if scope == "user":
            return Path.home() / ".copilot" / "prompts"
        return Path(project_path) / ".github" / "prompts"

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".copilot" / "agents"
        return Path(project_path) / ".github" / "agents"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".copilot" / self.INSTRUCTIONS_FILE
        return Path(project_path) / ".github" / self.INSTRUCTIONS_FILE

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path | None:
        if scope == "user":
            return Path.home() / ".copilot" / "mcp-config.json"
        return Path(project_path) / ".vscode" / "mcp.json"

    def generate_skill(
        self,
        source_path: Path,
        dest_path: Path,
        skill_name: str,
        project_path: str | None = None,  # noqa: ARG002
    ) -> bool:
        """Generate SKILL.md in .copilot/skills/<name>/ directory.

        Copilot skills use a directory-per-skill structure with
        name + description in YAML frontmatter.
        """
        if not source_path.exists():
            return False

        skill_file = source_path / config.SKILL_FILE
        if not skill_file.exists():
            return False

        content = skill_file.read_text(encoding="utf-8-sig")
        frontmatter, body = fm.parse(content)

        description = frontmatter.get("description")
        if not description:
            return False

        skill_dir = dest_path / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Build Copilot-compatible frontmatter (requires name + description)
        import yaml

        copilot_fm: dict = {
            "name": skill_name,
            "description": description,
        }
        if frontmatter.get("applyTo"):
            copilot_fm["applyTo"] = frontmatter["applyTo"]
        elif frontmatter.get("globs"):
            copilot_fm["applyTo"] = frontmatter["globs"]

        fm_str = yaml.dump(
            copilot_fm, default_flow_style=False, sort_keys=False
        ).rstrip()
        output = f"---\n{fm_str}\n---\n{body}"

        dest_file = skill_dir / "SKILL.md"
        dest_file.write_text(output, encoding="utf-8")

        # Copy supporting files (scripts, examples, etc.)
        import shutil

        for item in source_path.iterdir():
            if item.name == config.SKILL_FILE:
                continue
            dest_item = skill_dir / item.name
            if item.is_dir():
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
            else:
                shutil.copy2(item, dest_item)

        return True

    def remove_skill(self, dest_path: Path, skill_name: str) -> bool:
        """Remove a skill's directory."""
        import shutil

        removed = False
        skill_dir = dest_path / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
            removed = True
        # Legacy cleanup: old .instructions.md format
        legacy_file = (
            dest_path.parent / "instructions" / f"{skill_name}.instructions.md"
        )
        if legacy_file.exists():
            legacy_file.unlink()
            removed = True
        return removed

    def generate_command(
        self,
        source_path: Path,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        filename = self.get_command_filename(module_name, cmd_name)
        return _generate_passthrough_command(source_path, dest_dir, filename)

    def get_command_filename(self, module_name: str, cmd_name: str) -> str:  # noqa: ARG002
        """Copilot uses .prompt.md extension for commands."""
        return f"{cmd_name}.prompt.md"

    def generate_agent(
        self,
        source_path: Path,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Generate agent file with .agent.md extension.

        Copilot agents use YAML frontmatter with fields like:
        - description: when to use this agent
        - tools: list of tools the agent can use
        """
        if not source_path.exists():
            return False
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = self.get_agent_filename(module_name, agent_name)
        content = source_path.read_text(encoding="utf-8-sig")

        (dest_dir / filename).write_text(content, encoding="utf-8")
        return True

    def get_agent_filename(self, module_name: str, agent_name: str) -> str:  # noqa: ARG002
        """Copilot uses .agent.md extension for agents."""
        return f"{agent_name}.agent.md"

    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Delete command file (.prompt.md)."""
        filename = self.get_command_filename(module_name, cmd_name)
        cmd_file = dest_dir / filename
        if cmd_file.exists():
            cmd_file.unlink()
        # Legacy cleanup
        legacy_file = dest_dir / f"{module_name}.{cmd_name}.prompt.md"
        if legacy_file.exists():
            legacy_file.unlink()
        return True

    def remove_agent(
        self,
        dest_dir: Path,
        agent_name: str,
        module_name: str,
    ) -> bool:
        """Delete agent file (.agent.md)."""
        filename = self.get_agent_filename(module_name, agent_name)
        agent_file = dest_dir / filename
        if agent_file.exists():
            agent_file.unlink()
        # Legacy cleanup
        legacy_file = dest_dir / f"{module_name}.{agent_name}.agent.md"
        if legacy_file.exists():
            legacy_file.unlink()
        return True


# =============================================================================
# VS Code MCP helpers (.vscode/mcp.json uses the "servers" key)
# =============================================================================


def _transform_mcp_to_vscode(server_config: dict[str, Any]) -> dict[str, Any]:
    """Transform a Lola MCP server config into VS Code's mcp.json format.

    VS Code expects an explicit ``type`` field: ``stdio`` for command-based
    servers and ``http``/``sse`` for remote servers. Remote configs already
    carry their ``type``; command-based (stdio) configs do not, so it is added.
    Env var references are converted from Lola's ``${VAR}`` syntax to VS
    Code's ``${env:VAR}`` syntax.
    """
    result = _transform_mcp_env_vars(server_config, _convert_env_var_to_cursor_vscode)
    if "type" not in result:
        result["type"] = "http" if "url" in result else "stdio"
    return result


def _merge_mcps_into_vscode_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001 - kept for API symmetry, not used
    mcps: dict[str, dict[str, Any]],
) -> bool:
    """Merge MCP servers into a VS Code mcp.json config.

    VS Code uses the top-level ``servers`` key (not ``mcpServers``). Server
    keys are written as-is (no module-name prefix).
    """
    if dest_path.exists():
        try:
            existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            existing_config = {}
    else:
        existing_config = {}

    if "servers" not in existing_config:
        existing_config["servers"] = {}

    for name, server_config in mcps.items():
        existing_config["servers"][name] = _transform_mcp_to_vscode(server_config)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(json.dumps(existing_config, indent=2) + "\n", encoding="utf-8")
    return True


def _remove_mcps_from_vscode_file(
    dest_path: Path,
    module_name: str,  # noqa: ARG001 - kept for API symmetry, not used
    mcp_names: list[str] | None = None,
) -> bool:
    """Remove a module's MCP servers from a VS Code mcp.json config."""
    if not mcp_names:  # handles None and empty list — nothing to remove
        return True

    if not dest_path.exists():
        return True

    try:
        existing_config = json.loads(dest_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return True

    if "servers" not in existing_config:
        return True

    for name in mcp_names:
        existing_config["servers"].pop(name, None)

    remaining_keys = {k for k in existing_config.keys() if k != "$schema"}
    if not existing_config["servers"] and remaining_keys == {"servers"}:
        dest_path.unlink()
    else:
        dest_path.write_text(
            json.dumps(existing_config, indent=2) + "\n", encoding="utf-8"
        )
    return True


class CopilotVSCodeTarget(CopilotCliTarget):
    """Target for GitHub Copilot in VS Code.

    Identical to copilot-cli except:
    - MCP servers are written to .vscode/mcp.json using VS Code's ``servers``
      key (not ``mcpServers``), with an explicit per-server ``type``.
    - Slash commands have no user-scope filesystem location in VS Code, so
      user-scope command installs are skipped with a warning.
    - MCP servers have no user-scope filesystem location in VS Code, so
      user-scope MCP installs are skipped with a warning.
    """

    name = "copilot-vscode"

    def get_command_path(
        self, project_path: str, scope: str = "project"
    ) -> Path | None:
        # VS Code has no user-scope prompts directory; signal "unsupported".
        if scope == "user":
            return None
        return Path(project_path) / ".github" / "prompts"

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path | None:
        # VS Code reads project-scoped .vscode/mcp.json; there is no working
        # user-scope MCP file, so signal "unsupported" at user scope.
        if scope == "user":
            return None
        return Path(project_path) / ".vscode" / "mcp.json"

    def generate_mcps(
        self,
        mcps: dict[str, dict[str, Any]],
        dest_path: Path,
        module_name: str,
    ) -> bool:
        """Merge MCP servers using VS Code's mcp.json format."""
        if not mcps:
            return False
        return _merge_mcps_into_vscode_file(dest_path, module_name, mcps)

    def remove_mcps(
        self,
        dest_path: Path,
        module_name: str,
        mcp_names: list[str] | None = None,
    ) -> bool:
        """Remove a module's MCP servers from VS Code's mcp.json."""
        return _remove_mcps_from_vscode_file(dest_path, module_name, mcp_names)
