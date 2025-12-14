"""
command_converters:
    Convert command files between different AI assistant formats
"""

import re
from pathlib import Path
from typing import Optional

from lola import frontmatter as fm


def parse_command_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from a command .md file.

    Args:
        content: Full file content

    Returns:
        Tuple of (frontmatter dict, body content)
    """
    return fm.parse(content)


def has_positional_args(content: str) -> bool:
    """
    Check if content uses positional argument placeholders ($1, $2, etc.).

    Args:
        content: The command prompt content

    Returns:
        True if positional args are used
    """
    # Match $1, $2, etc. but not $ARGUMENTS
    return bool(re.search(r"\$\d+", content))


def convert_to_gemini_args(content: str) -> str:
    """
    Convert argument placeholders for Gemini CLI format.

    - Replaces $ARGUMENTS with {{args}}
    - If positional args ($1, $2, etc.) exist, prepends "Arguments: {{args}}"
      and keeps the $1, $2 placeholders as-is for LLM to infer

    Args:
        content: The command prompt content

    Returns:
        Content with converted argument syntax
    """
    # Replace $ARGUMENTS with {{args}}
    result = content.replace("$ARGUMENTS", "{{args}}")

    # If positional args exist, prepend the Arguments block
    if has_positional_args(result):
        result = f"Arguments: {{{{args}}}}\n\n{result}"

    return result


def command_to_claude(command_path: Path) -> Optional[str]:
    """
    Return command content for Claude Code (pass through).

    Claude Code uses markdown with frontmatter - the same format as source.

    Args:
        command_path: Path to the command .md file

    Returns:
        Command file content, or None if not found
    """
    if not command_path.exists():
        return None
    return command_path.read_text()


def command_to_cursor(command_path: Path) -> Optional[str]:
    """
    Convert a command file to Cursor format.

    Cursor also uses markdown format similar to Claude Code.

    Args:
        command_path: Path to the command .md file

    Returns:
        Command file content, or None if not found
    """
    if not command_path.exists():
        return None
    return command_path.read_text()


def command_to_gemini(command_path: Path) -> Optional[str]:
    """
    Convert a command file to Gemini CLI TOML format.

    Args:
        command_path: Path to the command .md file

    Returns:
        TOML formatted content, or None if not found
    """
    if not command_path.exists():
        return None

    content = command_path.read_text()
    frontmatter, body = parse_command_frontmatter(content)

    description = frontmatter.get("description", "")

    # Convert argument placeholders for Gemini
    prompt = convert_to_gemini_args(body)

    # Escape description for TOML (double quotes)
    description_escaped = description.replace("\\", "\\\\").replace('"', '\\"')

    # Build TOML content
    toml_lines = [
        f'description = "{description_escaped}"',
        'prompt = """',
        prompt.rstrip(),
        '"""',
    ]

    return "\n".join(toml_lines)


def get_command_filename(assistant: str, module_name: str, command_name: str) -> str:
    """
    Get the appropriate command filename for an assistant.

    Args:
        assistant: Name of the AI assistant
        module_name: Name of the module (for prefixing)
        command_name: Name of the command

    Returns:
        Filename like 'module-command.md' or 'module-command.toml'
    """
    base_name = f"{module_name}-{command_name}"
    if assistant == "gemini-cli":
        return f"{base_name}.toml"
    return f"{base_name}.md"
