"""
Install orchestration functions for lola targets.

This module provides:
- Registry management (get_registry)
- Module copying (copy_module_to_local)
- Installation helpers for skills, commands, agents, instructions, MCPs
- The main install_to_assistant orchestration function
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console

import lola.config as config
from lola.exceptions import ConfigurationError
from lola.models import Installation, InstallationRegistry, Module

from .base import AssistantTarget, _get_content_path, _get_skill_description, _skill_source_dir

console = Console()


# =============================================================================
# Registry
# =============================================================================


def get_registry() -> InstallationRegistry:
    return InstallationRegistry(config.INSTALLED_FILE)


# =============================================================================
# Install helpers
# =============================================================================


def copy_module_to_local(module: Module, local_modules_path: Path) -> Path:
    """Copy module to local .lola/modules directory."""
    dest = local_modules_path / module.name
    if dest.resolve() == module.path.resolve():
        return dest

    local_modules_path.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    shutil.copytree(module.path, dest)
    return dest


def _install_skills(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install skills for a target. Returns (installed, failed) lists."""
    if not module.skills:
        return [], []

    installed: list[str] = []
    failed: list[str] = []
    skill_dest = target.get_skill_path(project_path) if project_path else None

    if not skill_dest:
        return [], []

    # Batch updates for managed section targets (Gemini, OpenCode)
    if target.uses_managed_section:
        batch_skills: list[tuple[str, str, Path]] = []
        for skill in module.skills:
            source = _skill_source_dir(local_module_path, skill)
            prefixed = f"{module.name}.{skill}"
            if source.exists():
                batch_skills.append((skill, _get_skill_description(source), source))
                installed.append(prefixed)
            else:
                failed.append(skill)
        if batch_skills:
            target.generate_skills_batch(
                skill_dest, module.name, batch_skills, project_path
            )
    else:
        for skill in module.skills:
            source = _skill_source_dir(local_module_path, skill)
            prefixed = f"{module.name}.{skill}"
            if target.generate_skill(source, skill_dest, prefixed, project_path):
                installed.append(prefixed)
            else:
                failed.append(skill)

    return installed, failed


