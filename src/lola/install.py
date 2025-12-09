"""
install:
    Install and uninstall commands for lola skills

Architecture:
    - Source files live in .lola/modules/<module>/<skill>/
    - Generated assistant-specific files go to their expected locations:
        - Claude: .claude/skills/<skill>/SKILL.md
        - Cursor: .cursor/rules/<skill>.mdc
        - Gemini: .gemini/GEMINI.md (entries appended to managed section)
    - lola manages all generated files and can update them when source changes
"""

import shutil
from pathlib import Path
from typing import Optional

import click

from lola.config import (
    ASSISTANTS,
    INSTALLED_FILE,
    MODULES_DIR,
    get_assistant_skill_path,
)
from lola.converters import skill_to_claude, skill_to_cursor_mdc
from lola.layout import console
from lola.models import Installation, InstallationRegistry, Module
from lola.utils import ensure_lola_dirs, get_local_modules_path


def get_registry() -> InstallationRegistry:
    """Get the installation registry."""
    return InstallationRegistry(INSTALLED_FILE)


def link_module_to_local(module: Module, local_modules_path: Path) -> Path:
    """
    Link a module from the global registry to the local .lola/modules/.

    For user scope (same path), just returns the path.
    For project scope, creates a symlink to the global module.

    Args:
        module: The module to link
        local_modules_path: Path to .lola/modules/

    Returns:
        Path to the linked module
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

    # Create symlink to global module
    dest.symlink_to(module.path.resolve())

    return dest


def copy_module_to_local(module: Module, local_modules_path: Path) -> Path:
    """
    Copy a module from the global registry to the local .lola/modules/.

    Used for Gemini CLI which cannot follow symlinks outside the workspace.

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


def generate_claude_skill(source_path: Path, dest_path: Path) -> bool:
    """
    Generate Claude skill files from source.

    Args:
        source_path: Path to source skill in .lola/modules/
        dest_path: Path to .claude/skills/<skill>/

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    dest_path.mkdir(parents=True, exist_ok=True)

    # Generate SKILL.md
    content = skill_to_claude(source_path)
    if content:
        (dest_path / 'SKILL.md').write_text(content)

    # Copy supporting files (not SKILL.md)
    for item in source_path.iterdir():
        if item.name == 'SKILL.md':
            continue
        dest_item = dest_path / item.name
        if item.is_dir():
            if dest_item.exists():
                shutil.rmtree(dest_item)
            shutil.copytree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)

    return True


def generate_cursor_rule(source_path: Path, rules_dir: Path, skill_name: str) -> bool:
    """
    Generate Cursor .mdc rule from source.

    Args:
        source_path: Path to source skill in .lola/modules/
        rules_dir: Path to .cursor/rules/
        skill_name: Name of the skill

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    rules_dir.mkdir(parents=True, exist_ok=True)

    # Generate .mdc file with paths pointing to source
    content = skill_to_cursor_mdc(source_path, str(source_path))
    if content:
        mdc_file = rules_dir / f'{skill_name}.mdc'
        mdc_file.write_text(content)

    return True


def get_skill_description(source_path: Path) -> str:
    """Extract description from a SKILL.md file's frontmatter."""
    skill_file = source_path / 'SKILL.md'
    if not skill_file.exists():
        return ''

    content = skill_file.read_text()
    from lola.converters import parse_skill_frontmatter
    frontmatter, _ = parse_skill_frontmatter(content)
    return frontmatter.get('description', '')


# Markers for lola-managed sections in GEMINI.md
GEMINI_START_MARKER = "<!-- lola:skills:start -->"
GEMINI_END_MARKER = "<!-- lola:skills:end -->"


GEMINI_HEADER = """## Lola Skills

These skills are installed by Lola and provide specialized capabilities.
When a task matches a skill's description, read the skill's SKILL.md file
to learn the detailed instructions and workflows.

**How to use skills:**
1. Check if your task matches any skill description below
2. Use `read_file` to read the skill's SKILL.md for detailed instructions
3. Follow the instructions in the SKILL.md file

"""


