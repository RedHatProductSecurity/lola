"""
Module management CLI commands.

Commands for adding, removing, and managing lola modules.
"""

import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.tree import Tree

from lola.config import MODULES_DIR, INSTALLED_FILE
from lola.models import Module, InstallationRegistry
from lola.targets import GeminiTarget, get_target
from lola.parsers import (
    fetch_module,
    detect_source_type,
    save_source_info,
    load_source_info,
    update_module,
    validate_module_name,
)
from lola.utils import ensure_lola_dirs, get_local_modules_path

console = Console()


def list_registered_modules() -> list[Module]:
    """
    List all modules registered in the lola modules directory.

    Returns:
        List of Module objects
    """
    ensure_lola_dirs()

    modules = []
    if not MODULES_DIR.exists():
        return modules

    for item in MODULES_DIR.iterdir():
        if item.is_dir():
            module = Module.from_path(item)
            if module:
                modules.append(module)

    return sorted(modules, key=lambda m: m.name)


def _count_str(count: int, singular: str) -> str:
    """Format count with singular/plural form."""
    return f"{count} {singular}" if count == 1 else f"{count} {singular}s"


def _module_tree(
    name: str,
    skills: list[str] | None = None,
    commands: list[str] | None = None,
    agents: list[str] | None = None,
) -> None:
    """Print a module structure as a tree."""
    tree = Tree(f"[cyan]{name}/[/cyan]")

    if skills:
        for skill in skills:
            skill_node = tree.add(f"[green]{skill}/[/green]")
            skill_node.add("[dim]SKILL.md[/dim]")

    if commands:
        cmd_node = tree.add("[dim]commands/[/dim]")
        for cmd in commands:
            cmd_node.add(f"[dim]{cmd}.md[/dim]")

    if agents:
        agent_node = tree.add("[dim]agents/[/dim]")
        for agent in agents:
            agent_node.add(f"[dim]{agent}.md[/dim]")

    console.print(tree)


@click.group(name="mod")
def mod():
    """
    Manage lola modules.

    Add, remove, and list modules in your lola registry.
    """
    pass


@mod.command(name="add")
@click.argument("source")
@click.option(
    "-n", "--name", "module_name", default=None, help="Override the module name"
)
def add_module(source: str, module_name: str):
    """
    Add a module to the lola registry.

    \b
    SOURCE can be:
      - A git repository URL (https://github.com/user/repo.git)
      - A URL to a zip file (https://example.com/module.zip)
      - A URL to a tar file (https://example.com/module.tar.gz)
      - A path to a local zip file (/path/to/module.zip)
      - A path to a local tar file (/path/to/module.tar.gz)
      - A path to a local folder (/path/to/module)

    \b
    Examples:
        lola mod add https://github.com/user/my-skills.git
        lola mod add https://github.com/user/repo/archive/main.zip
        lola mod add https://example.com/skills.tar.gz
        lola mod add ./my-local-module
        lola mod add ~/Downloads/skills.zip
    """
    ensure_lola_dirs()

    source_type = detect_source_type(source)
    if source_type == "unknown":
        console.print(f"[red]Cannot determine source type for: {source}[/red]")
        console.print(
            "[dim]Supported: git repos, .zip files, .tar/.tar.gz files, or local folders[/dim]"
        )
        raise SystemExit(1)

    console.print(f"Adding module from {source_type}...")

    try:
        module_path = fetch_module(source, MODULES_DIR)
        # Save source info for future updates
        save_source_info(module_path, source, source_type)
    except Exception as e:
        console.print(f"[red]Failed to fetch module: {e}[/red]")
        raise SystemExit(1)

    # Rename if name override provided
    if module_name and module_path.name != module_name:
        # Validate the provided module name to prevent directory traversal
        try:
            module_name = validate_module_name(module_name)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            # Clean up the fetched module
            if module_path.exists():
                shutil.rmtree(module_path)
            raise SystemExit(1)

        new_path = MODULES_DIR / module_name
        if new_path.exists():
            shutil.rmtree(new_path)
        module_path.rename(new_path)
        module_path = new_path

    # Validate module structure
    module = Module.from_path(module_path)
    if not module:
        console.print("[yellow]No skills or commands found[/yellow]")
        console.print(f"  [dim]Path:[/dim] {module_path}")
        console.print(
            "[dim]Add skill folders with SKILL.md or commands/*.md files[/dim]"
        )
        return

    is_valid, errors = module.validate()
    if not is_valid:
        console.print("[yellow]Module has validation issues:[/yellow]")
        for err in errors:
            console.print(f"  {err}")

    console.print()
    console.print(f"[green]Added {module.name}[/green]")
    console.print(f"  [dim]Path:[/dim] {module_path}")
    console.print(f"  [dim]Skills:[/dim] {len(module.skills)}")
    console.print(f"  [dim]Commands:[/dim] {len(module.commands)}")
    console.print(f"  [dim]Agents:[/dim] {len(module.agents)}")

    if module.skills:
        console.print()
        console.print("[bold]Skills[/bold]")
        for skill in module.skills:
            console.print(f"  {skill}")

    if module.commands:
        console.print()
        console.print("[bold]Commands[/bold]")
        for cmd in module.commands:
            console.print(f"  /{module.name}-{cmd}")

    if module.agents:
        console.print()
        console.print("[bold]Agents[/bold]")
        for agent in module.agents:
            console.print(f"  @{module.name}-{agent}")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. lola install {module.name} -a <assistant> -s <scope>")


