"""
Installation logic for lola modules.

This module handles installing and managing module installations
across different AI assistants.
"""

import shutil
from pathlib import Path
from typing import Optional

from lola.config import (
    INSTALLED_FILE,
    get_assistant_command_path,
    get_assistant_skill_path,
)
from lola.core.generator import (
    generate_claude_skill,
    generate_cursor_rule,
    generate_claude_command,
    generate_cursor_command,
    generate_gemini_command,
    get_skill_description,
    update_gemini_md,
)
from lola.layout import console
from lola.models import Installation, InstallationRegistry, Module


def get_registry() -> InstallationRegistry:
    """Get the installation registry."""
    return InstallationRegistry(INSTALLED_FILE)


def copy_module_to_local(module: Module, local_modules_path: Path) -> Path:
    """
    Copy a module from the global registry to the local .lola/modules/.

    Args:
        module: The module to copy
        local_modules_path: Path to .lola/modules/

    Returns:
        Path to the copied module
    """
    dest = local_modules_path / module.name

    # If source and dest are the same (user scope), just return the path
    if dest.resolve() == module.path.resolve():
        return dest

    # Ensure parent directory exists
    local_modules_path.mkdir(parents=True, exist_ok=True)

    # Remove existing link/directory if present
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    # Copy the module (not symlink)
    shutil.copytree(module.path, dest)

    return dest


def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
) -> int:
    """
    Install a module's skills and commands to a specific assistant.

    Args:
        module: The module to install
        assistant: Target assistant (claude-code, cursor, gemini-cli)
        scope: Installation scope (user or project)
        project_path: Path to project (required for project scope)
        local_modules: Path to local .lola/modules/
        registry: Installation registry

    Returns:
        Number of skills + commands installed
    """
    # Copy module to local .lola/modules/
    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills = []
    installed_commands = []

    # Skills have scope restrictions for some assistants
    skills_skipped = False
    if module.skills:
        # Gemini CLI can only read skill files within the project workspace
        if assistant == 'gemini-cli' and scope == 'user':
            console.print(f"[yellow]{assistant}[/yellow] skills -> skipped (user scope not supported)")
            console.print("  Gemini CLI skills can only read files within project directories.")
            skills_skipped = True

        # Cursor only supports project-level rules for skills
        if assistant == 'cursor' and scope == 'user':
            console.print(f"[yellow]{assistant}[/yellow] skills -> skipped (user scope not supported)")
            console.print("  Cursor only supports project-level rules for skills.")
            skills_skipped = True

        if not skills_skipped:
            try:
                skill_dest = get_assistant_skill_path(assistant, scope, project_path)
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
                skill_dest = None

            if skill_dest:
                console.print(f"[bold]{assistant}[/bold] skills -> {skill_dest}")

                if assistant == 'gemini-cli':
                    # Gemini: Add entries to GEMINI.md file
                    gemini_skills = []
                    for skill_rel in module.skills:
                        skill_name = Path(skill_rel).name
                        source = local_module_path / skill_name
                        prefixed_name = f"{module.name}-{skill_name}"
                        if source.exists():
                            description = get_skill_description(source)
                            gemini_skills.append((skill_name, description, source))
                            installed_skills.append(prefixed_name)
                            console.print(f"  [green]{prefixed_name}[/green]")
                        else:
                            console.print(f"  [red]{skill_name}[/red] (source not found)")

                    if gemini_skills:
                        update_gemini_md(skill_dest, module.name, gemini_skills, project_path)
                else:
                    # Claude/Cursor: Generate individual files
                    for skill_rel in module.skills:
                        skill_name = Path(skill_rel).name
                        source = local_module_path / skill_name
                        # Prefix with module name to avoid conflicts
                        prefixed_name = f"{module.name}-{skill_name}"

                        if assistant == 'cursor':
                            success = generate_cursor_rule(source, skill_dest, prefixed_name, project_path)
                        else:  # claude-code
                            dest = skill_dest / prefixed_name
                            success = generate_claude_skill(source, dest)

                        if success:
                            console.print(f"  [green]{prefixed_name}[/green]")
                            installed_skills.append(prefixed_name)
                        else:
                            console.print(f"  [red]{skill_name}[/red] (source not found)")

    # Commands support all scopes for all assistants
    if module.commands:
        try:
            command_dest = get_assistant_command_path(assistant, scope, project_path)
        except ValueError as e:
            console.print(f"[red]Commands: {e}[/red]")
            command_dest = None

        if command_dest:
            console.print(f"[bold]{assistant}[/bold] commands -> {command_dest}")

            commands_dir = local_module_path / 'commands'
            for cmd_name in module.commands:
                source = commands_dir / f'{cmd_name}.md'

                if assistant == 'gemini-cli':
                    success = generate_gemini_command(source, command_dest, cmd_name, module.name)
                elif assistant == 'cursor':
                    success = generate_cursor_command(source, command_dest, cmd_name, module.name)
                else:  # claude-code
                    success = generate_claude_command(source, command_dest, cmd_name, module.name)

                if success:
                    console.print(f"  [green]/{module.name}-{cmd_name}[/green]")
                    installed_commands.append(cmd_name)
                else:
                    console.print(f"  [red]{cmd_name}[/red] (source not found)")

    # Record installation
    if installed_skills or installed_commands:
        installation = Installation(
            module_name=module.name,
            assistant=assistant,
            scope=scope,
            project_path=project_path,
            skills=installed_skills,
            commands=installed_commands,
        )
        registry.add(installation)

    return len(installed_skills) + len(installed_commands)
