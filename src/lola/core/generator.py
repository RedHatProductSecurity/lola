"""
Generator functions for creating assistant-specific files.

This module handles generating skill and command files for each
supported AI assistant (Claude Code, Cursor, Gemini CLI).
"""

import shutil
from pathlib import Path

from lola.command_converters import (
    command_to_claude,
    command_to_cursor,
    command_to_gemini,
    get_command_filename,
)
from lola.converters import skill_to_claude, skill_to_cursor_mdc


def get_skill_description(source_path: Path) -> str:
    """Extract description from a SKILL.md file's frontmatter."""
    from lola import frontmatter as fm

    skill_file = source_path / "SKILL.md"
    if not skill_file.exists():
        return ""

    return fm.get_description(skill_file) or ""


# =============================================================================
# Skill Generators
# =============================================================================


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
        (dest_path / "SKILL.md").write_text(content)

    # Copy supporting files (not SKILL.md)
    for item in source_path.iterdir():
        if item.name == "SKILL.md":
            continue
        dest_item = dest_path / item.name
        if item.is_dir():
            if dest_item.exists():
                shutil.rmtree(dest_item)
            shutil.copytree(item, dest_item)
        else:
            shutil.copy2(item, dest_item)

    return True


def generate_cursor_rule(
    source_path: Path, rules_dir: Path, skill_name: str, project_path: str | None
) -> bool:
    """
    Generate Cursor .mdc rule from source.

    Args:
        source_path: Path to source skill in .lola/modules/
        rules_dir: Path to .cursor/rules/
        skill_name: Name of the skill
        project_path: Path to the project root (for relative path computation)

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    rules_dir.mkdir(parents=True, exist_ok=True)

    # Compute relative path from project root to the skill source
    if project_path:
        try:
            relative_source = source_path.relative_to(Path(project_path))
            assets_path = str(relative_source)
        except ValueError:
            # Fallback to absolute path if not relative to project
            assets_path = str(source_path)
    else:
        assets_path = str(source_path)

    # Generate .mdc file with paths pointing to source
    content = skill_to_cursor_mdc(source_path, assets_path)
    if content:
        mdc_file = rules_dir / f"{skill_name}.mdc"
        mdc_file.write_text(content)

    return True


# =============================================================================
# Command Generators
# =============================================================================


def generate_claude_command(
    source_path: Path, dest_dir: Path, cmd_name: str, module_name: str
) -> bool:
    """
    Generate Claude command file from source.

    Args:
        source_path: Path to source command file (.md)
        dest_dir: Path to .claude/commands/
        cmd_name: Name of the command
        module_name: Name of the module (for prefixing)

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    content = command_to_claude(source_path)
    if content:
        filename = get_command_filename("claude-code", module_name, cmd_name)
        (dest_dir / filename).write_text(content)
        return True
    return False


def generate_cursor_command(
    source_path: Path, dest_dir: Path, cmd_name: str, module_name: str
) -> bool:
    """
    Generate Cursor command file from source.

    Args:
        source_path: Path to source command file (.md)
        dest_dir: Path to .cursor/commands/
        cmd_name: Name of the command
        module_name: Name of the module (for prefixing)

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    content = command_to_cursor(source_path)
    if content:
        filename = get_command_filename("cursor", module_name, cmd_name)
        (dest_dir / filename).write_text(content)
        return True
    return False


def generate_gemini_command(
    source_path: Path, dest_dir: Path, cmd_name: str, module_name: str
) -> bool:
    """
    Generate Gemini CLI command file (TOML format) from source.

    Args:
        source_path: Path to source command file (.md)
        dest_dir: Path to .gemini/commands/
        cmd_name: Name of the command
        module_name: Name of the module (for prefixing)

    Returns:
        True if successful
    """
    if not source_path.exists():
        return False

    dest_dir.mkdir(parents=True, exist_ok=True)

    content = command_to_gemini(source_path)
    if content:
        filename = get_command_filename("gemini-cli", module_name, cmd_name)
        (dest_dir / filename).write_text(content)
        return True
    return False


# =============================================================================
# Gemini MD Helpers
# =============================================================================

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


def update_gemini_md(
    gemini_file: Path,
    module_name: str,
    skills: list[tuple[str, str, Path]],
    project_path: str | None,
) -> bool:
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

    project_root = Path(project_path) if project_path else None

    # Build the skills section for this module
    skills_block = f"\n### {module_name}\n\n"
    for skill_name, description, skill_path in skills:
        # Use relative path from project root for Gemini compatibility
        if project_root:
            try:
                relative_path = skill_path.relative_to(project_root)
                skill_md_path = relative_path / "SKILL.md"
            except ValueError:
                # Fallback to absolute path if not relative to project
                skill_md_path = skill_path / "SKILL.md"
        else:
            skill_md_path = skill_path / "SKILL.md"
        skills_block += f"#### {skill_name}\n"
        skills_block += f"**When to use:** {description}\n"
        skills_block += (
            f"**Instructions:** Read `{skill_md_path}` for detailed guidance.\n\n"
        )

    # Find or create the lola-managed section
    if GEMINI_START_MARKER in content and GEMINI_END_MARKER in content:
        # Extract existing lola section
        start_idx = content.index(GEMINI_START_MARKER)
        end_idx = content.index(GEMINI_END_MARKER) + len(GEMINI_END_MARKER)
        existing_section = content[start_idx:end_idx]

        # Parse existing modules in the section
        section_content = existing_section[
            len(GEMINI_START_MARKER) : -len(GEMINI_END_MARKER)
        ]

        # Remove old entry for this module if exists
        lines = section_content.split("\n")
        new_lines = []
        skip_until_next_module = False
        for line in lines:
            if line.startswith("### "):
                if line == f"### {module_name}":
                    skip_until_next_module = True
                    continue
                else:
                    skip_until_next_module = False
            if not skip_until_next_module:
                new_lines.append(line)

        # Add new module entry
        new_section = (
            GEMINI_START_MARKER
            + "\n".join(new_lines)
            + skills_block
            + GEMINI_END_MARKER
        )
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
    section_content = existing_section[
        len(GEMINI_START_MARKER) : -len(GEMINI_END_MARKER)
    ]
    lines = section_content.split("\n")
    new_lines = []
    skip_until_next_module = False

    for line in lines:
        if line.startswith("### "):
            if line == f"### {module_name}":
                skip_until_next_module = True
                continue
            else:
                skip_until_next_module = False
        if not skip_until_next_module:
            new_lines.append(line)

    new_section = GEMINI_START_MARKER + "\n".join(new_lines) + GEMINI_END_MARKER
    content = content[:start_idx] + new_section + content[end_idx:]

    gemini_file.write_text(content)
    return True
