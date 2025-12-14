"""
Module management CLI commands.

Commands for adding, removing, and managing lola modules.
"""

import shutil
from pathlib import Path

import click

from lola.config import MODULES_DIR, INSTALLED_FILE, get_assistant_skill_path
from lola.core.generator import remove_gemini_skills
from lola.models import Module, InstallationRegistry
from lola.sources import (
    fetch_module,
    detect_source_type,
    save_source_info,
    load_source_info,
    update_module,
    validate_module_name,
)
from lola.utils import ensure_lola_dirs, get_local_modules_path
from lola import ui


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


@click.group(name='mod')
def mod():
    """
    Manage lola modules.

    Add, remove, and list modules in your lola registry.
    """
    pass


@mod.command(name='add')
@click.argument('source')
@click.option(
    '-n', '--name',
    'module_name',
    default=None,
    help='Override the module name'
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
    if source_type == 'unknown':
        ui.error(f"Cannot determine source type for: {source}")
        ui.hint("Supported: git repos, .zip files, .tar/.tar.gz files, or local folders")
        raise SystemExit(1)

    ui.info(f"Adding module from {source_type}...")

    try:
        module_path = fetch_module(source, MODULES_DIR)
        # Save source info for future updates
        save_source_info(module_path, source, source_type)
    except Exception as e:
        ui.error(f"Failed to fetch module: {e}")
        raise SystemExit(1)

    # Rename if name override provided
    if module_name and module_path.name != module_name:
        # Validate the provided module name to prevent directory traversal
        try:
            module_name = validate_module_name(module_name)
        except ValueError as e:
            ui.error(str(e))
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
        ui.warning("No skills or commands found")
        ui.kv("Path", str(module_path))
        ui.hint("Add skill folders with SKILL.md or commands/*.md files")
        return

    is_valid, errors = module.validate()
    if not is_valid:
        ui.warning("Module has validation issues:")
        for err in errors:
            ui.item(err)

    ui.blank()
    ui.success(f"Added {ui.module_name(module.name)}")
    ui.kv("Path", str(module_path))
    ui.kv("Version", module.version)
    ui.kv("Skills", str(len(module.skills)))
    ui.kv("Commands", str(len(module.commands)))

    if module.skills:
        ui.blank()
        ui.subheader("Skills")
        for skill in module.skills:
            ui.item(skill)

    if module.commands:
        ui.blank()
        ui.subheader("Commands")
        for cmd in module.commands:
            ui.item(f"/{module.name}-{cmd}")

    ui.next_steps([f"lola install {module.name} -a <assistant> -s <scope>"])


@mod.command(name='init')
@click.argument('name', required=False, default=None)
@click.option(
    '-s', '--skill',
    'skill_name',
    default='example-skill',
    help='Name for the initial skill'
)
@click.option(
    '--no-skill',
    is_flag=True,
    help='Do not create an initial skill'
)
@click.option(
    '-c', '--command',
    'command_name',
    default='example-command',
    help='Name for an initial slash command'
)
@click.option(
    '--no-command',
    is_flag=True,
    help='Do not create an initial command'
)
def init_module(name: str | None, skill_name: str, no_skill: bool, command_name: str, no_command: bool):
    """
    Initialize a new lola module.

    Creates a module folder structure with skills and commands that are
    auto-discovered. Skills are folders containing SKILL.md files, and
    commands are .md files in the commands/ folder.

    \b
    Examples:
        lola mod init                           # Use current folder name
        lola mod init my-skills                 # Create my-skills/ subdirectory
        lola mod init -s code-review            # Custom skill name
        lola mod init --no-skill                # Skip initial skill
        lola mod init -c review-pr              # Custom command name
        lola mod init --no-command              # Skip initial command
    """
    if name:
        # Create a new subdirectory
        module_dir = Path.cwd() / name
        if module_dir.exists():
            ui.error(f"Directory already exists: {module_dir}")
            raise SystemExit(1)
        module_dir.mkdir(parents=True)
        module_name = name
    else:
        # Use current directory
        module_dir = Path.cwd()
        module_name = module_dir.name

    # Apply --no-skill and --no-command flags
    if no_skill:
        skill_name = None
    if no_command:
        command_name = None

    # Create initial skill if requested
    if skill_name:
        skill_dir = module_dir / skill_name
        if skill_dir.exists():
            ui.error(f"Skill directory already exists: {skill_dir}")
            raise SystemExit(1)
        skill_dir.mkdir()

        skill_content = f'''---
name: {skill_name}
description: Description of what this skill does and when to use it.
---

# {skill_name.replace('-', ' ').title()} Skill

Describe the skill's purpose and capabilities here.

## Usage

Explain how to use this skill.

## Examples

Provide examples of the skill in action.
'''
        (skill_dir / 'SKILL.md').write_text(skill_content)

    # Create initial command if requested
    if command_name:
        commands_dir = module_dir / 'commands'
        commands_dir.mkdir(exist_ok=True)

        command_content = f'''---
description: Description of what this command does
argument-hint: "[optional args]"
---

Prompt instructions for the {command_name} command.

Use $ARGUMENTS to reference any arguments passed to the command.
'''
        (commands_dir / f'{command_name}.md').write_text(command_content)

    ui.success(f"Initialized module [cyan]{module_name}[/cyan]")
    ui.kv("Path", str(module_dir))

    ui.blank()
    ui.subheader("Structure")
    ui.module_tree(
        module_name,
        skills=[skill_name] if skill_name else None,
        commands=[command_name] if command_name else None
    )

    steps = []
    if skill_name:
        steps.append(f"Edit {skill_name}/SKILL.md with your skill content")
    if command_name:
        steps.append(f"Edit commands/{command_name}.md with your command prompt")
    if not skill_name and not command_name:
        steps.append("Create skill directories with SKILL.md files")
        steps.append("Create commands/ directory with .md files for slash commands")
    steps.append(f"lola mod add {module_dir}")

    ui.next_steps(steps)


@mod.command(name='rm')
@click.argument('module_name')
@click.option(
    '-f', '--force',
    is_flag=True,
    help='Force removal without confirmation'
)
def remove_module(module_name: str, force: bool):
    """
    Remove a module from the lola registry.

    This also uninstalls the module from all AI assistants and removes
    generated skill files.
    """
    ensure_lola_dirs()

    module_path = MODULES_DIR / module_name

    if not module_path.exists():
        ui.error(f"Module '{module_name}' not found")
        ui.hint("Use 'lola mod ls' to see available modules")
        raise SystemExit(1)

    # Check for installations
    registry = InstallationRegistry(INSTALLED_FILE)
    installations = registry.find(module_name)

    if not force:
        ui.console.print(f"Remove module [cyan]{module_name}[/cyan] from registry?")
        ui.kv("Path", str(module_path))
        if installations:
            ui.blank()
            ui.warning(f"Will also uninstall from {len(installations)} location(s):")
            for inst in installations:
                loc = f"{inst.assistant}/{inst.scope}"
                if inst.project_path:
                    loc += f" ({inst.project_path})"
                ui.item(loc)
        ui.blank()
        if not click.confirm("Continue?"):
            ui.warning("Cancelled")
            return

    # Uninstall from all locations
    for inst in installations:
        try:
            skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
        except ValueError:
            ui.error(f"Cannot determine path for {inst.assistant}/{inst.scope}")
            continue

        # Remove generated files
        if inst.assistant == 'gemini-cli':
            # Remove entries from GEMINI.md
            if remove_gemini_skills(skill_dest, module_name):
                ui.dim(f"  Removed from: {skill_dest}")
        elif inst.assistant == 'cursor':
            # Remove .mdc files
            for skill in inst.skills:
                mdc_file = skill_dest / f'{skill}.mdc'
                if mdc_file.exists():
                    mdc_file.unlink()
                    ui.dim(f"  Removed: {mdc_file}")
        else:
            # Remove skill directories (claude-code)
            for skill in inst.skills:
                skill_dir = skill_dest / skill
                if skill_dir.exists():
                    shutil.rmtree(skill_dir)
                    ui.dim(f"  Removed: {skill_dir}")

        # Remove source files from project .lola/modules/ if applicable
        if inst.project_path:
            local_modules = get_local_modules_path(inst.project_path)
            source_module = local_modules / module_name
            if source_module.exists():
                shutil.rmtree(source_module)
                ui.dim(f"  Removed source: {source_module}")

        # Remove from registry
        registry.remove(
            module_name,
            assistant=inst.assistant,
            scope=inst.scope,
            project_path=inst.project_path
        )

    # Remove from global registry
    shutil.rmtree(module_path)
    ui.success(f"Removed {ui.module_name(module_name)}")


@mod.command(name='ls')
@click.option(
    '-v', '--verbose',
    is_flag=True,
    help='Show detailed module information'
)
def list_modules(verbose: bool):
    """
    List modules in the lola registry.

    Shows all modules that have been added with 'lola mod add'.
    """
    ensure_lola_dirs()

    modules = list_registered_modules()

    if not modules:
        ui.warning("No modules found")
        ui.blank()
        ui.hint("Add modules with: lola mod add <git-url|zip-file|tar-file|folder>")
        return

    ui.header(f"Modules ({len(modules)})")
    ui.blank()

    for module in modules:
        ui.console.print(f"{ui.module_name(module.name, module.version)}")

        if module.description:
            ui.console.print(f"  {module.description}")

        skills_str = ui.count_summary("skills", len(module.skills))
        cmds_str = ui.count_summary("commands", len(module.commands))
        ui.console.print(f"  [dim]{skills_str}, {cmds_str}[/dim]")

        if verbose:
            if module.skills:
                ui.console.print("  [bold]Skills:[/bold]")
                for skill in module.skills:
                    ui.item(skill, indent=2)
            if module.commands:
                ui.console.print("  [bold]Commands:[/bold]")
                for cmd in module.commands:
                    ui.item(f"/{module.name}-{cmd}", indent=2)

        ui.blank()


@mod.command(name='info')
@click.argument('module_name')
def module_info(module_name: str):
    """
    Show detailed information about a module.
    """
    ensure_lola_dirs()

    module_path = MODULES_DIR / module_name
    if not module_path.exists():
        ui.error(f"Module '{module_name}' not found")
        raise SystemExit(1)

    module = Module.from_path(module_path)
    if not module:
        ui.warning(f"No skills or commands found in '{module_name}'")
        ui.kv("Path", str(module_path))
        return

    ui.console.print(f"[bold cyan]{module.name}[/bold cyan]")
    ui.blank()
    ui.kv("Version", module.version)
    ui.kv("Path", str(module.path))

    if module.description:
        ui.kv("Description", module.description)

    ui.blank()
    ui.subheader("Skills")

    if not module.skills:
        ui.console.print("  [dim](none)[/dim]")
    else:
        from lola.frontmatter import parse_file
        for skill_rel in module.skills:
            skill_path = module.path / skill_rel
            if skill_path.exists():
                ui.item_result(skill_rel, ok=True)
                skill_file = skill_path / 'SKILL.md'
                if skill_file.exists():
                    # Show description from frontmatter
                    frontmatter, _ = parse_file(skill_file)
                    desc = frontmatter.get('description', '')
                    if desc:
                        ui.console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                ui.item_result(skill_rel, ok=False, note="not found")

    ui.blank()
    ui.subheader("Commands")

    if not module.commands:
        ui.console.print("  [dim](none)[/dim]")
    else:
        from lola.command_converters import parse_command_frontmatter
        commands_dir = module.path / 'commands'
        for cmd_name in module.commands:
            cmd_path = commands_dir / f'{cmd_name}.md'
            if cmd_path.exists():
                ui.item_result(f"/{module.name}-{cmd_name}", ok=True)
                # Show description from frontmatter
                content = cmd_path.read_text()
                frontmatter, _ = parse_command_frontmatter(content)
                desc = frontmatter.get('description', '')
                if desc:
                    ui.console.print(f"    [dim]{desc[:60]}[/dim]")
            else:
                ui.item_result(cmd_name, ok=False, note="not found")

    # Source info
    source_info = load_source_info(module.path)
    if source_info:
        ui.blank()
        ui.subheader("Source")
        ui.kv("Type", source_info.get('type', 'unknown'))
        ui.kv("Location", source_info.get('source', 'unknown'))

    # Validation status
    is_valid, errors = module.validate()
    if not is_valid:
        ui.blank()
        ui.warning("Validation issues:")
        for err in errors:
            ui.item(err)


@mod.command(name='update')
@click.argument('module_name', required=False, default=None)
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
            ui.error(f"Module '{module_name}' not found")
            raise SystemExit(1)

        ui.info(f"Updating {ui.module_name(module_name)}...")
        success, message = update_module(module_path)

        if success:
            ui.success(message)

            # Show updated module info
            module = Module.from_path(module_path)
            if module:
                ui.kv("Version", module.version)
                ui.kv("Skills", str(len(module.skills)))

            ui.blank()
            ui.hint("Run 'lola update' to regenerate assistant files")
        else:
            ui.error(message)
            raise SystemExit(1)
    else:
        # Update all modules
        modules = list_registered_modules()

        if not modules:
            ui.warning("No modules to update")
            return

        ui.info(f"Updating {len(modules)} module(s)...")
        ui.blank()

        updated = 0
        failed = 0

        for module in modules:
            ui.console.print(f"  {ui.module_name(module.name)}")
            success, message = update_module(module.path)

            if success:
                ui.item_result(message, ok=True, indent=2)
                updated += 1
            else:
                ui.item_result(message, ok=False, indent=2)
                failed += 1

        ui.blank()
        if updated > 0:
            ui.success(f"Updated {ui.count_summary('modules', updated)}")
        if failed > 0:
            ui.warning(f"Failed to update {ui.count_summary('modules', failed)}")

        if updated > 0:
            ui.blank()
            ui.hint("Run 'lola update' to regenerate assistant files")
