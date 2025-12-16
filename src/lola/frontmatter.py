"""
Centralized frontmatter parsing using python-frontmatter library.

This module provides consistent frontmatter parsing across lola,
with proper error handling and validation warnings.
"""

import re
from pathlib import Path
from typing import Optional

import frontmatter


def parse(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Full file content (markdown with optional frontmatter)

    Returns:
        Tuple of (frontmatter dict, body content)
    """
    try:
        post = frontmatter.loads(content)
        return dict(post.metadata), post.content
    except Exception:
        # If parsing fails, return empty frontmatter and full content
        return {}, content


def parse_file(file_path: Path) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from a markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        Tuple of (frontmatter dict, body content)
    """
    try:
        post = frontmatter.load(str(file_path))
        return dict(post.metadata), post.content
    except Exception:
        # If parsing fails, return empty frontmatter and file content
        try:
            return {}, file_path.read_text()
        except Exception:
            return {}, ""


def validate_command(command_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in a command .md file.

    Args:
        command_file: Path to the command .md file

    Returns:
        List of warning/error messages (empty if valid)
    """
    errors = []

    try:
        content = command_file.read_text()
    except Exception as e:
        return [f"Cannot read file: {e}"]

    # Frontmatter is optional for commands but recommended
    if not content.startswith("---"):
        return ["Warning: Missing frontmatter with 'description' field (recommended)"]

    # Try to parse and check for YAML errors
    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
    except Exception as e:
        # Provide helpful message for common YAML issues
        error_msg = str(e)
        if "[" in error_msg or "found" in error_msg.lower():
            errors.append(
                "Error: YAML parsing failed - if using brackets in values like "
                "'[--flag]', wrap them in quotes: '\"[--flag]\"'"
            )
        else:
            errors.append(f"Error: Invalid YAML frontmatter - {e}")
        return errors

    # description is recommended but not strictly required
    if not metadata.get("description"):
        errors.append("Warning: Missing 'description' field (recommended)")

    return errors


def validate_skill(skill_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in a SKILL.md file.

    Args:
        skill_file: Path to the SKILL.md file

    Returns:
        List of warning/error messages (empty if valid)
    """
    errors = []

    try:
        content = skill_file.read_text()
    except Exception as e:
        return [f"Cannot read file: {e}"]

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (required)")
        return errors

    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
    except Exception as e:
        errors.append(f"Error: Invalid YAML frontmatter - {e}")
        return errors

    if not metadata.get("description"):
        errors.append("Missing required 'description' field in frontmatter")

    return errors


def validate_agent(agent_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in an agent .md file.

    Args:
        agent_file: Path to the agent .md file

    Returns:
        List of warning/error messages (empty if valid)
    """
    errors = []

    try:
        content = agent_file.read_text()
    except Exception as e:
        return [f"Cannot read file: {e}"]

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (required)")
        return errors

    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
    except Exception as e:
        errors.append(f"Error: Invalid YAML frontmatter - {e}")
        return errors

    if not metadata.get("description"):
        errors.append("Missing required 'description' field in frontmatter")

    return errors


def get_metadata(file_path: Path) -> dict:
    """
    Get just the frontmatter metadata from a file.

    Args:
        file_path: Path to the markdown file

    Returns:
        Frontmatter metadata dict (empty if none or error)
    """
    metadata, _ = parse_file(file_path)
    return metadata


def get_description(file_path: Path) -> Optional[str]:
    """
    Get the description field from a file's frontmatter.

    Args:
        file_path: Path to the markdown file

    Returns:
        Description string or None if not found
    """
    metadata = get_metadata(file_path)
    return metadata.get("description")


def has_positional_args(content: str) -> bool:
    """Check if content uses positional argument placeholders ($1, $2, etc.)."""
    return bool(re.search(r"\$\d+", content))
