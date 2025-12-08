"""
mod:
    Module management commands for lola package manager
"""

import shutil
from pathlib import Path

import click

from lola.config import MODULES_DIR, get_assistant_skill_path
from lola.layout import console
from lola.models import Module, InstallationRegistry
from lola.config import INSTALLED_FILE
from lola.sources import fetch_module, detect_source_type, save_source_info, load_source_info, update_module
from lola.install import remove_gemini_skills
from lola.utils import ensure_lola_dirs, get_local_modules_path


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
      - A path to a zip file (/path/to/module.zip)
      - A path to a tar file (/path/to/module.tar.gz)
      - A path to a local folder (/path/to/module)

    \b
    Examples:
        lola mod add https://github.com/user/my-skills.git
        lola mod add ./my-local-module
        lola mod add ~/Downloads/skills.zip
    """
    ensure_lola_dirs()

    source_type = detect_source_type(source)
    if source_type == 'unknown':
        console.print(f"[red]Cannot determine source type for: {source}[/red]")
        console.print("Supported sources: git repos, .zip files, .tar/.tar.gz files, or local folders")
        raise SystemExit(1)

    console.print(f"[bold]Adding module from {source_type} source...[/bold]")

    try:
        module_path = fetch_module(source, MODULES_DIR)
        # Save source info for future updates
        save_source_info(module_path, source, source_type)
    except Exception as e:
        console.print(f"[red]Failed to fetch module: {e}[/red]")
        raise SystemExit(1)

    # Rename if name override provided
    if module_name and module_path.name != module_name:
        new_path = MODULES_DIR / module_name
        if new_path.exists():
            shutil.rmtree(new_path)
        module_path.rename(new_path)
        module_path = new_path

    # Validate module structure
    module = Module.from_path(module_path)
    if not module:
        console.print(f"[yellow]Warning: No valid .lola/module.yml found[/yellow]")
        console.print(f"Module added to: {module_path}")
        console.print("Create a .lola/module.yml to define skills for installation.")
        return

    is_valid, errors = module.validate()
    if not is_valid:
        console.print(f"[yellow]Module has validation warnings:[/yellow]")
        for err in errors:
            console.print(f"  - {err}")

    console.print()
    console.print(f"[green]Module '{module.name}' added successfully![/green]")
    console.print(f"  Path: {module_path}")
    console.print(f"  Version: {module.version}")
    console.print(f"  Skills: {len(module.skills)}")

    if module.skills:
        console.print()
        console.print("Available skills:")
        for skill in module.skills:
            console.print(f"  - {skill}")

    console.print()
    console.print("Next steps:")
    console.print(f"  lola install {module.name} -a <assistant> -s <scope>")


@mod.command(name='init')
@click.argument('name', required=False, default=None)
@click.option(
    '-d', '--description',
    default='',
    help='Module description'
)
@click.option(
    '-s', '--skill',
    'skill_name',
    default=None,
    help='Name for the initial skill (default: module name)'
)
@click.option(
    '--no-skill',
    is_flag=True,
    help='Do not create an initial skill'
)
def init_module(name: str | None, description: str, skill_name: str, no_skill: bool):
    """
    Initialize a new lola module.

    Creates the .lola/module.yml configuration file in the current directory
    or in a new subdirectory if NAME is provided. By default, creates an
    initial skill with the same name as the module.

    \b
    Examples:
        lola mod init                           # Use current folder name
        lola mod init my-skills                 # Create my-skills/ subdirectory
        lola mod init -d "My custom skills"
        lola mod init -s code-review            # Custom skill name
        lola mod init --no-skill                # Skip initial skill
    """
    if name:
        # Create a new subdirectory
        module_dir = Path.cwd() / name
        if module_dir.exists():
            console.print(f"[red]Directory '{module_dir}' already exists[/red]")
            raise SystemExit(1)
        module_dir.mkdir(parents=True)
        module_name = name
    else:
        # Use current directory
        module_dir = Path.cwd()
        module_name = module_dir.name

    lola_dir = module_dir / '.lola'
    if lola_dir.exists():
        console.print(f"[red]Module already initialized (.lola/ exists)[/red]")
        raise SystemExit(1)

    lola_dir.mkdir()

    # Determine skill name (default to module name unless --no-skill)
    if no_skill:
        skill_name = None
    elif skill_name is None:
        skill_name = module_name

    # Create module.yml
    skills_list = []
    if skill_name:
        skills_list.append(skill_name)

    module_yml = {
        'type': 'lola/module',
        'version': '0.1.0',
        'description': description or f'{module_name} module',
        'skills': skills_list,
    }

    import yaml
    (lola_dir / 'module.yml').write_text(yaml.dump(module_yml, default_flow_style=False, sort_keys=False))

    # Create initial skill if requested
    if skill_name:
        skill_dir = module_dir / skill_name
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

    console.print(f"[green]Initialized module '{module_name}'[/green]")
    console.print(f"  Path: {module_dir}")
    console.print()
    console.print("[bold]Structure:[/bold]")
    console.print(f"  {module_name}/")
    console.print(f"    .lola/")
    console.print(f"      module.yml")
    if skill_name:
        console.print(f"    {skill_name}/")
        console.print(f"      SKILL.md")

    console.print()
    console.print("[bold]Next steps:[/bold]")
    if skill_name:
        console.print(f"  1. Edit {skill_name}/SKILL.md with your skill content")
        console.print(f"  2. lola mod add {module_dir}")
    else:
        console.print(f"  1. Create skill directories with SKILL.md files")
        console.print(f"  2. Add skill names to .lola/module.yml")
        console.print(f"  3. lola mod add {module_dir}")


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
        console.print(f"[red]Module '{module_name}' not found in registry[/red]")
        console.print(f"Use 'lola mod ls' to see available modules")
        raise SystemExit(1)

    # Check for installations
    registry = InstallationRegistry(INSTALLED_FILE)
    installations = registry.find(module_name)

    if not force:
        console.print(f"This will remove module '{module_name}' from the registry.")
        console.print(f"Path: {module_path}")
        if installations:
            console.print(f"[yellow]This will also uninstall from {len(installations)} location(s):[/yellow]")
            for inst in installations:
                loc = f"  - {inst.assistant}/{inst.scope}"
                if inst.project_path:
                    loc += f" ({inst.project_path})"
                console.print(loc)
        if not click.confirm("Continue?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Uninstall from all locations
    for inst in installations:
        try:
            skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
        except ValueError:
            console.print(f"[red]Cannot determine path for {inst.assistant}/{inst.scope}[/red]")
            continue

        # Remove generated files
        if inst.assistant == 'gemini-cli':
            # Remove entries from GEMINI.md
            if remove_gemini_skills(skill_dest, module_name):
                console.print(f"  [dim]Removed from: {skill_dest}[/dim]")
        elif inst.assistant == 'cursor':
            # Remove .mdc files
            for skill_name in inst.skills:
                mdc_file = skill_dest / f'{skill_name}.mdc'
                if mdc_file.exists():
                    mdc_file.unlink()
                    console.print(f"  [dim]Removed: {mdc_file}[/dim]")
        else:
            # Remove skill directories (claude-code)
            for skill_name in inst.skills:
                skill_dir = skill_dest / skill_name
                if skill_dir.exists():
                    shutil.rmtree(skill_dir)
                    console.print(f"  [dim]Removed: {skill_dir}[/dim]")

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
            project_path=inst.project_path
        )

    # Remove from global registry
    shutil.rmtree(module_path)
    console.print(f"[green]Module '{module_name}' removed from registry[/green]")


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
        console.print("[yellow]No modules found in registry[/yellow]")
        console.print()
        console.print("Add modules with:")
        console.print("  lola mod add <git-url|zip-file|tar-file|folder>")
        return

    console.print(f"[bold]Registered modules ({len(modules)}):[/bold]")
    console.print()

    for module in modules:
        console.print(f"[cyan]{module.name}[/cyan] (v{module.version})")

        if module.description:
            console.print(f"  {module.description}")

        console.print(f"  Skills: {len(module.skills)}")

        if verbose and module.skills:
            for skill in module.skills:
                console.print(f"    - {skill}")

        console.print()


@mod.command(name='info')
@click.argument('module_name')
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
        console.print(f"[yellow]No valid .lola/module.yml found in '{module_name}'[/yellow]")
        console.print(f"Path: {module_path}")
        return

    console.print(f"[bold cyan]{module.name}[/bold cyan]")
    console.print()
    console.print(f"  Version: {module.version}")
    console.print(f"  Path: {module.path}")

    if module.description:
        console.print(f"  Description: {module.description}")

    console.print()
    console.print("[bold]Skills:[/bold]")

    if not module.skills:
        console.print("  (no skills defined)")
    else:
        for skill_rel in module.skills:
            skill_path = module.path / skill_rel
            if skill_path.exists():
                console.print(f"  [green]{skill_rel}[/green]")
                skill_file = skill_path / 'SKILL.md'
                if skill_file.exists():
                    # Show first line of SKILL.md as description
                    content = skill_file.read_text().strip()
                    lines = content.split('\n')
                    for line in lines:
                        if line.strip() and not line.startswith('#') and not line.startswith('---'):
                            console.print(f"    {line.strip()[:60]}")
                            break
            else:
                console.print(f"  [red]{skill_rel}[/red] (not found)")

    # Source info
    source_info = load_source_info(module.path)
    if source_info:
        console.print()
        console.print("[bold]Source:[/bold]")
        console.print(f"  Type: {source_info.get('type', 'unknown')}")
        console.print(f"  Location: {source_info.get('source', 'unknown')}")

    # Validation status
    is_valid, errors = module.validate()
    if not is_valid:
        console.print()
        console.print("[yellow]Validation issues:[/yellow]")
        for err in errors:
            console.print(f"  - {err}")


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
            console.print(f"[red]Module '{module_name}' not found[/red]")
            raise SystemExit(1)

        console.print(f"[bold]Updating '{module_name}'...[/bold]")
        success, message = update_module(module_path)

        if success:
            console.print(f"[green]{message}[/green]")

            # Show updated module info
            module = Module.from_path(module_path)
            if module:
                console.print(f"  Version: {module.version}")
                console.print(f"  Skills: {len(module.skills)}")

            console.print()
            console.print("Run 'lola update' to regenerate assistant files.")
        else:
            console.print(f"[red]{message}[/red]")
            raise SystemExit(1)
    else:
        # Update all modules
        modules = list_registered_modules()

        if not modules:
            console.print("[yellow]No modules to update[/yellow]")
            return

        console.print(f"[bold]Updating {len(modules)} module(s)...[/bold]")
        console.print()

        updated = 0
        failed = 0

        for module in modules:
            console.print(f"[cyan]{module.name}[/cyan]")
            success, message = update_module(module.path)

            if success:
                console.print(f"  [green]{message}[/green]")
                updated += 1
            else:
                console.print(f"  [red]{message}[/red]")
                failed += 1

        console.print()
        if updated > 0:
            console.print(f"[green]Updated {updated} module(s)[/green]")
        if failed > 0:
            console.print(f"[yellow]Failed to update {failed} module(s)[/yellow]")

        if updated > 0:
            console.print()
            console.print("Run 'lola update' to regenerate assistant files.")