def update_gemini_md(gemini_file: Path, module_name: str, skills: list[tuple[str, str, Path]], project_path: str) -> bool:
    """
    Add or update skill entries in GEMINI.md file.

    Args:
        gemini_file: Path to GEMINI.md
        module_name: Name of the module being installed
        skills: List of (skill_name, description, skill_path) tuples
        project_path: Path to the project root (for relative paths)

    Returns:
        True if successful
    """
    # Read existing content or start fresh
    if gemini_file.exists():
        content = gemini_file.read_text()
    else:
        gemini_file.parent.mkdir(parents=True, exist_ok=True)
        content = ""

    project_root = Path(project_path)

    # Build the skills section for this module
    skills_block = f"\n### {module_name}\n\n"
    for skill_name, description, skill_path in skills:
        # Use relative path from project root for Gemini compatibility
        try:
            relative_path = skill_path.relative_to(project_root)
            skill_md_path = relative_path / 'SKILL.md'
        except ValueError:
            # Fallback to absolute path if not relative to project
            skill_md_path = skill_path / 'SKILL.md'
        skills_block += f"#### {skill_name}\n"
        skills_block += f"**When to use:** {description}\n"
        skills_block += f"**Instructions:** Read `{skill_md_path}` for detailed guidance.\n\n"

    # Find or create the lola-managed section
    if GEMINI_START_MARKER in content and GEMINI_END_MARKER in content:
        # Extract existing lola section
        start_idx = content.index(GEMINI_START_MARKER)
        end_idx = content.index(GEMINI_END_MARKER) + len(GEMINI_END_MARKER)
        existing_section = content[start_idx:end_idx]

        # Parse existing modules in the section
        section_content = existing_section[len(GEMINI_START_MARKER):-len(GEMINI_END_MARKER)]

        # Remove old entry for this module if exists
        lines = section_content.split('\n')
        new_lines = []
        skip_until_next_module = False
        for line in lines:
            if line.startswith('### '):
                if line == f'### {module_name}':
                    skip_until_next_module = True
                    continue
                else:
                    skip_until_next_module = False
            if not skip_until_next_module:
                new_lines.append(line)

        # Add new module entry
        new_section = GEMINI_START_MARKER + '\n'.join(new_lines) + skills_block + GEMINI_END_MARKER
        content = content[:start_idx] + new_section + content[end_idx:]
    else:
        # Add new lola section at end
        lola_section = f"\n\n{GEMINI_HEADER}{GEMINI_START_MARKER}\n{skills_block}{GEMINI_END_MARKER}\n"
        content = content.rstrip() + lola_section

    gemini_file.write_text(content)
    return True


def remove_gemini_skills(gemini_file: Path, module_name: str) -> bool:
    """
    Remove skill entries for a module from GEMINI.md.

    Args:
        gemini_file: Path to GEMINI.md
        module_name: Name of the module to remove

    Returns:
        True if successful
    """
    if not gemini_file.exists():
        return True

    content = gemini_file.read_text()

    if GEMINI_START_MARKER not in content or GEMINI_END_MARKER not in content:
        return True

    start_idx = content.index(GEMINI_START_MARKER)
    end_idx = content.index(GEMINI_END_MARKER) + len(GEMINI_END_MARKER)
    existing_section = content[start_idx:end_idx]

    # Parse and remove module
    section_content = existing_section[len(GEMINI_START_MARKER):-len(GEMINI_END_MARKER)]
    lines = section_content.split('\n')
    new_lines = []
    skip_until_next_module = False

    for line in lines:
        if line.startswith('### '):
            if line == f'### {module_name}':
                skip_until_next_module = True
                continue
            else:
                skip_until_next_module = False
        if not skip_until_next_module:
            new_lines.append(line)

    new_section = GEMINI_START_MARKER + '\n'.join(new_lines) + GEMINI_END_MARKER
    content = content[:start_idx] + new_section + content[end_idx:]

    gemini_file.write_text(content)
    return True


