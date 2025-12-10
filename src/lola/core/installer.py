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
from lola.models import Installation, InstallationRegistry, Module
from lola import ui


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
    verbose: bool = False,
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
        verbose: Show detailed per-item output

    Returns:
        Number of skills + commands installed
    """
    # Copy module to local .lola/modules/
    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills = []
    installed_commands = []
    failed_skills = []
    failed_commands = []

    # Skills have scope restrictions for some assistants
    skills_skipped_reason = None
    if module.skills:
        # Gemini CLI can only read skill files within the project workspace
        if assistant == 'gemini-cli' and scope == 'user':
            skills_skipped_reason = "user scope not supported"

        # Cursor only supports project-level rules for skills
        if assistant == 'cursor' and scope == 'user':
            skills_skipped_reason = "user scope not supported"

        if not skills_skipped_reason:
            try:
                skill_dest = get_assistant_skill_path(assistant, scope, project_path)
            except ValueError as e:
                ui.error(str(e))
                skill_dest = None

            if skill_dest:
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
                        else:
                            failed_skills.append(skill_name)

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
                            installed_skills.append(prefixed_name)
                        else:
                            failed_skills.append(skill_name)

    # Commands support all scopes for all assistants
    if module.commands:
        try:
            command_dest = get_assistant_command_path(assistant, scope, project_path)
        except ValueError as e:
            ui.error(f"Commands: {e}")
            command_dest = None

        if command_dest:
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
                    installed_commands.append(cmd_name)
                else:
                    failed_commands.append(cmd_name)

    # Print compact summary for this assistant
    if skills_skipped_reason:
        ui.assistant_summary(assistant, skipped_reason=skills_skipped_reason)
    elif installed_skills or installed_commands:
        ui.assistant_summary(assistant, skills=installed_skills, commands=installed_commands)

        # In verbose mode, list all items after the summary
        if verbose:
            for skill in installed_skills:
                ui.item_result(skill, ok=True, indent=2)
            for cmd in installed_commands:
                ui.item_result(f"/{module.name}-{cmd}", ok=True, indent=2)

        # Show failures (always show failures, not just in verbose mode)
        if failed_skills or failed_commands:
            for skill in failed_skills:
                ui.item_result(skill, ok=False, note="source not found", indent=2)
            for cmd in failed_commands:
                ui.item_result(cmd, ok=False, note="source not found", indent=2)

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