@mod.command(name="init")
@click.argument("name", required=False, default=None)
@click.option(
    "-s",
    "--skill",
    "skill_name",
    default="example-skill",
    help="Name for the initial skill",
)
@click.option("--no-skill", is_flag=True, help="Do not create an initial skill")
@click.option(
    "-c",
    "--command",
    "command_name",
    default="example-command",
    help="Name for an initial slash command",
)
@click.option("--no-command", is_flag=True, help="Do not create an initial command")
@click.option(
    "-g",
    "--agent",
    "agent_name",
    default=None,
    help="Name for an initial agent",
)
@click.option("--no-agent", is_flag=True, help="Do not create an initial agent")
def init_module(
    name: str | None,
    skill_name: str,
    no_skill: bool,
    command_name: str,
    no_command: bool,
    agent_name: str | None,
    no_agent: bool,
):
    """
    Initialize a new lola module.

    Creates a module folder structure with skills, commands, and agents that are
    auto-discovered. Skills are folders containing SKILL.md files, commands are
    .md files in the commands/ folder, and agents are .md files in the agents/ folder.

    \b
    Examples:
        lola mod init                           # Use current folder name
        lola mod init my-skills                 # Create my-skills/ subdirectory
        lola mod init -s code-review            # Custom skill name
        lola mod init --no-skill                # Skip initial skill
        lola mod init -c review-pr              # Custom command name
        lola mod init --no-command              # Skip initial command
        lola mod init -g my-agent               # Add an initial agent
    """
    if name:
        # Create a new subdirectory
        module_dir = Path.cwd() / name
        if module_dir.exists():
            console.print(f"[red]Directory already exists: {module_dir}[/red]")
            raise SystemExit(1)
        module_dir.mkdir(parents=True)
        module_name = name
    else:
        # Use current directory
        module_dir = Path.cwd()
        module_name = module_dir.name

    # Apply --no-skill and --no-command flags
    final_skill_name: str | None = None if no_skill else skill_name
    final_command_name: str | None = None if no_command else command_name

    # Create initial skill if requested
    if final_skill_name:
        skill_dir = module_dir / final_skill_name
        if skill_dir.exists():
            console.print(f"[red]Skill directory already exists: {skill_dir}[/red]")
            raise SystemExit(1)
        skill_dir.mkdir()

        skill_content = f"""---
name: {final_skill_name}
description: Description of what this skill does and when to use it.
---

# {final_skill_name.replace('-', ' ').title()} Skill

Describe the skill's purpose and capabilities here.

## Usage

Explain how to use this skill.

## Examples

Provide examples of the skill in action.
"""
        (skill_dir / "SKILL.md").write_text(skill_content)

    # Create initial command if requested
    if final_command_name:
        commands_dir = module_dir / "commands"
        commands_dir.mkdir(exist_ok=True)

        command_content = f"""---
description: Description of what this command does
argument-hint: "[optional args]"
---

Prompt instructions for the {final_command_name} command.

Use $ARGUMENTS to reference any arguments passed to the command.
"""
        (commands_dir / f"{final_command_name}.md").write_text(command_content)

    # Apply --no-agent flag
    final_agent_name: str | None = None if no_agent else agent_name

    # Create initial agent if requested
    if final_agent_name:
        agents_dir = module_dir / "agents"
        agents_dir.mkdir(exist_ok=True)

        agent_content = f"""---
description: Description of what this agent does and when to use it
---

Instructions for the {final_agent_name.replace('-', ' ').title()} agent.

Describe the agent's purpose, capabilities, and guidelines here.
"""
        (agents_dir / f"{final_agent_name}.md").write_text(agent_content)

    console.print(f"[green]Initialized module {module_name}[/green]")
    console.print(f"  [dim]Path:[/dim] {module_dir}")

    console.print()
    console.print("[bold]Structure[/bold]")
    _module_tree(
        module_name,
        skills=[final_skill_name] if final_skill_name else None,
        commands=[final_command_name] if final_command_name else None,
        agents=[final_agent_name] if final_agent_name else None,
    )

    steps = []
    if final_skill_name:
        steps.append(f"Edit {final_skill_name}/SKILL.md with your skill content")
    if final_command_name:
        steps.append(f"Edit commands/{final_command_name}.md with your command prompt")
    if final_agent_name:
        steps.append(f"Edit agents/{final_agent_name}.md with your agent instructions")
    if not final_skill_name and not final_command_name and not final_agent_name:
        steps.append("Create skill directories with SKILL.md files")
        steps.append("Create commands/ directory with .md files for slash commands")
        steps.append("Create agents/ directory with .md files for agents")
    steps.append(f"lola mod add {module_dir}")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i}. {step}")


