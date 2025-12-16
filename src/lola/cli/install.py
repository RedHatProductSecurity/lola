"""
Install CLI commands.

Commands for installing, uninstalling, updating, and listing module installations.
"""

import shutil
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lola.config import MODULES_DIR
from lola.models import Module
from lola.targets import (
    TARGETS,
    _get_skill_description,
    _skill_source_dir,
    copy_module_to_local,
    get_registry,
    get_target,
    install_to_assistant,
)
from lola.utils import ensure_lola_dirs, get_local_modules_path

console = Console()


@click.command(name="install")
@click.argument("module_name")
@click.option(
    "-a",
    "--assistant",
    type=click.Choice(list(TARGETS.keys())),
    default=None,
    help="AI assistant to install skills for (default: all)",
)
@click.option(
    "-s",
    "--scope",
    type=click.Choice(["user", "project"]),
    default="project",
    help="Installation scope",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed output for each skill and command",
)
@click.argument("project_path", required=False, default="./")
def install_cmd(
    module_name: str,
    assistant: Optional[str],
    scope: str,
    verbose: bool,
    project_path: str,
):
    """
    Install a module's skills to AI assistants.

    If no assistant is specified, installs to all assistants.
    If no project path is specified, installs to the current directory.

    \b
    Examples:
        lola install my-module                              # All assistants in the current directory
        lola install my-module -a claude-code               # Specific assistant in the current directory
        lola install my-module -s user                      # User scope (in the user's home directory)
        lola install my-module -s project ./my-project      # Project scope (in the specified project directory)
    """
    ensure_lola_dirs()

    # Validate project path for project scope
    if scope == "project":
        project_path = str(Path(project_path).resolve())
        if not Path(project_path).exists():
            console.print(f"[red]Project path does not exist: {project_path}[/red]")
            raise SystemExit(1)

    # Find module in global registry
    module_path = MODULES_DIR / module_name
    if not module_path.exists():
        console.print(f"[red]Module '{module_name}' not found[/red]")
        console.print("[dim]Use 'lola mod ls' to see available modules[/dim]")
        console.print("[dim]Use 'lola mod add <source>' to add a module[/dim]")
        raise SystemExit(1)

    module = Module.from_path(module_path)
    if not module:
        console.print("[red]Invalid module: no skills, commands, or agents found[/red]")
        console.print("[dim]Expected structure: skills/<name>/SKILL.md, commands/*.md, or agents/*.md[/dim]")
        raise SystemExit(1)

    # Validate module structure and skill files
    is_valid, errors = module.validate()
    if not is_valid:
        console.print(f"[red]Module '{module_name}' has validation errors:[/red]")
        for err in errors:
            console.print(f"  [red]{err}[/red]")
        raise SystemExit(1)

    if not module.skills and not module.commands and not module.agents:
        console.print(
            f"[yellow]Module '{module_name}' has no skills, commands, or agents defined[/yellow]"
        )
        return

    # Get paths and registry
    local_modules = get_local_modules_path(project_path)
    registry = get_registry()

    # Determine which assistants to install to
    assistants_to_install = [assistant] if assistant else list(TARGETS.keys())

    # Build location string
    if scope == "project":
        location = project_path
    else:
        location = "~/.lola (user scope)"

    console.print(f"\n[bold]Installing {module_name} -> {location}[/bold]")
    console.print()

    total_installed = 0
    for asst in assistants_to_install:
        total_installed += install_to_assistant(
            module, asst, scope, project_path, local_modules, registry, verbose
        )

    console.print()
    console.print(
        f"[green]Installed to {len(assistants_to_install)} assistant{'s' if len(assistants_to_install) != 1 else ''}[/green]"
    )