def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
) -> int:
    """
    Install a module's skills to a specific assistant.

    Returns:
        Number of skills installed
    """
    # Gemini CLI can only read files within the project workspace
    if assistant == 'gemini-cli' and scope == 'user':
        console.print(f"[yellow]{assistant}[/yellow] -> skipped (user scope not supported)")
        console.print("  Gemini CLI can only read files within project directories.")
        console.print("  Use: lola install <module> -a gemini-cli -s project <path>")
        return 0

    try:
        skill_dest = get_assistant_skill_path(assistant, scope, project_path)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 0

    console.print(f"[bold]{assistant}[/bold] -> {skill_dest}")

    # Copy or link module to local .lola/modules/
    # Gemini needs a copy since it can't follow symlinks outside workspace
    if assistant == 'gemini-cli':
        local_module_path = copy_module_to_local(module, local_modules)
    else:
        local_module_path = link_module_to_local(module, local_modules)

    # Generate assistant-specific files
    installed_skills = []

    if assistant == 'gemini-cli':
        # Gemini: Add entries to GEMINI.md file
        gemini_skills = []
        for skill_rel in module.skills:
            skill_name = Path(skill_rel).name
            source = local_module_path / skill_name
            if source.exists():
                description = get_skill_description(source)
                gemini_skills.append((skill_name, description, source))
                installed_skills.append(skill_name)
                console.print(f"  [green]{skill_name}[/green]")
            else:
                console.print(f"  [red]{skill_name}[/red] (source not found)")

        if gemini_skills:
            update_gemini_md(skill_dest, module.name, gemini_skills, project_path)
    else:
        # Claude/Cursor: Generate individual files
        for skill_rel in module.skills:
            skill_name = Path(skill_rel).name
            source = local_module_path / skill_name

            if assistant == 'cursor':
                success = generate_cursor_rule(source, skill_dest, skill_name)
            else:  # claude-code
                dest = skill_dest / skill_name
                success = generate_claude_skill(source, dest)

            if success:
                console.print(f"  [green]{skill_name}[/green]")
                installed_skills.append(skill_name)
            else:
                console.print(f"  [red]{skill_name}[/red] (source not found)")

    # Record installation
    if installed_skills:
        installation = Installation(
            module_name=module.name,
            assistant=assistant,
            scope=scope,
            project_path=project_path,
            skills=installed_skills,
        )
        registry.add(installation)

    return len(installed_skills)


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

    if not module.skills:
        console.print(f"[yellow]Module '{module_name}' has no skills defined[/yellow]")
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
        console.print(f"    Skills: {', '.join(inst.skills)}")

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
        try:
            skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
        except ValueError:
            console.print(f"[red]Cannot determine path for {inst.assistant}/{inst.scope}[/red]")
            continue

        # Remove generated files
        if inst.assistant == 'gemini-cli':
            # Remove entries from GEMINI.md
            if remove_gemini_skills(skill_dest, module_name):
                console.print(f"[green]Removed from: {skill_dest}[/green]")
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

        # For project scope, also remove the project-local module symlink
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

        local_modules = get_local_modules_path(inst.project_path)

        # Refresh the local copy/symlink from global module
        # Gemini needs a fresh copy, others use symlinks
        if inst.assistant == 'gemini-cli':
            source_module = copy_module_to_local(global_module, local_modules)
        else:
            source_module = link_module_to_local(global_module, local_modules)

        try:
            skill_dest = get_assistant_skill_path(inst.assistant, inst.scope, inst.project_path)
        except ValueError:
            console.print(f"[red]Cannot determine path for {inst.assistant}/{inst.scope}[/red]")
            continue

        console.print(f"[cyan]{inst.module_name}[/cyan] -> {inst.assistant}")

        if inst.assistant == 'gemini-cli':
            # Gemini: Update entries in GEMINI.md
            gemini_skills = []
            for skill_name in inst.skills:
                source = source_module / skill_name
                if source.exists():
                    description = get_skill_description(source)
                    gemini_skills.append((skill_name, description, source))
                    console.print(f"  [green]{skill_name}[/green]")
                else:
                    console.print(f"  [red]{skill_name}[/red] (source not found)")
            if gemini_skills:
                update_gemini_md(skill_dest, inst.module_name, gemini_skills, inst.project_path)
        else:
            for skill_name in inst.skills:
                source = source_module / skill_name

                if inst.assistant == 'cursor':
                    success = generate_cursor_rule(source, skill_dest, skill_name)
                else:
                    dest = skill_dest / skill_name
                    success = generate_claude_skill(source, dest)

                if success:
                    console.print(f"  [green]{skill_name}[/green]")
                else:
                    console.print(f"  [red]{skill_name}[/red] (source not found)")

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
            console.print(f"    Skills: {', '.join(inst.skills)}")
        console.print()
