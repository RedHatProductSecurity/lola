"""
Module management CLI commands.

Commands for adding, removing, and managing lola modules.
"""

import shutil
from pathlib import Path
from typing import NoReturn

import click
from rich.console import Console
from rich.tree import Tree

from lola.config import MCPS_FILE, MODULES_DIR, INSTALLED_FILE
from lola.exceptions import (
    LolaError,
    ModuleNameError,
    ModuleNotFoundError,
    PathExistsError,
    SourceError,
    UnsupportedSourceError,
)
from lola.models import Module, InstallationRegistry
from lola.targets import get_target
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


def _handle_lola_error(e: LolaError) -> NoReturn:
    """Handle a LolaError by printing an error message and exiting."""
    console.print(f"[red]{e}[/red]")
    raise SystemExit(1)


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
    has_mcps: bool = False,
    has_instructions: bool = False,
) -> None:
    """Print a module structure as a tree."""
    tree = Tree(f"[cyan]{name}/[/cyan]")

    if skills:
        skills_node = tree.add("[dim]skills/[/dim]")
        for skill in skills:
            skill_node = skills_node.add(f"[green]{skill}/[/green]")
            skill_node.add("[dim]SKILL.md[/dim]")

    if commands:
        cmd_node = tree.add("[dim]commands/[/dim]")
        for cmd in commands:
            cmd_node.add(f"[dim]{cmd}.md[/dim]")

    if agents:
        agent_node = tree.add("[dim]agents/[/dim]")
        for agent in agents:
            agent_node.add(f"[dim]{agent}.md[/dim]")

    if has_mcps:
        tree.add("[dim]mcps.json[/dim]")

    if has_instructions:
        tree.add("[dim]AGENTS.md[/dim]")

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
        _handle_lola_error(UnsupportedSourceError(source))

    console.print(f"Adding module from {source_type}...")

    try:
        module_path = fetch_module(source, MODULES_DIR)
        # Save source info for future updates
        save_source_info(module_path, source, source_type)
    except LolaError as e:
        _handle_lola_error(e)
    except Exception as e:
        console.print(f"[red]Failed to fetch module: {e}[/red]")
        raise SystemExit(1)

    # Rename if name override provided
    if module_name and module_path.name != module_name:
        # Validate the provided module name to prevent directory traversal
        try:
            module_name = validate_module_name(module_name)
        except ModuleNameError as e:
            # Clean up the fetched module
            if module_path.exists():
                shutil.rmtree(module_path)
            _handle_lola_error(e)

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
            console.print(f"  /{module.name}.{cmd}")

    if module.agents:
        console.print()
        console.print("[bold]Agents[/bold]")
        for agent in module.agents:
            console.print(f"  @{module.name}.{agent}")

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
    default="example-agent",
    help="Name for an initial agent",
)
@click.option("--no-agent", is_flag=True, help="Do not create an initial agent")
@click.option("--no-mcps", is_flag=True, help="Do not create mcps.json")
@click.option("--no-instructions", is_flag=True, help="Do not create AGENTS.md")
@click.option(
    "--minimal", is_flag=True, help="Create only empty directories, no example content"
)
@click.option("--force", is_flag=True, help="Overwrite existing directory")
def init_module(
    name: str | None,
    skill_name: str,
    no_skill: bool,
    command_name: str,
    no_command: bool,
    agent_name: str | None,
    no_agent: bool,
    no_mcps: bool,
    no_instructions: bool,
    minimal: bool,
    force: bool,
):
    """
    Initialize a new lola module.

    Creates a module folder structure with a module/ subdirectory containing
    skills, commands, agents, mcps.json, and AGENTS.md. A README.md is created
    at the repository root.

    By default, creates example content in the module/ directory. Use --minimal
    to create only empty directories, or use --no-skill, --no-command, --no-agent,
    --no-mcps, or --no-instructions to skip specific components.

    \b
    Examples:
        lola mod init                           # Use current folder name
        lola mod init my-skills                 # Create my-skills/ subdirectory
        lola mod init --minimal                 # Empty structure, no example content
        lola mod init --force                   # Overwrite existing directory
        lola mod init -s code-review            # Custom skill name
        lola mod init --no-skill                # Skip initial skill
        lola mod init -c review-pr              # Custom command name
        lola mod init -g my-agent               # Custom agent name
        lola mod init --no-mcps                 # Skip creating mcps.json
        lola mod init --no-instructions         # Skip creating AGENTS.md
    """
    if name:
        # Create a new subdirectory
        repo_dir = Path.cwd() / name
        if repo_dir.exists():
            if force:
                shutil.rmtree(repo_dir)
            else:
                _handle_lola_error(PathExistsError(repo_dir, "Directory"))
        repo_dir.mkdir(parents=True)
        module_name = name
    else:
        # Use current directory
        repo_dir = Path.cwd()
        module_name = repo_dir.name

    # Create module/ subdirectory for lola-importable content
    module_dir = repo_dir / "module"
    module_dir.mkdir(exist_ok=True)

    # With --minimal, skip all example content, mcps.json, and AGENTS.md
    if minimal:
        no_skill = True
        no_command = True
        no_agent = True
        no_mcps = True
        no_instructions = True

    # Apply --no-skill, --no-command, and --no-agent flags
    final_skill_name: str | None = None if no_skill else skill_name
    final_command_name: str | None = None if no_command else command_name
    final_agent_name: str | None = None if no_agent else agent_name

    # Create directories inside module/
    skills_dir = module_dir / "skills"
    commands_dir = module_dir / "commands"
    agents_dir = module_dir / "agents"

    # Always create empty directories
    skills_dir.mkdir(exist_ok=True)
    commands_dir.mkdir(exist_ok=True)
    agents_dir.mkdir(exist_ok=True)

    # Helper for title casing names
    def _title_case(s: str) -> str:
        return s.replace("-", " ").title()

    # Create initial skill if requested
    if final_skill_name:
        skill_dir = skills_dir / final_skill_name
        if skill_dir.exists():
            console.print(
                f"[yellow]Skill directory already exists, skipping:[/yellow] {skill_dir}"
            )
        else:
            skill_dir.mkdir()

            skill_content = f"""---
name: {final_skill_name}
description: [REPLACE: Brief description of what this skill does and when to use it]
---

# {_title_case(final_skill_name)} Skill

[REPLACE: Detailed description of the skill's purpose and capabilities]

## When to Use

[REPLACE: Describe the scenarios and triggers for using this skill]

## Instructions

[REPLACE: Step-by-step instructions for the AI assistant to follow]

## Examples

[REPLACE: Provide concrete examples of the skill in action]

### Example 1: [REPLACE: Example Title]

```
[REPLACE: Example input/output or workflow]
```

## Best Practices

[REPLACE: Tips and guidelines for effective skill usage]
"""
            (skill_dir / "SKILL.md").write_text(skill_content)

    # Create initial command if requested
    if final_command_name:
        command_file = commands_dir / f"{final_command_name}.md"
        if command_file.exists():
            console.print(
                f"[yellow]Command file already exists, skipping:[/yellow] {command_file}"
            )
        else:
            command_content = """---
description: [REPLACE: Brief description of what this command does]
argument-hint: "[REPLACE: expected arguments, e.g., <file> [options]]"
---

[REPLACE: Prompt instructions for the AI assistant when this command is invoked]

## Arguments

Use `$ARGUMENTS` to access any arguments passed to this command.

## Workflow

1. [REPLACE: First step]
2. [REPLACE: Second step]
3. [REPLACE: Continue as needed]

## Output

[REPLACE: Describe what the command should produce or accomplish]
"""
            command_file.write_text(command_content)

    # Create initial agent if requested
    if final_agent_name:
        agent_file = agents_dir / f"{final_agent_name}.md"
        if agent_file.exists():
            console.print(
                f"[yellow]Agent file already exists, skipping:[/yellow] {agent_file}"
            )
        else:
            agent_content = f"""---
description: [REPLACE: Brief description of what this agent does and when to delegate to it]
---

# {_title_case(final_agent_name)}

[REPLACE: Detailed instructions for this specialized agent]

## Purpose

[REPLACE: What tasks is this agent designed to handle?]

## Capabilities

[REPLACE: What can this agent do?]

## Guidelines

[REPLACE: Rules and best practices for this agent's behavior]

## Workflow

1. [REPLACE: Describe the agent's typical workflow]
2. [REPLACE: Continue as needed]
"""
            agent_file.write_text(agent_content)

    # Create mcps.json if not skipped (in module/)
    if not no_mcps:
        mcps_file = module_dir / MCPS_FILE
        if mcps_file.exists():
            console.print(
                f"[yellow]mcps.json already exists, skipping:[/yellow] {mcps_file}"
            )
        else:
            mcps_content = """{
  "mcpServers": {
    "[REPLACE: your-server-name]": {
      "command": "[REPLACE: command to run, e.g., npx]",
      "args": [
        "[REPLACE: first argument]",
        "[REPLACE: second argument, e.g., @package/server]"
      ],
      "env": {
        "[REPLACE: ENV_VAR_NAME]": "${[REPLACE: ENV_VAR_NAME]}"
      }
    }
  }
}
"""
            mcps_file.write_text(mcps_content)

    # Create AGENTS.md if not skipped (in module/)
    if not no_instructions:
        agents_md_file = module_dir / "AGENTS.md"
        if agents_md_file.exists():
            console.print(
                f"[yellow]AGENTS.md already exists, skipping:[/yellow] {agents_md_file}"
            )
        else:
            # Build the "When to Use" section based on what was created
            when_to_use_items = []

            if final_skill_name:
                when_to_use_items.append(
                    f"- **{_title_case(final_skill_name)}**: Use the `{final_skill_name}` skill for [REPLACE: describe when to use]"
                )
            if final_command_name:
                when_to_use_items.append(
                    f"- **{_title_case(final_command_name)}**: Use `/{module_name}.{final_command_name}` to [REPLACE: describe what it does]"
                )
            if final_agent_name:
                when_to_use_items.append(
                    f"- **{_title_case(final_agent_name)}**: Delegate to `@{module_name}.{final_agent_name}` for [REPLACE: describe when to use]"
                )

            if not when_to_use_items:
                when_to_use_items.append(
                    "- [REPLACE: Add skills, commands, or agents and describe when to use them]"
                )

            agents_md_content = f"""# {_title_case(module_name)}

[REPLACE: Brief overview of what this module provides]

## When to Use

{chr(10).join(when_to_use_items)}

## Configuration

[REPLACE: Any configuration or setup requirements]

## Notes

[REPLACE: Additional guidance for AI assistants using this module]
"""
            agents_md_file.write_text(agents_md_content)

    # Create README.md at repo root
    readme_file = repo_dir / "README.md"
    if readme_file.exists():
        console.print(
            f"[yellow]README.md already exists, skipping:[/yellow] {readme_file}"
        )
    else:
        # Build component sections based on what was created
        skills_section = "[REPLACE: List and describe each skill in module/skills/]"
        commands_section = (
            "[REPLACE: List and describe each command in module/commands/]"
        )
        agents_section = "[REPLACE: List and describe each agent in module/agents/]"
        mcps_section = (
            "[REPLACE: List and describe each MCP server in module/mcps.json]"
        )

        readme_content = f"""# {_title_case(module_name)}

[REPLACE: Brief description of what this module provides]

## Installation

```bash
# Add to lola registry
lola mod add /path/to/{module_name}

# Install to a project
lola install {module_name}
```

## Components

### Skills

{skills_section}

### Commands

{commands_section}

### Agents

{agents_section}

### MCP Servers

{mcps_section}

## Development

This module follows the lola module structure:

```
{module_name}/
├── README.md           # This file (repo documentation)
└── module/             # Lola-importable content
    ├── skills/         # Skill folders with SKILL.md
    ├── commands/       # Slash command .md files
    ├── agents/         # Subagent .md files
    ├── mcps.json       # MCP server configuration
    └── AGENTS.md       # Module-level instructions
```

Edit files in `module/` to customize the content that gets installed to AI assistants.

## License

[REPLACE: Your license here]
"""
        readme_file.write_text(readme_content)

    console.print(f"[green]Initialized module {module_name}[/green]")
    console.print(f"  [dim]Path:[/dim] {repo_dir}")

    console.print()
    console.print("[bold]Structure[/bold]")
    # Print tree with module/ subdirectory
    tree = Tree(f"[cyan]{module_name}/[/cyan]")
    tree.add("[dim]README.md[/dim]")
    module_node = tree.add("[cyan]module/[/cyan]")

    if final_skill_name or not minimal:
        skills_node = module_node.add("[dim]skills/[/dim]")
        if final_skill_name:
            skill_node = skills_node.add(f"[green]{final_skill_name}/[/green]")
            skill_node.add("[dim]SKILL.md[/dim]")

    if final_command_name or not minimal:
        cmd_node = module_node.add("[dim]commands/[/dim]")
        if final_command_name:
            cmd_node.add(f"[dim]{final_command_name}.md[/dim]")

    if final_agent_name or not minimal:
        agent_node = module_node.add("[dim]agents/[/dim]")
        if final_agent_name:
            agent_node.add(f"[dim]{final_agent_name}.md[/dim]")

    if not no_mcps:
        module_node.add("[dim]mcps.json[/dim]")
    if not no_instructions:
        module_node.add("[dim]AGENTS.md[/dim]")

    console.print(tree)

    steps = []
    steps.append("Replace [REPLACE: ...] markers with your content")
    if final_skill_name:
        steps.append(
            f"Edit module/skills/{final_skill_name}/SKILL.md with your skill content"
        )
    else:
        steps.append("Add skill directories under module/skills/ with SKILL.md files")
    if final_command_name:
        steps.append(
            f"Edit module/commands/{final_command_name}.md with your command prompt"
        )
    else:
        steps.append("Add .md files to module/commands/ for slash commands")
    if final_agent_name:
        steps.append(
            f"Edit module/agents/{final_agent_name}.md with your agent instructions"
        )
    else:
        steps.append("Add .md files to module/agents/ for subagents")
    if not no_mcps:
        steps.append(f"Edit module/{MCPS_FILE} to configure MCP servers")
    if not no_instructions:
        steps.append("Edit module/AGENTS.md with module instructions")
    steps.append(f"lola mod add {repo_dir}")

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
        _handle_lola_error(ModuleNotFoundError(module_name))

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
        if target.uses_managed_section:
            # Remove module section from managed file (e.g., GEMINI.md, AGENTS.md)
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
                    console.print(f"    /{module.name}.{cmd}")
            if module.agents:
                console.print("  [bold]Agents:[/bold]")
                for agent in module.agents:
                    console.print(f"    @{module.name}.{agent}")

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
        _handle_lola_error(ModuleNotFoundError(module_name))

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
                console.print(f"  [green]/{module.name}.{cmd_name}[/green]")
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
                console.print(f"  [green]@{module.name}.{agent_name}[/green]")
                # Show description from frontmatter
                frontmatter, _ = fm_parse_file(agent_path)
                desc = frontmatter.get("description", "")
                if desc:
                    console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                console.print(f"  [red]{agent_name}[/red] [dim](not found)[/dim]")

    console.print()
    console.print("[bold]MCP Servers[/bold]")

    if not module.mcps:
        console.print("  [dim](none)[/dim]")
    else:
        import json
        from lola.config import MCPS_FILE

        mcps_file = module.path / MCPS_FILE
        mcps_data = {}
        if mcps_file.exists():
            try:
                mcps_data = json.loads(mcps_file.read_text()).get("mcpServers", {})
            except (json.JSONDecodeError, OSError):
                pass

        for mcp_name in module.mcps:
            console.print(f"  [green]{mcp_name}[/green]")
            mcp_info = mcps_data.get(mcp_name, {})
            cmd = mcp_info.get("command", "")
            args = mcp_info.get("args", [])
            if cmd:
                cmd_str = f"{cmd} {' '.join(args[:2])}"
                if len(args) > 2:
                    cmd_str += " ..."
                console.print(f"    [dim]{cmd_str[:60]}[/dim]")

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
            _handle_lola_error(ModuleNotFoundError(module_name))

        console.print(f"Updating {module_name}...")
        try:
            message = update_module(module_path)
            console.print(f"[green]{message}[/green]")

            # Show updated module info
            module = Module.from_path(module_path)
            if module:
                console.print(f"  [dim]Skills:[/dim] {len(module.skills)}")

            console.print()
            console.print("[dim]Run 'lola update' to regenerate assistant files[/dim]")
        except SourceError as e:
            _handle_lola_error(e)
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
            try:
                message = update_module(module.path)
                console.print(f"    [green]{message}[/green]")
                updated += 1
            except SourceError as e:
                console.print(f"    [red]{e}[/red]")
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