@click.command(name="uninstall")
@click.argument("module_name")
@click.option(
    "-a",
    "--assistant",
    type=click.Choice(list(TARGETS.keys())),
    default=None,
    help="AI assistant to uninstall from (optional)",
)
@click.option(
    "-s",
    "--scope",
    type=click.Choice(["user", "project"]),
    default=None,
    help="Installation scope (optional)",
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Show detailed output for each file removed"
)
@click.argument("project_path", required=False, default=None)
@click.option(
    "-f", "--force", is_flag=True, help="Force uninstall without confirmation"
)
def uninstall_cmd(
    module_name: str,
    assistant: Optional[str],
    scope: Optional[str],
    verbose: bool,
    project_path: Optional[str],
    force: bool,
):
    """
    Uninstall a module's skills from AI assistants.

    Removes generated skill files but keeps the module in the registry.
    Use 'lola mod rm' to fully remove a module.

    \b
    Examples:
        lola uninstall my-module
        lola uninstall my-module -a claude-code
        lola uninstall my-module -a cursor -s project ./my-project
    """
    ensure_lola_dirs()

    registry = get_registry()
    installations = registry.find(module_name)

    if not installations:
        console.print(f"[yellow]No installations found for '{module_name}'[/yellow]")
        return

    # Filter by assistant/scope if provided
    if assistant:
        installations = [i for i in installations if i.assistant == assistant]
    if scope:
        installations = [i for i in installations if i.scope == scope]
    if project_path:
        project_path = str(Path(project_path).resolve())
        installations = [i for i in installations if i.project_path == project_path]

    if not installations:
        console.print("[yellow]No matching installations found[/yellow]")
        return

    # Show what will be uninstalled
    console.print(f"\n[bold]Uninstalling {module_name}[/bold]")
    console.print()

    # Group installations by project for cleaner display
    by_project = {}
    for inst in installations:
        key = inst.project_path or "~/.lola (user scope)"
        if key not in by_project:
            by_project[key] = []
        by_project[key].append(inst)

    for project, insts in by_project.items():
        assistants = [i.assistant for i in insts]
        skill_count = len(insts[0].skills) if insts[0].skills else 0
        cmd_count = len(insts[0].commands) if insts[0].commands else 0
        agent_count = len(insts[0].agents) if insts[0].agents else 0

        parts = []
        if skill_count:
            parts.append(f"{skill_count} skill{'s' if skill_count != 1 else ''}")
        if cmd_count:
            parts.append(f"{cmd_count} command{'s' if cmd_count != 1 else ''}")
        if agent_count:
            parts.append(f"{agent_count} agent{'s' if agent_count != 1 else ''}")

        summary = ", ".join(parts) if parts else "no items"
        console.print(f"  [dim]{project}[/dim]")
        console.print(f"    {', '.join(assistants)} [dim]({summary})[/dim]")

    console.print()

    # Confirm if multiple installations and not forced
    if len(installations) > 1 and not force:
        console.print("[yellow]Multiple installations found[/yellow]")
        console.print(
            "[dim]Use -a <assistant> and -s <scope> to target specific installation[/dim]"
        )
        console.print("[dim]Use -f/--force to uninstall all[/dim]")
        console.print()

        if not click.confirm("Uninstall all?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Uninstall each
    removed_count = 0
    for inst in installations:
        target = get_target(inst.assistant)

        # Remove skill files
        if inst.skills and inst.project_path:
            skill_dest = target.get_skill_path(inst.project_path)

            if target.uses_managed_section:
                # Managed section targets: remove module section from GEMINI.md/AGENTS.md
                if target.remove_skill(skill_dest, module_name):
                    removed_count += 1
                    if verbose:
                        console.print(f"  [green]Removed skills from {skill_dest}[/green]")
            else:
                for skill in inst.skills:
                    if target.remove_skill(skill_dest, skill):
                        removed_count += 1
                        if verbose:
                            console.print(f"  [green]Removed {skill}[/green]")

        # Remove command files
        if inst.commands and inst.project_path:
            command_dest = target.get_command_path(inst.project_path)

            for cmd_name in inst.commands:
                filename = target.get_command_filename(module_name, cmd_name)
                cmd_file = command_dest / filename
                if cmd_file.exists():
                    cmd_file.unlink()
                    removed_count += 1
                    if verbose:
                        console.print(f"  [green]Removed {cmd_file}[/green]")

        # Remove agent files
        if inst.agents and inst.project_path:
            agent_dest = target.get_agent_path(inst.project_path)

            if agent_dest:
                for agent_name in inst.agents:
                    filename = target.get_agent_filename(module_name, agent_name)
                    agent_file = agent_dest / filename
                    if agent_file.exists():
                        agent_file.unlink()
                        removed_count += 1
                        if verbose:
                            console.print(f"  [green]Removed {agent_file}[/green]")

        # For project scope, also remove the project-local module copy
        if inst.scope == "project" and inst.project_path:
            local_modules = get_local_modules_path(inst.project_path)
            source_module = local_modules / module_name
            if source_module.is_symlink():
                source_module.unlink()
                removed_count += 1
                if verbose:
                    console.print(f"  [green]Removed symlink {source_module}[/green]")
            elif source_module.exists():
                # Handle legacy copies
                shutil.rmtree(source_module)
                removed_count += 1
                if verbose:
                    console.print(f"  [green]Removed {source_module}[/green]")

        # Remove from registry
        registry.remove(
            module_name,
            assistant=inst.assistant,
            scope=inst.scope,
            project_path=inst.project_path,
        )

    console.print(
        f"[green]Uninstalled from {len(installations)} installation{'s' if len(installations) != 1 else ''}[/green]"
    )


@click.command(name="update")
@click.argument("module_name", required=False, default=None)
@click.option(
    "-a",
    "--assistant",
    type=click.Choice(list(TARGETS.keys())),
    default=None,
    help="Filter by AI assistant",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed output for each skill and command",
)
def update_cmd(module_name: Optional[str], assistant: Optional[str], verbose: bool):
    """
    Regenerate assistant files from source in .lola/modules/.

    Use this after modifying skills in .lola/modules/ to update the
    generated files for all assistants.

    \b
    Examples:
        lola update                    # Update all modules
        lola update my-module          # Update specific module
        lola update -a cursor          # Update only Cursor files
        lola update -v                 # Verbose output
    """
    ensure_lola_dirs()

    registry = get_registry()
    installations = registry.all()

    if module_name:
        installations = [i for i in installations if i.module_name == module_name]
    if assistant:
        installations = [i for i in installations if i.assistant == assistant]

    if not installations:
        console.print("[yellow]No installations to update[/yellow]")
        return

    # Group installations by module name for cleaner display
    by_module = {}
    for inst in installations:
        if inst.module_name not in by_module:
            by_module[inst.module_name] = []
        by_module[inst.module_name].append(inst)

    module_word = "module" if len(by_module) == 1 else "modules"
    console.print(f"\n[bold]Updating {len(by_module)} {module_word}[/bold]")
    console.print()

    # Track stale installations and errors
    stale_installations = []

    for mod_name, mod_installations in by_module.items():
        console.print(f"[bold]{mod_name}[/bold]")

        # Group by (scope, path) for display
        by_scope_path = {}
        for inst in mod_installations:
            key = (inst.scope, inst.project_path)
            if key not in by_scope_path:
                by_scope_path[key] = []
            by_scope_path[key].append(inst)

        for (scope, project_path), scope_insts in by_scope_path.items():
            console.print(f"  [dim]scope:[/dim] {scope}")
            if project_path:
                console.print(f'  [dim]path:[/dim] "{project_path}"')

            for inst in scope_insts:
                # Check if project path still exists for project-scoped installations
                if inst.scope == "project" and inst.project_path:
                    if not Path(inst.project_path).exists():
                        console.print(
                            f"    [red]{inst.assistant}: project path no longer exists[/red]"
                        )
                        stale_installations.append(inst)
                        continue

                # Get the global module to refresh from
                global_module_path = MODULES_DIR / inst.module_name
                if not global_module_path.exists():
                    console.print(f"    [red]{inst.assistant}: module not found in registry[/red]")
                    continue

                global_module = Module.from_path(global_module_path)
                if not global_module:
                    console.print(
                        f"    [red]{inst.assistant}: invalid module[/red]"
                    )
                    continue

                # Validate module structure and skill files
                is_valid, errors = global_module.validate()
                if not is_valid:
                    console.print(
                        f"    [red]{inst.assistant}: validation errors[/red]"
                    )
                    for err in errors:
                        console.print(f"      [red]{err}[/red]")
                    continue

                local_modules = get_local_modules_path(inst.project_path)
                target = get_target(inst.assistant)

                # Refresh the local copy from global module
                source_module = copy_module_to_local(global_module, local_modules)

                skill_dest = target.get_skill_path(inst.project_path)

                # Compute current skills, commands, and agents from the module (with prefixes)
                current_skills = {f"{inst.module_name}-{s}" for s in global_module.skills}
                current_commands = set(global_module.commands)
                current_agents = set(global_module.agents)

                # Find orphaned items (in registry but not in module)
                orphaned_skills = set(inst.skills) - current_skills
                orphaned_commands = set(inst.commands) - current_commands
                orphaned_agents = set(inst.agents) - current_agents

                # Track results for this installation
                skills_ok = 0
                skills_failed = 0
                commands_ok = 0
                commands_failed = 0
                agents_ok = 0
                agents_failed = 0
                orphans_removed = 0

                # Remove orphaned skill files (not for managed section targets - they rebuild the whole section)
                if orphaned_skills and not target.uses_managed_section:
                    for skill in orphaned_skills:
                        if target.remove_skill(skill_dest, skill):
                            orphans_removed += 1
                            if verbose:
                                console.print(
                                    f"      [yellow]- {skill}[/yellow] [dim](orphaned)[/dim]"
                                )

                # Remove orphaned command files
                if orphaned_commands:
                    command_dest = target.get_command_path(inst.project_path)
                    for cmd_name in orphaned_commands:
                        filename = target.get_command_filename(inst.module_name, cmd_name)
                        orphan_file = command_dest / filename
                        if orphan_file.exists():
                            orphan_file.unlink()
                            orphans_removed += 1
                            if verbose:
                                console.print(
                                    f"      [yellow]- /{inst.module_name}-{cmd_name}[/yellow] [dim](orphaned)[/dim]"
                                )

                # Remove orphaned agent files
                if orphaned_agents:
                    agent_dest = target.get_agent_path(inst.project_path)
                    if agent_dest:
                        for agent_name in orphaned_agents:
                            filename = target.get_agent_filename(inst.module_name, agent_name)
                            orphan_file = agent_dest / filename
                            if orphan_file.exists():
                                orphan_file.unlink()
                                orphans_removed += 1
                                if verbose:
                                    console.print(
                                        f"      [yellow]- @{inst.module_name}-{agent_name}[/yellow] [dim](orphaned)[/dim]"
                                    )

                # Update skills - iterate over CURRENT module skills, not old registry
                if global_module.skills:
                    if target.uses_managed_section:
                        # Managed section targets: Update entries in GEMINI.md/AGENTS.md
                        batch_skills = []
                        for original_skill in global_module.skills:
                            prefixed_skill = f"{inst.module_name}-{original_skill}"
                            source = _skill_source_dir(source_module, original_skill)
                            if source.exists():
                                description = _get_skill_description(source)
                                batch_skills.append((original_skill, description, source))
                                skills_ok += 1
                                if verbose:
                                    console.print(f"      [green]{prefixed_skill}[/green]")
                            else:
                                skills_failed += 1
                                if verbose:
                                    console.print(
                                        f"      [red]{original_skill}[/red] [dim](source not found)[/dim]"
                                    )
                        if batch_skills:
                            target.generate_skills_batch(
                                skill_dest,
                                inst.module_name,
                                batch_skills,
                                inst.project_path,
                            )
                    else:
                        for original_skill in global_module.skills:
                            prefixed_skill = f"{inst.module_name}-{original_skill}"
                            source = _skill_source_dir(source_module, original_skill)

                            success = target.generate_skill(
                                source, skill_dest, prefixed_skill, inst.project_path
                            )

                            if success:
                                skills_ok += 1
                                if verbose:
                                    console.print(f"      [green]{prefixed_skill}[/green]")
                            else:
                                skills_failed += 1
                                if verbose:
                                    console.print(
                                        f"      [red]{original_skill}[/red] [dim](source not found)[/dim]"
                                    )

                # Update commands - iterate over CURRENT module commands, not old registry
                if global_module.commands:
                    command_dest = target.get_command_path(inst.project_path)
                    commands_dir = source_module / "commands"
                    for cmd_name in global_module.commands:
                        source = commands_dir / f"{cmd_name}.md"
                        success = target.generate_command(
                            source, command_dest, cmd_name, inst.module_name
                        )

                        if success:
                            commands_ok += 1
                            if verbose:
                                console.print(
                                    f"      [green]/{inst.module_name}-{cmd_name}[/green]"
                                )
                        else:
                            commands_failed += 1
                            if verbose:
                                console.print(
                                    f"      [red]{cmd_name}[/red] [dim](source not found)[/dim]"
                                )

                # Update agents
                if global_module.agents and target.supports_agents:
                    agent_dest = target.get_agent_path(inst.project_path)

                    if agent_dest:
                        agents_dir = source_module / "agents"
                        for agent_name in global_module.agents:
                            source = agents_dir / f"{agent_name}.md"
                            success = target.generate_agent(
                                source, agent_dest, agent_name, inst.module_name
                            )

                            if success:
                                agents_ok += 1
                                if verbose:
                                    console.print(
                                        f"      [green]@{inst.module_name}-{agent_name}[/green]"
                                    )
                            else:
                                agents_failed += 1
                                if verbose:
                                    console.print(
                                        f"      [red]{agent_name}[/red] [dim](source not found)[/dim]"
                                    )

                # Update the registry with current skills/commands/agents
                inst.skills = list(current_skills)
                inst.commands = list(current_commands)
                inst.agents = list(current_agents)
                registry.add(inst)

                # Print summary line for this installation
                parts = []
                if skills_ok > 0:
                    parts.append(f"{skills_ok} {('skill' if skills_ok == 1 else 'skills')}")
                if commands_ok > 0:
                    parts.append(
                        f"{commands_ok} {('command' if commands_ok == 1 else 'commands')}"
                    )
                if agents_ok > 0:
                    parts.append(f"{agents_ok} {('agent' if agents_ok == 1 else 'agents')}")

                summary = ", ".join(parts) if parts else "no items"

                # Build status indicators
                status_parts = []
                if skills_failed > 0 or commands_failed > 0 or agents_failed > 0:
                    status_parts.append(
                        f"[red]{skills_failed + commands_failed + agents_failed} failed[/red]"
                    )
                if orphans_removed > 0:
                    status_parts.append(f"[yellow]{orphans_removed} orphaned removed[/yellow]")

                status_suffix = f" ({', '.join(status_parts)})" if status_parts else ""

                console.print(
                    f"    [green]{inst.assistant}[/green] [dim]({summary}){status_suffix}[/dim]"
                )

    console.print()
    if stale_installations:
        console.print(
            f"[yellow]Found {len(stale_installations)} stale installation(s)[/yellow]"
        )
    console.print("[green]Update complete[/green]")


@click.command(name="list")
@click.option(
    "-a",
    "--assistant",
    type=click.Choice(list(TARGETS.keys())),
    default=None,
    help="Filter by AI assistant",
)
def list_installed_cmd(assistant: Optional[str]):
    """
    List all installed modules.

    Shows where each module's skills have been installed.
    """
    ensure_lola_dirs()

    registry = get_registry()
    installations = registry.all()

    if assistant:
        installations = [i for i in installations if i.assistant == assistant]

    if not installations:
        console.print("[yellow]No modules installed[/yellow]")
        console.print()
        console.print("[dim]Install modules with: lola install <module>[/dim]")
        return

    # Group by module name
    by_module = {}
    for inst in installations:
        if inst.module_name not in by_module:
            by_module[inst.module_name] = []
        by_module[inst.module_name].append(inst)

    # Pluralize correctly
    module_word = "module" if len(by_module) == 1 else "modules"
    console.print(f"\n[bold]Installed ({len(by_module)} {module_word})[/bold]")
    console.print()

    for mod_name, insts in by_module.items():
        console.print(f"[bold]{mod_name}[/bold]")

        # Group installations by (scope, path) to consolidate assistants
        by_scope_path = {}
        for inst in insts:
            key = (inst.scope, inst.project_path)
            if key not in by_scope_path:
                by_scope_path[key] = []
            by_scope_path[key].append(inst)

        for (scope, project_path), scope_insts in by_scope_path.items():
            # Collect all assistants for this scope/path
            assistants = sorted(set(inst.assistant for inst in scope_insts))
            assistants_str = ", ".join(assistants)

            console.print(f"- [dim]scope:[/dim] {scope}")
            if project_path:
                console.print(f'  [dim]path:[/dim] "{project_path}"')
            console.print(f"  [dim]assistants:[/dim] \\[{assistants_str}]")
        console.print()
