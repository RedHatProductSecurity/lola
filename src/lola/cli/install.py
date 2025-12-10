"""
Install CLI commands.

Commands for installing, uninstalling, updating, and listing module installations.
"""

import shutil
from pathlib import Path
from typing import Optional

import click

from lola.config import (
    ASSISTANTS,
    MODULES_DIR,
    get_assistant_command_path,
    get_assistant_skill_path,
)
from lola.command_converters import get_command_filename
from lola.core.installer import (
    copy_module_to_local,
    get_registry,
    install_to_assistant,
)
from lola.core.generator import (
    generate_claude_skill,
    generate_cursor_rule,
    generate_claude_command,
    generate_cursor_command,
    generate_gemini_command,
    get_skill_description,
    remove_gemini_skills,
    update_gemini_md,
)
from lola.layout import console
from lola.models import Module
from lola.utils import ensure_lola_dirs, get_local_modules_path


@click.command(name='install')
@click.argument('module_name')
@click.option(
    '-a', '--assistant',
    type=click.Choice(list(ASSISTANTS.keys())),
    default=None,
    help='AI assistant to install skills for (default: all)'
)
@click.option(
    '-s', '--scope',
    type=click.Choice(['user', 'project']),
    default='user',
    help='Installation scope (user or project)'
)
@click.argument('project_path', required=False, default=None)
def install_cmd(module_name: str, assistant: Optional[str], scope: str, project_path: Optional[str]):
    """
    Install a module's skills to AI assistants.

    If no assistant is specified, installs to all assistants.

    \b
    Examples:
        lola install my-module                              # All assistants
        lola install my-module -a claude-code               # Specific assistant
        lola install my-module -s project ./my-project      # Project scope
    """
    ensure_lola_dirs()

    # Validate project path for project scope
    if scope == 'project':
        if not project_path:
            console.print("[red]Project path required for project scope[/red]")
            console.print("Usage: lola install <module> -s project <path/to/project>")
            raise SystemExit(1)

        project_path = str(Path(project_path).resolve())
        if not Path(project_path).exists():
            console.print(f"[red]Project path does not exist: {project_path}[/red]")
            raise SystemExit(1)

    # Find module in global registry
    module_path = MODULES_DIR / module_name
    if not module_path.exists():
        console.print(f"[red]Module '{module_name}' not found in registry[/red]")
        console.print("Use 'lola mod ls' to see available modules")
        console.print("Use 'lola mod add <source>' to add a module")
        raise SystemExit(1)

    module = Module.from_path(module_path)
    if not module:
        console.print(f"[red]Invalid module: no .lola/module.yml found[/red]")
        raise SystemExit(1)

    # Validate module structure and skill files
    is_valid, errors = module.validate()
    if not is_valid:
        console.print(f"[red]Module '{module_name}' has validation errors:[/red]")
        for err in errors:
            console.print(f"  [red]- {err}[/red]")
        raise SystemExit(1)

    if not module.skills and not module.commands:
        console.print(f"[yellow]Module '{module_name}' has no skills or commands defined[/yellow]")
        return

    # Get paths and registry
    local_modules = get_local_modules_path(project_path)
    registry = get_registry()

    # Determine which assistants to install to
    assistants_to_install = [assistant] if assistant else list(ASSISTANTS.keys())

    console.print(f"[bold]Installing '{module_name}'[/bold]")
    console.print(f"  Scope: {scope}")
    if project_path:
        console.print(f"  Project: {project_path}")
    console.print()

    total_installed = 0
    for asst in assistants_to_install:
        total_installed += install_to_assistant(
            module, asst, scope, project_path, local_modules, registry
        )
        console.print()

    console.print(f"[bold green]Installed to {len(assistants_to_install)} assistant(s)[/bold green]")