@mod.command(name="rm")
@click.argument("module_name")
@click.option("-f", "--force", is_flag=True, help="Force removal without confirmation")
def remove_module(module_name: str, force: bool):
    """
    Remove a module from the lola registry.

    This also uninstalls the module from all AI assistants and removes
    generated skill files.
    """
    ensure_lola_dirs()

    module_path = MODULES_DIR / module_name

    if not module_path.exists():
        console.print(f"[red]Module '{module_name}' not found[/red]")
        console.print("[dim]Use 'lola mod ls' to see available modules[/dim]")
        raise SystemExit(1)

    # Check for installations
    registry = InstallationRegistry(INSTALLED_FILE)
    installations = registry.find(module_name)

    if not force:
        console.print(f"Remove module [cyan]{module_name}[/cyan] from registry?")
        console.print(f"  [dim]Path:[/dim] {module_path}")
        if installations:
            console.print()
            console.print(
                f"[yellow]Will also uninstall from {len(installations)} location(s):[/yellow]"
            )
            for inst in installations:
                loc = f"{inst.assistant}/{inst.scope}"
                if inst.project_path:
                    loc += f" ({inst.project_path})"
                console.print(f"  {loc}")
        console.print()
        if not click.confirm("Continue?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Uninstall from all locations
    for inst in installations:
        if not inst.project_path:
            continue

        target = get_target(inst.assistant)
        skill_dest = target.get_skill_path(inst.project_path)

        # Remove generated skill files
        if isinstance(target, GeminiTarget):
            # Remove module section from GEMINI.md
            if target.remove_skill(skill_dest, module_name):
                console.print(f"  [dim]Removed from: {skill_dest}[/dim]")
        else:
            for skill in inst.skills:
                if target.remove_skill(skill_dest, skill):
                    console.print(f"  [dim]Removed: {skill}[/dim]")

        # Remove source files from project .lola/modules/ if applicable
        if inst.project_path:
            local_modules = get_local_modules_path(inst.project_path)
            source_module = local_modules / module_name
            if source_module.exists():
                shutil.rmtree(source_module)
                console.print(f"  [dim]Removed source: {source_module}[/dim]")

        # Remove from registry
        registry.remove(
            module_name,
            assistant=inst.assistant,
            scope=inst.scope,
            project_path=inst.project_path,
        )

    # Remove from global registry
    shutil.rmtree(module_path)
    console.print(f"[green]Removed {module_name}[/green]")


@mod.command(name="ls")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed module information")
def list_modules(verbose: bool):
    """
    List modules in the lola registry.

    Shows all modules that have been added with 'lola mod add'.
    """
    ensure_lola_dirs()

    modules = list_registered_modules()

    if not modules:
        console.print("[yellow]No modules found[/yellow]")
        console.print()
        console.print(
            "[dim]Add modules with: lola mod add <git-url|zip-file|tar-file|folder>[/dim]"
        )
        return

    console.print(f"\n[bold]Modules ({len(modules)})[/bold]")
    console.print()

    for module in modules:
        console.print(f"[cyan]{module.name}[/cyan]")

        skills_str = _count_str(len(module.skills), "skill")
        cmds_str = _count_str(len(module.commands), "command")
        agents_str = _count_str(len(module.agents), "agent")
        console.print(f"  [dim]{skills_str}, {cmds_str}, {agents_str}[/dim]")

        if verbose:
            if module.skills:
                console.print("  [bold]Skills:[/bold]")
                for skill in module.skills:
                    console.print(f"    {skill}")
            if module.commands:
                console.print("  [bold]Commands:[/bold]")
                for cmd in module.commands:
                    console.print(f"    /{module.name}-{cmd}")
            if module.agents:
                console.print("  [bold]Agents:[/bold]")
                for agent in module.agents:
                    console.print(f"    @{module.name}-{agent}")

        console.print()


@mod.command(name="info")
@click.argument("module_name")
def module_info(module_name: str):
    """
    Show detailed information about a module.
    """
    ensure_lola_dirs()

    module_path = MODULES_DIR / module_name
    if not module_path.exists():
        console.print(f"[red]Module '{module_name}' not found[/red]")
        raise SystemExit(1)

    module = Module.from_path(module_path)
    if not module:
        console.print(
            f"[yellow]No skills or commands found in '{module_name}'[/yellow]"
        )
        console.print(f"  [dim]Path:[/dim] {module_path}")
        return

    console.print(f"[bold cyan]{module.name}[/bold cyan]")
    console.print()
    console.print(f"  [dim]Path:[/dim] {module.path}")

    console.print()
    console.print("[bold]Skills[/bold]")

    if not module.skills:
        console.print("  [dim](none)[/dim]")
    else:
        from lola.frontmatter import parse_file

        for skill_rel, skill_path in zip(module.skills, module.get_skill_paths()):
            if skill_path.exists():
                console.print(f"  [green]{skill_rel}[/green]")
                skill_file = skill_path / "SKILL.md"
                if skill_file.exists():
                    # Show description from frontmatter
                    frontmatter, _ = parse_file(skill_file)
                    desc = frontmatter.get("description", "")
                    if desc:
                        console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                console.print(f"  [red]{skill_rel}[/red] [dim](not found)[/dim]")

    console.print()
    console.print("[bold]Commands[/bold]")

    if not module.commands:
        console.print("  [dim](none)[/dim]")
    else:
        from lola.frontmatter import parse_file as fm_parse_file

        commands_dir = module.path / "commands"
        for cmd_name in module.commands:
            cmd_path = commands_dir / f"{cmd_name}.md"
            if cmd_path.exists():
                console.print(f"  [green]/{module.name}-{cmd_name}[/green]")
                # Show description from frontmatter
                frontmatter, _ = fm_parse_file(cmd_path)
                desc = frontmatter.get("description", "")
                if desc:
                    console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                console.print(f"  [red]{cmd_name}[/red] [dim](not found)[/dim]")

    console.print()
    console.print("[bold]Agents[/bold]")

    if not module.agents:
        console.print("  [dim](none)[/dim]")
    else:
        from lola.frontmatter import parse_file as fm_parse_file

        agents_dir = module.path / "agents"
        for agent_name in module.agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if agent_path.exists():
                console.print(f"  [green]@{module.name}-{agent_name}[/green]")
                # Show description from frontmatter
                frontmatter, _ = fm_parse_file(agent_path)
                desc = frontmatter.get("description", "")
                if desc:
                    console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                console.print(f"  [red]{agent_name}[/red] [dim](not found)[/dim]")

    # Source info
    source_info = load_source_info(module.path)
    if source_info:
        console.print()
        console.print("[bold]Source[/bold]")
        console.print(f"  [dim]Type:[/dim] {source_info.get('type', 'unknown')}")
        console.print(f"  [dim]Location:[/dim] {source_info.get('source', 'unknown')}")

    # Validation status
    is_valid, errors = module.validate()
    if not is_valid:
        console.print()
        console.print("[yellow]Validation issues:[/yellow]")
        for err in errors:
            console.print(f"  {err}")


@mod.command(name="update")
@click.argument("module_name", required=False, default=None)
def update_module_cmd(module_name: str | None):
    """
    Update module(s) from their original source.

    Re-fetches the module from the source it was added from (git repo,
    folder, zip, or tar file). After updating, run 'lola update' to
    regenerate assistant files.

    \b
    Examples:
        lola mod update                    # Update all modules
        lola mod update my-module          # Update specific module
    """
    ensure_lola_dirs()

    if module_name:
        # Update specific module
        module_path = MODULES_DIR / module_name
        if not module_path.exists():
            console.print(f"[red]Module '{module_name}' not found[/red]")
            raise SystemExit(1)

        console.print(f"Updating {module_name}...")
        success, message = update_module(module_path)

        if success:
            console.print(f"[green]{message}[/green]")

            # Show updated module info
            module = Module.from_path(module_path)
            if module:
                console.print(f"  [dim]Skills:[/dim] {len(module.skills)}")

            console.print()
            console.print("[dim]Run 'lola update' to regenerate assistant files[/dim]")
        else:
            console.print(f"[red]{message}[/red]")
            raise SystemExit(1)
    else:
        # Update all modules
        modules = list_registered_modules()

        if not modules:
            console.print("[yellow]No modules to update[/yellow]")
            return

        console.print(f"Updating {len(modules)} module(s)...")
        console.print()

        updated = 0
        failed = 0

        for module in modules:
            console.print(f"  [cyan]{module.name}[/cyan]")
            success, message = update_module(module.path)

            if success:
                console.print(f"    [green]{message}[/green]")
                updated += 1
            else:
                console.print(f"    [red]{message}[/red]")
                failed += 1

        console.print()
        if updated > 0:
            console.print(f"[green]Updated {_count_str(updated, 'module')}[/green]")
        if failed > 0:
            console.print(
                f"[yellow]Failed to update {_count_str(failed, 'module')}[/yellow]"
            )

        if updated > 0:
            console.print()
            console.print("[dim]Run 'lola update' to regenerate assistant files[/dim]")
