"""
converters:
    Convert skill files between different AI assistant formats
"""

import re
from pathlib import Path
from typing import Optional

from lola import frontmatter as fm


def parse_skill_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from a SKILL.md file.

    Args:
        content: Full file content

    Returns:
        Tuple of (frontmatter dict, body content)
    """
    return fm.parse(content)


def rewrite_relative_paths(content: str, assets_path: str) -> str:
    """
    Rewrite relative paths in content to point to the assets location.

    Handles patterns like:
    - ./scripts/foo.sh -> /path/to/assets/scripts/foo.sh
    - ../templates/bar.md -> /path/to/assets/templates/bar.md
    - scripts/foo.sh -> /path/to/assets/scripts/foo.sh (in code blocks)

    Args:
        content: The skill content
        assets_path: Absolute path to where assets are stored

    Returns:
        Content with rewritten paths
    """
    # Pattern to match relative paths in various contexts
    # Matches: ./path, ../path, or bare paths in code blocks/commands
    patterns = [
        # ./relative/path or ../relative/path
        (r'(\s|^|"|\'|\(|`)(\.\./[^\s"\')\]`]+)', r"\1" + assets_path + r"/\2"),
        (r'(\s|^|"|\'|\(|`)(\./([^\s"\')\]`]+))', r"\1" + assets_path + r"/\3"),
    ]

    result = content
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)

    # Clean up any double slashes (except in URLs)
    result = re.sub(r"(?<!:)//+", "/", result)

    return result


def skill_to_cursor_mdc(
    skill_path: Path, assets_path: Optional[str] = None
) -> Optional[str]:
    """
    Convert a SKILL.md file to Cursor MDC format.

    Args:
        skill_path: Path to the skill directory containing SKILL.md
        assets_path: Path where supporting files will be stored (for path rewriting)

    Returns:
        MDC file content, or None if conversion fails
    """
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return None

    content = skill_file.read_text()
    frontmatter, body = parse_skill_frontmatter(content)

    # Rewrite relative paths if assets_path provided
    if assets_path:
        body = rewrite_relative_paths(body, assets_path)

    # Build MDC content
    mdc_lines = ["---"]
    mdc_lines.append(f"description: {frontmatter.get('description', '')}")
    mdc_lines.append("globs:")
    mdc_lines.append("alwaysApply: false")
    mdc_lines.append("---")
    mdc_lines.append("")
    mdc_lines.append(body)

    return "\n".join(mdc_lines)


def skill_to_claude(skill_path: Path) -> Optional[str]:
    """
    Return SKILL.md content for Claude Code (no conversion needed).

    Args:
        skill_path: Path to the skill directory containing SKILL.md

    Returns:
        Skill file content, or None if not found
    """
    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        return None
    return skill_file.read_text()


def skill_to_gemini(skill_path: Path) -> Optional[str]:
    """
    Convert a SKILL.md file to Gemini CLI format.

    For now, Gemini uses the same format as Claude.

    Args:
        skill_path: Path to the skill directory containing SKILL.md

    Returns:
        Skill file content, or None if conversion fails
    """
    return skill_to_claude(skill_path)


def get_skill_filename(assistant: str, skill_name: str) -> str:
    """Get the appropriate skill filename for an assistant."""
    if assistant == "cursor":
        return f"{skill_name}.mdc"
    return "SKILL.md"


def is_flat_file_assistant(assistant: str) -> bool:
    """Check if the assistant uses flat files instead of directories."""
    return assistant == "cursor"