@click.command(name='uninstall')
@click.argument('module_name')
@click.option(
    '-a', '--assistant',
    type=click.Choice(list(ASSISTANTS.keys())),
    default=None,
    help='AI assistant to uninstall from (optional)'
)
@click.option(
    '-s', '--scope',
    type=click.Choice(['user', 'project']),
    default=None,
    help='Installation scope (optional)'
)
@click.argument('project_path', required=False, default=None)
@click.option(
    '-f', '--force',
    is_flag=True,
    help='Force uninstall without confirmation'
)
def uninstall_cmd(module_name: str, assistant: Optional[str], scope: Optional[str],
                  project_path: Optional[str], force: bool):
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
        console.print(f"[yellow]No matching installations found[/yellow]")
        return

    # Show what will be uninstalled
    console.print(f"[bold]Found {len(installations)} installation(s) of '{module_name}':[/bold]")
    console.print()

    for inst in installations:
        console.print(f"  - {inst.assistant} ({inst.scope})")
        if inst.project_path:
            console.print(f"    Project: {inst.project_path}")
        if inst.skills:
            console.print(f"    Skills: {', '.join(inst.skills)}")
        if inst.commands:
            console.print(f"    Commands: {', '.join(inst.commands)}")

    console.print()

    # Confirm if multiple installations and not forced
    if len(installations) > 1 and not force:
        console.print("[yellow]Multiple installations found.[/yellow]")
        console.print("Use -a <assistant> and -s <scope> to target specific installation,")
        console.print("or use -f/--force to uninstall all.")

        if not click.confirm("Uninstall all?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Uninstall each
    for inst in installations:
        # Remove skill files
        if inst.skills:
            try:
                skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
            except ValueError:
                console.print(f"[red]Cannot determine skill path for {inst.assistant}/{inst.scope}[/red]")
                skill_dest = None

            if skill_dest:
                if inst.assistant == 'gemini-cli':
                    # Remove entries from GEMINI.md
                    if remove_gemini_skills(skill_dest, module_name):
                        console.print(f"[green]Removed skills from: {skill_dest}[/green]")
                elif inst.assistant == 'cursor':
                    # Remove .mdc files
                    for skill_name in inst.skills:
                        mdc_file = skill_dest / f'{skill_name}.mdc'
                        if mdc_file.exists():
                            mdc_file.unlink()
                            console.print(f"[green]Removed: {mdc_file}[/green]")
                else:
                    # Remove skill directories (claude-code)
                    for skill_name in inst.skills:
                        skill_dir = skill_dest / skill_name
                        if skill_dir.exists():
                            shutil.rmtree(skill_dir)
                            console.print(f"[green]Removed: {skill_dir}[/green]")

        # Remove command files
        if inst.commands:
            try:
                command_dest = get_assistant_command_path(inst.assistant, inst.scope, inst.project_path)
            except ValueError:
                console.print(f"[red]Cannot determine command path for {inst.assistant}/{inst.scope}[/red]")
                command_dest = None

            if command_dest:
                for cmd_name in inst.commands:
                    filename = get_command_filename(inst.assistant, module_name, cmd_name)
                    cmd_file = command_dest / filename
                    if cmd_file.exists():
                        cmd_file.unlink()
                        console.print(f"[green]Removed: {cmd_file}[/green]")

        # For project scope, also remove the project-local module copy
        if inst.scope == 'project' and inst.project_path:
            local_modules = get_local_modules_path(inst.project_path)
            source_module = local_modules / module_name
            if source_module.is_symlink():
                source_module.unlink()
                console.print(f"[green]Removed symlink: {source_module}[/green]")
            elif source_module.exists():
                # Handle legacy copies
                shutil.rmtree(source_module)
                console.print(f"[green]Removed: {source_module}[/green]")

        # Remove from registry
        registry.remove(
            module_name,
            assistant=inst.assistant,
            scope=inst.scope,
            project_path=inst.project_path
        )

    console.print()
    console.print(f"[bold green]Uninstalled '{module_name}'[/bold green]")


@click.command(name='update')
@click.argument('module_name', required=False, default=None)
@click.option(
    '-a', '--assistant',
    type=click.Choice(list(ASSISTANTS.keys())),
    default=None,
    help='Filter by AI assistant'
)
def update_cmd(module_name: Optional[str], assistant: Optional[str]):
    """
    Regenerate assistant files from source in .lola/modules/.

    Use this after modifying skills in .lola/modules/ to update the
    generated files for all assistants.

    \b
    Examples:
        lola update                    # Update all modules
        lola update my-module          # Update specific module
        lola update -a cursor          # Update only Cursor files
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

    console.print(f"[bold]Updating {len(installations)} installation(s)...[/bold]")
    console.print()

    # Track stale installations to remove
    stale_installations = []

    for inst in installations:
        # Check if project path still exists for project-scoped installations
        if inst.scope == 'project' and inst.project_path:
            if not Path(inst.project_path).exists():
                console.print(f"[red]{inst.module_name}[/red] ({inst.assistant})")
                console.print(f"  [red]Project path no longer exists: {inst.project_path}[/red]")
                console.print(f"  [dim]Run 'lola uninstall {inst.module_name}' to remove this stale entry[/dim]")
                stale_installations.append(inst)
                continue

        # Get the global module to refresh from
        global_module_path = MODULES_DIR / inst.module_name
        if not global_module_path.exists():
            console.print(f"[red]{inst.module_name}: not found in registry[/red]")
            console.print(f"  [dim]Run 'lola mod add <source>' to re-add, or 'lola uninstall {inst.module_name}' to remove[/dim]")
            continue

        global_module = Module.from_path(global_module_path)
        if not global_module:
            console.print(f"[red]{inst.module_name}: invalid module (no .lola/module.yml)[/red]")
            continue

        # Validate module structure and skill files
        is_valid, errors = global_module.validate()
        if not is_valid:
            console.print(f"[red]{inst.module_name}[/red] ({inst.assistant})")
            console.print(f"  [red]Module has validation errors:[/red]")
            for err in errors:
                console.print(f"    [red]- {err}[/red]")
            continue

        local_modules = get_local_modules_path(inst.project_path)

        # Refresh the local copy from global module
        source_module = copy_module_to_local(global_module, local_modules)

        try:
            skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
        except ValueError:
            console.print(f"[red]Cannot determine path for {inst.assistant}/{inst.scope}[/red]")
            continue

        console.print(f"[cyan]{inst.module_name}[/cyan] -> {inst.assistant}")
        console.print(f"  [dim]Local path: {source_module}[/dim]")

        # Update skills
        if inst.skills:
            try:
                skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
            except ValueError:
                console.print(f"  [red]Cannot determine skill path[/red]")
                skill_dest = None

            if skill_dest:
                if inst.assistant == 'gemini-cli':
                    # Gemini: Update entries in GEMINI.md
                    gemini_skills = []
                    for prefixed_skill in inst.skills:
                        # Extract original skill name by removing module prefix
                        prefix = f"{inst.module_name}-"
                        if prefixed_skill.startswith(prefix):
                            original_skill = prefixed_skill[len(prefix):]
                        else:
                            original_skill = prefixed_skill  # Fallback for old records

                        source = source_module / original_skill
                        if source.exists():
                            description = get_skill_description(source)
                            gemini_skills.append((original_skill, description, source))
                            console.print(f"  [green]{prefixed_skill}[/green]")
                        else:
                            console.print(f"  [red]{original_skill}[/red] (source not found)")
                    if gemini_skills:
                        update_gemini_md(skill_dest, inst.module_name, gemini_skills, inst.project_path)
                else:
                    for prefixed_skill in inst.skills:
                        # Extract original skill name by removing module prefix
                        prefix = f"{inst.module_name}-"
                        if prefixed_skill.startswith(prefix):
                            original_skill = prefixed_skill[len(prefix):]
                        else:
                            original_skill = prefixed_skill  # Fallback for old records

                        source = source_module / original_skill

                        if inst.assistant == 'cursor':
                            success = generate_cursor_rule(source, skill_dest, prefixed_skill, inst.project_path)
                        else:
                            dest = skill_dest / prefixed_skill
                            success = generate_claude_skill(source, dest)

                        if success:
                            console.print(f"  [green]{prefixed_skill}[/green]")
                        else:
                            console.print(f"  [red]{original_skill}[/red] (source not found)")

        # Update commands
        if inst.commands:
            try:
                command_dest = get_assistant_command_path(inst.assistant, inst.scope, inst.project_path)
            except ValueError:
                console.print(f"  [red]Cannot determine command path[/red]")
                command_dest = None

            if command_dest:
                commands_dir = source_module / 'commands'
                for cmd_name in inst.commands:
                    source = commands_dir / f'{cmd_name}.md'

                    if inst.assistant == 'gemini-cli':
                        success = generate_gemini_command(source, command_dest, cmd_name, inst.module_name)
                    elif inst.assistant == 'cursor':
                        success = generate_cursor_command(source, command_dest, cmd_name, inst.module_name)
                    else:
                        success = generate_claude_command(source, command_dest, cmd_name, inst.module_name)

                    if success:
                        console.print(f"  [green]/{inst.module_name}-{cmd_name}[/green]")
                    else:
                        console.print(f"  [red]{cmd_name}[/red] (source not found)")

    console.print()
    if stale_installations:
        console.print(f"[yellow]Found {len(stale_installations)} stale installation(s)[/yellow]")
    console.print("[bold green]Update complete[/bold green]")


@click.command(name='list')
@click.option(
    '-a', '--assistant',
    type=click.Choice(list(ASSISTANTS.keys())),
    default=None,
    help='Filter by AI assistant'
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
        console.print("Install modules with:")
        console.print("  lola install <module>")
        return

    # Group by module name
    by_module = {}
    for inst in installations:
        if inst.module_name not in by_module:
            by_module[inst.module_name] = []
        by_module[inst.module_name].append(inst)

    console.print(f"[bold]Installed modules ({len(by_module)}):[/bold]")
    console.print()

    for mod_name, insts in by_module.items():
        console.print(f"[cyan]{mod_name}[/cyan]")
        for inst in insts:
            scope_str = f"{inst.assistant}/{inst.scope}"
            if inst.project_path:
                scope_str += f" ({inst.project_path})"
            console.print(f"  - {scope_str}")
            if inst.skills:
                console.print(f"    Skills: {', '.join(inst.skills)}")
            if inst.commands:
                console.print(f"    Commands: {', '.join(inst.commands)}")
        console.print()