def _install_commands(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install commands for a target. Returns (installed, failed) lists."""
    if not module.commands:
        return [], []

    installed: list[str] = []
    failed: list[str] = []
    command_dest = target.get_command_path(project_path) if project_path else None

    if not command_dest:
        return [], []

    content_path = _get_content_path(local_module_path)
    commands_dir = content_path / "commands"
    for cmd in module.commands:
        source = commands_dir / f"{cmd}.md"
        if target.generate_command(source, command_dest, cmd, module.name):
            installed.append(cmd)
        else:
            failed.append(cmd)

    return installed, failed


def _install_agents(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install agents for a target. Returns (installed, failed) lists."""
    if not module.agents or not target.supports_agents:
        return [], []

    agent_dest = target.get_agent_path(project_path) if project_path else None
    if not agent_dest:
        return [], []

    installed: list[str] = []
    failed: list[str] = []

    content_path = _get_content_path(local_module_path)
    agents_dir = content_path / "agents"
    for agent in module.agents:
        source = agents_dir / f"{agent}.md"
        if target.generate_agent(source, agent_dest, agent, module.name):
            installed.append(agent)
        else:
            failed.append(agent)

    return installed, failed


def _install_instructions(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> bool:
    """Install module instructions for a target. Returns True if installed."""
    from lola.models import INSTRUCTIONS_FILE

    if not module.has_instructions or not project_path:
        return False

    content_path = _get_content_path(local_module_path)
    instructions_source = content_path / INSTRUCTIONS_FILE
    if not instructions_source.exists():
        return False

    instructions_dest = target.get_instructions_path(project_path)
    return target.generate_instructions(
        instructions_source, instructions_dest, module.name
    )


def _install_mcps(
    target: AssistantTarget,
    module: Module,
    local_module_path: Path,
    project_path: str | None,
) -> tuple[list[str], list[str]]:
    """Install MCPs for a target. Returns (installed, failed) lists."""
    if not module.mcps or not project_path:
        return [], []

    mcp_dest = target.get_mcp_path(project_path)
    if not mcp_dest:
        return [], []

    # Load mcps.json from local module (respecting module/ subdirectory)
    content_path = _get_content_path(local_module_path)
    mcps_file = content_path / config.MCPS_FILE
    if not mcps_file.exists():
        return [], list(module.mcps)

    try:
        mcps_data = json.loads(mcps_file.read_text())
        servers = mcps_data.get("mcpServers", {})
    except json.JSONDecodeError:
        return [], list(module.mcps)

    # Generate MCPs
    if target.generate_mcps(servers, mcp_dest, module.name):
        installed = [f"{module.name}-{name}" for name in servers.keys()]
        return installed, []

    return [], list(module.mcps)


def _print_summary(
    assistant: str,
    installed_skills: list[str],
    installed_commands: list[str],
    installed_agents: list[str],
    installed_mcps: list[str],
    has_instructions: bool,
    failed_skills: list[str],
    failed_commands: list[str],
    failed_agents: list[str],
    failed_mcps: list[str],
    module_name: str,
    verbose: bool,
) -> None:
    """Print installation summary."""
    if not (
        installed_skills
        or installed_commands
        or installed_agents
        or installed_mcps
        or has_instructions
    ):
        return

    parts: list[str] = []
    if installed_skills:
        parts.append(
            f"{len(installed_skills)} skill{'s' if len(installed_skills) != 1 else ''}"
        )
    if installed_commands:
        parts.append(
            f"{len(installed_commands)} command{'s' if len(installed_commands) != 1 else ''}"
        )
    if installed_agents:
        parts.append(
            f"{len(installed_agents)} agent{'s' if len(installed_agents) != 1 else ''}"
        )
    if installed_mcps:
        parts.append(
            f"{len(installed_mcps)} MCP{'s' if len(installed_mcps) != 1 else ''}"
        )
    if has_instructions:
        parts.append("instructions")

    console.print(f"  [green]{assistant}[/green] [dim]({', '.join(parts)})[/dim]")

    if verbose:
        for skill in installed_skills:
            console.print(f"    [green]{skill}[/green]")
        for cmd in installed_commands:
            console.print(f"    [green]/{module_name}.{cmd}[/green]")
        for agent in installed_agents:
            console.print(f"    [green]@{module_name}.{agent}[/green]")
        for mcp in installed_mcps:
            console.print(f"    [green]mcp:{mcp}[/green]")
        if has_instructions:
            console.print("    [green]instructions[/green]")

    if failed_skills or failed_commands or failed_agents or failed_mcps:
        for skill in failed_skills:
            console.print(f"    [red]{skill}[/red] [dim](source not found)[/dim]")
        for cmd in failed_commands:
            console.print(f"    [red]{cmd}[/red] [dim](source not found)[/dim]")
        for agent in failed_agents:
            console.print(f"    [red]{agent}[/red] [dim](source not found)[/dim]")
        for mcp in failed_mcps:
            console.print(f"    [red]{mcp}[/red] [dim](source not found)[/dim]")


def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
    verbose: bool = False,
) -> int:
    """Install module to a specific assistant."""
    # Late import to avoid circular imports - get_target is defined in __init__.py
    from lola.targets import get_target

    target = get_target(assistant)

    if scope != "project":
        raise ConfigurationError("Only project scope is supported")

    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills, failed_skills = _install_skills(
        target, module, local_module_path, project_path
    )
    installed_commands, failed_commands = _install_commands(
        target, module, local_module_path, project_path
    )
    installed_agents, failed_agents = _install_agents(
        target, module, local_module_path, project_path
    )
    installed_mcps, failed_mcps = _install_mcps(
        target, module, local_module_path, project_path
    )
    instructions_installed = _install_instructions(
        target, module, local_module_path, project_path
    )

    _print_summary(
        assistant,
        installed_skills,
        installed_commands,
        installed_agents,
        installed_mcps,
        instructions_installed,
        failed_skills,
        failed_commands,
        failed_agents,
        failed_mcps,
        module.name,
        verbose,
    )

    if (
        installed_skills
        or installed_commands
        or installed_agents
        or installed_mcps
        or instructions_installed
    ):
        registry.add(
            Installation(
                module_name=module.name,
                assistant=assistant,
                scope=scope,
                project_path=project_path,
                skills=installed_skills,
                commands=installed_commands,
                agents=installed_agents,
                mcps=installed_mcps,
                has_instructions=instructions_installed,
            )
        )

    return (
        len(installed_skills)
        + len(installed_commands)
        + len(installed_agents)
        + len(installed_mcps)
        + (1 if instructions_installed else 0)
    )
