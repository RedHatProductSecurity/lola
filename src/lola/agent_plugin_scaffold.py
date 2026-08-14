"""Scaffolding for Agent Plugins v1 packages."""

from dataclasses import dataclass
import json
from pathlib import Path
import re

from lola.agent_plugins import (
    LOLA_NAMESPACE,
    MCP_SCHEMA,
    PLUGIN_SCHEMA,
    validate_plugin_name,
)
from lola.config import SKILL_FILE
from lola.exceptions import ValidationError


@dataclass(frozen=True)
class ScaffoldOptions:
    """Options for an Agent Plugins scaffold."""

    skill_name: str | None
    command_name: str | None
    agent_name: str | None
    include_mcps: bool
    include_instructions: bool


def plugin_name_from_directory(dirname: str) -> str:
    """Derive an Agent Plugins name from a directory name.

    Directory names are not constrained the way manifest names are
    (``My_Project`` is a perfectly good folder), so slugify rather than
    reject when the name was inferred instead of typed.
    """
    slug = re.sub(r"[^a-z0-9.-]+", "-", dirname.lower())
    slug = re.sub(r"-{2,}", "-", slug)
    slug = re.sub(r"\.{2,}", ".", slug)
    return slug.strip("-.")[:64].strip("-.")


def scaffold_agent_plugin(
    root: Path,
    name: str,
    options: ScaffoldOptions,
) -> None:
    """Create a conformant Agent Plugins package with Lola extensions."""
    if not validate_plugin_name(name):
        raise ValidationError(name, ["invalid Agent Plugins name"])

    root.mkdir(parents=True, exist_ok=True)
    extension = root / LOLA_NAMESPACE
    skills = root / "skills"
    commands = extension / "commands"
    agents = extension / "agents"
    skills.mkdir(exist_ok=True)
    commands.mkdir(parents=True, exist_ok=True)
    agents.mkdir(exist_ok=True)

    manifest = {
        "$schema": PLUGIN_SCHEMA,
        "name": name,
        "version": "0.1.0",
        "description": "[REPLACE: Brief plugin description]",
        "extensions": {
            LOLA_NAMESPACE: {
                "commands": f"./{LOLA_NAMESPACE}/commands",
                "agents": f"./{LOLA_NAMESPACE}/agents",
                "instructions": f"./{LOLA_NAMESPACE}/AGENTS.md",
            }
        },
    }
    (root / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if options.skill_name:
        skill = skills / options.skill_name
        skill.mkdir(exist_ok=True)
        (skill / SKILL_FILE).write_text(
            "---\n"
            f"name: {options.skill_name}\n"
            "description: [REPLACE: Describe this skill and when to use it]\n"
            "---\n\n"
            f"# {_title_case(options.skill_name)}\n\n"
            "[REPLACE: Skill instructions]\n"
        )
    if options.command_name:
        (commands / f"{options.command_name}.md").write_text(
            "---\n"
            "description: [REPLACE: Describe this command]\n"
            "---\n\n"
            "[REPLACE: Command instructions]\n"
        )
    if options.agent_name:
        (agents / f"{options.agent_name}.md").write_text(
            "---\n"
            "description: [REPLACE: Describe this agent]\n"
            "---\n\n"
            "[REPLACE: Agent instructions]\n"
        )
    if options.include_mcps:
        mcp = {"$schema": MCP_SCHEMA, "mcpServers": {}}
        (root / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")
    if options.include_instructions:
        (extension / "AGENTS.md").write_text(
            f"# {_title_case(name)}\n\n"
            "[REPLACE: Instructions for agents using this plugin]\n"
        )
    (root / "README.md").write_text(
        f"# {_title_case(name)}\n\n[REPLACE: Describe this Agent Plugins package]\n"
    )


def _title_case(value: str) -> str:
    return value.replace("-", " ").replace(".", " ").title()
