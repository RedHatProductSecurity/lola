"""
Install CLI commands.

Commands for installing, uninstalling, updating, and listing module installations.
"""

from dataclasses import dataclass, field
import shutil
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from lola.config import MODULES_DIR
from lola.models import Installation, Module
from lola.targets import (
    AssistantTarget,
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


# =============================================================================
# Update command helper types and functions
# =============================================================================


@dataclass
class UpdateResult:
    """Result of updating a single installation."""

    skills_ok: int = 0
    skills_failed: int = 0
    commands_ok: int = 0
    commands_failed: int = 0
    agents_ok: int = 0
    agents_failed: int = 0
    orphans_removed: int = 0
    error: str | None = None


@dataclass
class UpdateContext:
    """Context for update operations on a single installation."""

    inst: Installation
    global_module: Module
    source_module: Path
    target: AssistantTarget
    current_skills: set[str] = field(default_factory=set)
    current_commands: set[str] = field(default_factory=set)
    current_agents: set[str] = field(default_factory=set)
    orphaned_skills: set[str] = field(default_factory=set)
    orphaned_commands: set[str] = field(default_factory=set)
    orphaned_agents: set[str] = field(default_factory=set)


def _validate_installation_for_update(inst: Installation) -> tuple[bool, str | None]:
    """
    Validate that an installation can be updated.

    Returns (is_valid, error_message).
    """
    # Check if project path still exists for project-scoped installations
    if inst.scope == "project" and inst.project_path:
        if not Path(inst.project_path).exists():
            return False, "project path no longer exists"

    # For project scope, project_path is required
    if inst.scope == "project" and not inst.project_path:
        return False, "project scope requires project path"

    # Get the global module to refresh from
    global_module_path = MODULES_DIR / inst.module_name
    if not global_module_path.exists():
        return False, "module not found in registry"

    global_module = Module.from_path(global_module_path)
    if not global_module:
        return False, "invalid module"

    # Validate module structure and skill files
    is_valid, errors = global_module.validate()
    if not is_valid:
        return False, f"validation errors: {', '.join(errors)}"

    return True, None


def _build_update_context(inst: Installation) -> UpdateContext | None:
    """
    Build the context needed for updating an installation.

    Returns None if the installation cannot be updated.
    """
    global_module_path = MODULES_DIR / inst.module_name
    global_module = Module.from_path(global_module_path)
    if not global_module:
        return None

    local_modules = get_local_modules_path(inst.project_path)
    target = get_target(inst.assistant)

    # Refresh the local copy from global module
    source_module = copy_module_to_local(global_module, local_modules)

    # Compute current skills, commands, and agents from the module (with prefixes)
    current_skills = {f"{inst.module_name}-{s}" for s in global_module.skills}
    current_commands = set(global_module.commands)
    current_agents = set(global_module.agents)

    # Find orphaned items (in registry but not in module)
    orphaned_skills = set(inst.skills) - current_skills
    orphaned_commands = set(inst.commands) - current_commands
    orphaned_agents = set(inst.agents) - current_agents

    return UpdateContext(
        inst=inst,
        global_module=global_module,
        source_module=source_module,
        target=target,
        current_skills=current_skills,
        current_commands=current_commands,
        current_agents=current_agents,
        orphaned_skills=orphaned_skills,
        orphaned_commands=orphaned_commands,
        orphaned_agents=orphaned_agents,
    )


def _remove_orphaned_skills(
    ctx: UpdateContext, skill_dest: Path, verbose: bool
) -> int:
    """Remove orphaned skill files. Returns count of removed items."""
    if not ctx.orphaned_skills or ctx.target.uses_managed_section:
        return 0

    removed = 0
    for skill in ctx.orphaned_skills:
        if ctx.target.remove_skill(skill_dest, skill):
            removed += 1
            if verbose:
                console.print(f"      [yellow]- {skill}[/yellow] [dim](orphaned)[/dim]")
    return removed


def _remove_orphaned_commands(ctx: UpdateContext, verbose: bool) -> int:
    """Remove orphaned command files. Returns count of removed items."""
    if not ctx.orphaned_commands:
        return 0

    removed = 0
    command_dest = ctx.target.get_command_path(ctx.inst.project_path or "")
    for cmd_name in ctx.orphaned_commands:
        filename = ctx.target.get_command_filename(ctx.inst.module_name, cmd_name)
        orphan_file = command_dest / filename
        if orphan_file.exists():
            orphan_file.unlink()
            removed += 1
            if verbose:
                console.print(
                    f"      [yellow]- /{ctx.inst.module_name}-{cmd_name}[/yellow] [dim](orphaned)[/dim]"
                )
    return removed


def _remove_orphaned_agents(ctx: UpdateContext, verbose: bool) -> int:
    """Remove orphaned agent files. Returns count of removed items."""
    if not ctx.orphaned_agents:
        return 0

    agent_dest = ctx.target.get_agent_path(ctx.inst.project_path or "")
    if not agent_dest:
        return 0

    removed = 0
    for agent_name in ctx.orphaned_agents:
        filename = ctx.target.get_agent_filename(ctx.inst.module_name, agent_name)
        orphan_file = agent_dest / filename
        if orphan_file.exists():
            orphan_file.unlink()
            removed += 1
            if verbose:
                console.print(
                    f"      [yellow]- @{ctx.inst.module_name}-{agent_name}[/yellow] [dim](orphaned)[/dim]"
                )
    return removed


def _update_skills(
    ctx: UpdateContext, skill_dest: Path, verbose: bool
) -> tuple[int, int]:
    """
    Update skills for an installation.

    Returns (success_count, failed_count).
    """
    if not ctx.global_module.skills:
        return 0, 0

    skills_ok = 0
    skills_failed = 0

    if ctx.target.uses_managed_section:
        # Managed section targets: Update entries in GEMINI.md/AGENTS.md
        batch_skills = []
        for original_skill in ctx.global_module.skills:
            prefixed_skill = f"{ctx.inst.module_name}-{original_skill}"
            source = _skill_source_dir(ctx.source_module, original_skill)
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
            ctx.target.generate_skills_batch(
                skill_dest,
                ctx.inst.module_name,
                batch_skills,
                ctx.inst.project_path,
            )
    else:
        for original_skill in ctx.global_module.skills:
            prefixed_skill = f"{ctx.inst.module_name}-{original_skill}"
            source = _skill_source_dir(ctx.source_module, original_skill)

            success = ctx.target.generate_skill(
                source, skill_dest, prefixed_skill, ctx.inst.project_path
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

    return skills_ok, skills_failed


def _update_commands(ctx: UpdateContext, verbose: bool) -> tuple[int, int]:
    """
    Update commands for an installation.

    Returns (success_count, failed_count).
    """
    if not ctx.global_module.commands:
        return 0, 0

    commands_ok = 0
    commands_failed = 0

    command_dest = ctx.target.get_command_path(ctx.inst.project_path or "")
    commands_dir = ctx.source_module / "commands"

    for cmd_name in ctx.global_module.commands:
        source = commands_dir / f"{cmd_name}.md"
        success = ctx.target.generate_command(
            source, command_dest, cmd_name, ctx.inst.module_name
        )

        if success:
            commands_ok += 1
            if verbose:
                console.print(f"      [green]/{ctx.inst.module_name}-{cmd_name}[/green]")
        else:
            commands_failed += 1
            if verbose:
                console.print(
                    f"      [red]{cmd_name}[/red] [dim](source not found)[/dim]"
                )

    return commands_ok, commands_failed


def _update_agents(ctx: UpdateContext, verbose: bool) -> tuple[int, int]:
    """
    Update agents for an installation.

    Returns (success_count, failed_count).
    """
    if not ctx.global_module.agents or not ctx.target.supports_agents:
        return 0, 0

    agent_dest = ctx.target.get_agent_path(ctx.inst.project_path or "")
    if not agent_dest:
        return 0, 0

    agents_ok = 0
    agents_failed = 0

    agents_dir = ctx.source_module / "agents"
    for agent_name in ctx.global_module.agents:
        source = agents_dir / f"{agent_name}.md"
        success = ctx.target.generate_agent(
            source, agent_dest, agent_name, ctx.inst.module_name
        )

        if success:
            agents_ok += 1
            if verbose:
                console.print(f"      [green]@{ctx.inst.module_name}-{agent_name}[/green]")
        else:
            agents_failed += 1
            if verbose:
                console.print(
                    f"      [red]{agent_name}[/red] [dim](source not found)[/dim]"
                )

    return agents_ok, agents_failed


def _process_single_installation(
    ctx: UpdateContext, verbose: bool
) -> UpdateResult:
    """
    Process a single installation update.

    Removes orphaned items and regenerates all skills, commands, and agents.
    """
    result = UpdateResult()
    skill_dest = ctx.target.get_skill_path(ctx.inst.project_path or "")

    # Remove orphaned items
    result.orphans_removed += _remove_orphaned_skills(ctx, skill_dest, verbose)
    result.orphans_removed += _remove_orphaned_commands(ctx, verbose)
    result.orphans_removed += _remove_orphaned_agents(ctx, verbose)

    # Update skills
    result.skills_ok, result.skills_failed = _update_skills(ctx, skill_dest, verbose)

    # Update commands
    result.commands_ok, result.commands_failed = _update_commands(ctx, verbose)

    # Update agents
    result.agents_ok, result.agents_failed = _update_agents(ctx, verbose)

    return result


def _format_update_summary(result: UpdateResult) -> str:
    """Format the summary string for an update result."""
    parts = []
    if result.skills_ok > 0:
        parts.append(f"{result.skills_ok} {'skill' if result.skills_ok == 1 else 'skills'}")
    if result.commands_ok > 0:
        parts.append(
            f"{result.commands_ok} {'command' if result.commands_ok == 1 else 'commands'}"
        )
    if result.agents_ok > 0:
        parts.append(f"{result.agents_ok} {'agent' if result.agents_ok == 1 else 'agents'}")

    summary = ", ".join(parts) if parts else "no items"

    # Build status indicators
    status_parts = []
    total_failed = result.skills_failed + result.commands_failed + result.agents_failed
    if total_failed > 0:
        status_parts.append(f"[red]{total_failed} failed[/red]")
    if result.orphans_removed > 0:
        status_parts.append(f"[yellow]{result.orphans_removed} orphaned removed[/yellow]")

    status_suffix = f" ({', '.join(status_parts)})" if status_parts else ""

    return f"({summary}){status_suffix}"


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
    by_module: dict[str, list[Installation]] = {}
    for inst in installations:
        if inst.module_name not in by_module:
            by_module[inst.module_name] = []
        by_module[inst.module_name].append(inst)

    module_word = "module" if len(by_module) == 1 else "modules"
    console.print(f"\n[bold]Updating {len(by_module)} {module_word}[/bold]")
    console.print()

    stale_installations: list[Installation] = []

    for mod_name, mod_installations in by_module.items():
        console.print(f"[bold]{mod_name}[/bold]")

        # Group by (scope, path) for display
        by_scope_path: dict[tuple[str, str | None], list[Installation]] = {}
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
                # Validate installation
                is_valid, error_msg = _validate_installation_for_update(inst)
                if not is_valid:
                    console.print(f"    [red]{inst.assistant}: {error_msg}[/red]")
                    if error_msg == "project path no longer exists":
                        stale_installations.append(inst)
                    continue

                # Build context for update
                ctx = _build_update_context(inst)
                if not ctx:
                    console.print(f"    [red]{inst.assistant}: failed to build context[/red]")
                    continue

                # Process the installation update
                result = _process_single_installation(ctx, verbose)

                # Update the registry with current skills/commands/agents
                inst.skills = list(ctx.current_skills)
                inst.commands = list(ctx.current_commands)
                inst.agents = list(ctx.current_agents)
                registry.add(inst)

                # Print summary line for this installation
                summary = _format_update_summary(result)
                console.print(f"    [green]{inst.assistant}[/green] [dim]{summary}[/dim]")

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
