"""
targets:
    Target assistants + installation logic for lola.

This file intentionally centralizes:
- Supported assistant targets + their project-scoped locations
- Generation of target-specific skill/command/agent files
- Install orchestration helpers (copy local module, record installations)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console

import lola.config as config
from lola.models import Installation, InstallationRegistry, Module
from lola.parsers import (
    has_positional_args,
    parse_command_frontmatter,
    skill_to_claude,
    skill_to_cursor_mdc,
)

console = Console()

#
# Command target-formatting helpers (belong in targets, not parsers)
#


def get_command_filename(assistant: str, module_name: str, command_name: str) -> str:
    """Get assistant command filename."""
    base_name = f"{module_name}-{command_name}"
    if assistant == "gemini-cli":
        return f"{base_name}.toml"
    return f"{base_name}.md"


def convert_to_gemini_args(content: str) -> str:
    """
    Convert argument placeholders for Gemini CLI format.

    - Replaces $ARGUMENTS with {{args}}
    - If positional args exist, prepends "Arguments: {{args}}"
    """
    result = content.replace("$ARGUMENTS", "{{args}}")
    if has_positional_args(result):
        result = f"Arguments: {{{{args}}}}\n\n{result}"
    return result


def command_to_claude(command_path: Path) -> Optional[str]:
    """Return command content for Claude Code (pass through)."""
    if not command_path.exists():
        return None
    return command_path.read_text()


def command_to_cursor(command_path: Path) -> Optional[str]:
    """Return command content for Cursor (pass through)."""
    if not command_path.exists():
        return None
    return command_path.read_text()


def command_to_gemini(command_path: Path) -> Optional[str]:
    """Convert a command file to Gemini CLI TOML format."""
    if not command_path.exists():
        return None

    content = command_path.read_text()
    frontmatter, body = parse_command_frontmatter(content)
    description = frontmatter.get("description", "")
    prompt = convert_to_gemini_args(body)

    description_escaped = description.replace("\\", "\\\\").replace('"', '\\"')
    toml_lines = [
        f'description = "{description_escaped}"',
        'prompt = """',
        prompt.rstrip(),
        '"""',
    ]
    return "\n".join(toml_lines)


# =============================================================================
# Target definitions (project-scope only)
# =============================================================================


ASSISTANTS: dict[str, dict[str, object]] = {
    "claude-code": {
        "skills_project": lambda path: Path(path) / ".claude" / "skills",
        "commands_project": lambda path: Path(path) / ".claude" / "commands",
        "agents_project": lambda path: Path(path) / ".claude" / "agents",
    },
    "cursor": {
        "skills_project": lambda path: Path(path) / ".cursor" / "rules",
        "commands_project": lambda path: Path(path) / ".cursor" / "commands",
        "agents_project": lambda path: Path(path) / ".cursor" / "agents",
    },
    "gemini-cli": {
        # Gemini uses GEMINI.md for skills
        "skills_project": lambda path: Path(path) / "GEMINI.md",
        "commands_project": lambda path: Path(path) / ".gemini" / "commands",
    },
    "opencode": {
        "skills_project": lambda path: Path(path) / ".opencode" / "skills",
        "commands_project": lambda path: Path(path) / ".opencode" / "commands",
        "agents_project": lambda path: Path(path) / ".opencode" / "agent",
    },
}


def get_assistant_skill_path(assistant: str, scope: str, project_path: str | None = None) -> Path:
    if assistant not in ASSISTANTS:
        raise ValueError(f"Unknown assistant: {assistant}. Supported: {list(ASSISTANTS.keys())}")
    if scope != "project":
        raise ValueError("Only project scope is supported")
    if not project_path:
        raise ValueError("Project path required for project scope")
    return ASSISTANTS[assistant]["skills_project"](project_path)  # type: ignore[index]


def get_assistant_command_path(assistant: str, scope: str, project_path: str | None = None) -> Path:
    if assistant not in ASSISTANTS:
        raise ValueError(f"Unknown assistant: {assistant}. Supported: {list(ASSISTANTS.keys())}")
    if scope != "project":
        raise ValueError("Only project scope is supported")
    if not project_path:
        raise ValueError("Project path required for project scope")
    return ASSISTANTS[assistant]["commands_project"](project_path)  # type: ignore[index]


def get_assistant_agent_path(assistant: str, scope: str, project_path: str | None = None) -> Path:
    if assistant not in ASSISTANTS:
        raise ValueError(f"Unknown assistant: {assistant}. Supported: {list(ASSISTANTS.keys())}")
    config = ASSISTANTS[assistant]
    if "agents_project" not in config:
        raise ValueError(f"Assistant '{assistant}' does not support agents")
    if scope != "project":
        raise ValueError("Only project scope is supported")
    if not project_path:
        raise ValueError("Project path required for project scope")
    return config["agents_project"](project_path)  # type: ignore[index]


# =============================================================================
# Registry
# =============================================================================


def get_registry() -> InstallationRegistry:
    return InstallationRegistry(config.INSTALLED_FILE)


# =============================================================================
# Generators
# =============================================================================


def get_skill_description(source_path: Path) -> str:
    from lola import frontmatter as fm

    skill_file = source_path / "SKILL.md"
    if not skill_file.exists():
        return ""
    return fm.get_description(skill_file) or ""


def generate_claude_skill(source_path: Path, dest_path: Path) -> bool:
    if not source_path.exists():
        return False
    dest_path.mkdir(parents=True, exist_ok=True)

    content = skill_to_claude(source_path)
    if content:
        (dest_path / "SKILL.md").write_text(content)

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


def generate_cursor_rule(source_path: Path, rules_dir: Path, skill_name: str, project_path: str | None) -> bool:
    if not source_path.exists():
        return False
    rules_dir.mkdir(parents=True, exist_ok=True)

    if project_path:
        try:
            relative_source = source_path.relative_to(Path(project_path))
            assets_path = str(relative_source)
        except ValueError:
            assets_path = str(source_path)
    else:
        assets_path = str(source_path)

    content = skill_to_cursor_mdc(source_path, assets_path)
    if content:
        (rules_dir / f"{skill_name}.mdc").write_text(content)
    return True


def generate_cursor_agent(source_path: Path, dest_dir: Path, agent_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text()

    # Add model: inherit to frontmatter
    frontmatter, body = parse_command_frontmatter(content)
    frontmatter["model"] = "inherit"

    import yaml

    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    filename = f"{module_name}-{agent_name}.md"
    (dest_dir / filename).write_text(content)
    return True


def get_agent_filename(assistant: str, module_name: str, agent_name: str) -> str:
    """Get the appropriate agent filename for an assistant."""
    _ = assistant
    return f"{module_name}-{agent_name}.md"


def generate_claude_command(source_path: Path, dest_dir: Path, cmd_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = command_to_claude(source_path)
    if not content:
        return False
    filename = get_command_filename("claude-code", module_name, cmd_name)
    (dest_dir / filename).write_text(content)
    return True


def generate_cursor_command(source_path: Path, dest_dir: Path, cmd_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = command_to_cursor(source_path)
    if not content:
        return False
    filename = get_command_filename("cursor", module_name, cmd_name)
    (dest_dir / filename).write_text(content)
    return True


def generate_gemini_command(source_path: Path, dest_dir: Path, cmd_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = command_to_gemini(source_path)
    if not content:
        return False
    filename = get_command_filename("gemini-cli", module_name, cmd_name)
    (dest_dir / filename).write_text(content)
    return True


def generate_claude_agent(source_path: Path, dest_dir: Path, agent_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text()

    # Add model: inherit to frontmatter for Claude Code
    frontmatter, body = parse_command_frontmatter(content)
    frontmatter["model"] = "inherit"

    # Rebuild content with updated frontmatter
    import yaml

    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    filename = get_agent_filename("claude-code", module_name, agent_name)
    (dest_dir / filename).write_text(content)
    return True


def generate_opencode_skill(source_path: Path, dest_dir: Path, skill_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = skill_to_claude(source_path)
    if not content:
        return False
    (dest_dir / f"{skill_name}.md").write_text(content)
    return True


def generate_opencode_command(source_path: Path, dest_dir: Path, cmd_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = command_to_claude(source_path)
    if not content:
        return False
    filename = get_command_filename("opencode", module_name, cmd_name)
    (dest_dir / filename).write_text(content)
    return True


def generate_opencode_agent(source_path: Path, dest_dir: Path, agent_name: str, module_name: str) -> bool:
    if not source_path.exists():
        return False
    dest_dir.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text()

    # Add mode: subagent to frontmatter for OpenCode
    frontmatter, body = parse_command_frontmatter(content)
    frontmatter["mode"] = "subagent"

    import yaml

    frontmatter_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip()
    content = f"---\n{frontmatter_str}\n---\n{body}"

    filename = get_agent_filename("opencode", module_name, agent_name)
    (dest_dir / filename).write_text(content)
    return True


# =============================================================================
# GEMINI.md helpers
# =============================================================================


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
    if gemini_file.exists():
        content = gemini_file.read_text()
    else:
        gemini_file.parent.mkdir(parents=True, exist_ok=True)
        content = ""

    project_root = Path(project_path) if project_path else None

    skills_block = f"\n### {module_name}\n\n"
    for skill_name, description, skill_path in skills:
        if project_root:
            try:
                relative_path = skill_path.relative_to(project_root)
                skill_md_path = relative_path / "SKILL.md"
            except ValueError:
                skill_md_path = skill_path / "SKILL.md"
        else:
            skill_md_path = skill_path / "SKILL.md"
        skills_block += f"#### {skill_name}\n"
        skills_block += f"**When to use:** {description}\n"
        skills_block += f"**Instructions:** Read `{skill_md_path}` for detailed guidance.\n\n"

    if GEMINI_START_MARKER in content and GEMINI_END_MARKER in content:
        start_idx = content.index(GEMINI_START_MARKER)
        end_idx = content.index(GEMINI_END_MARKER) + len(GEMINI_END_MARKER)
        existing_section = content[start_idx:end_idx]
        section_content = existing_section[len(GEMINI_START_MARKER) : -len(GEMINI_END_MARKER)]

        lines = section_content.split("\n")
        new_lines: list[str] = []
        skip_until_next_module = False
        for line in lines:
            if line.startswith("### "):
                if line == f"### {module_name}":
                    skip_until_next_module = True
                    continue
                skip_until_next_module = False
            if not skip_until_next_module:
                new_lines.append(line)

        new_section = GEMINI_START_MARKER + "\n".join(new_lines) + skills_block + GEMINI_END_MARKER
        content = content[:start_idx] + new_section + content[end_idx:]
    else:
        lola_section = f"\n\n{GEMINI_HEADER}{GEMINI_START_MARKER}\n{skills_block}{GEMINI_END_MARKER}\n"
        content = content.rstrip() + lola_section

    gemini_file.write_text(content)
    return True


def remove_gemini_skills(gemini_file: Path, module_name: str) -> bool:
    if not gemini_file.exists():
        return True
    content = gemini_file.read_text()
    if GEMINI_START_MARKER not in content or GEMINI_END_MARKER not in content:
        return True

    start_idx = content.index(GEMINI_START_MARKER)
    end_idx = content.index(GEMINI_END_MARKER) + len(GEMINI_END_MARKER)
    existing_section = content[start_idx:end_idx]
    section_content = existing_section[len(GEMINI_START_MARKER) : -len(GEMINI_END_MARKER)]

    lines = section_content.split("\n")
    new_lines: list[str] = []
    skip_until_next_module = False
    for line in lines:
        if line.startswith("### "):
            if line == f"### {module_name}":
                skip_until_next_module = True
                continue
            skip_until_next_module = False
        if not skip_until_next_module:
            new_lines.append(line)

    new_section = GEMINI_START_MARKER + "\n".join(new_lines) + GEMINI_END_MARKER
    content = content[:start_idx] + new_section + content[end_idx:]
    gemini_file.write_text(content)
    return True


# =============================================================================
# Install helpers
# =============================================================================


def copy_module_to_local(module: Module, local_modules_path: Path) -> Path:
    dest = local_modules_path / module.name
    if dest.resolve() == module.path.resolve():
        return dest

    local_modules_path.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    shutil.copytree(module.path, dest)
    return dest


def _skill_source_dir(local_module_path: Path, skill_name: str) -> Path:
    preferred = local_module_path / "skills" / skill_name
    if preferred.exists():
        return preferred
    return local_module_path / skill_name


def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
    verbose: bool = False,
) -> int:
    local_module_path = copy_module_to_local(module, local_modules)

    installed_skills: list[str] = []
    installed_commands: list[str] = []
    installed_agents: list[str] = []

    failed_skills: list[str] = []
    failed_commands: list[str] = []
    failed_agents: list[str] = []

    # Skills
    if module.skills:
        try:
            skill_dest = get_assistant_skill_path(assistant, scope, project_path)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            skill_dest = None

        if skill_dest:
            if assistant == "gemini-cli":
                gemini_skills: list[tuple[str, str, Path]] = []
                for s in module.skills:
                    source = _skill_source_dir(local_module_path, s)
                    prefixed = f"{module.name}-{s}"
                    if source.exists():
                        gemini_skills.append((s, get_skill_description(source), source))
                        installed_skills.append(prefixed)
                    else:
                        failed_skills.append(s)
                if gemini_skills:
                    update_gemini_md(skill_dest, module.name, gemini_skills, project_path)
            elif assistant == "opencode":
                for s in module.skills:
                    source = _skill_source_dir(local_module_path, s)
                    prefixed = f"{module.name}-{s}"
                    if generate_opencode_skill(source, skill_dest, prefixed):
                        installed_skills.append(prefixed)
                    else:
                        failed_skills.append(s)
            else:
                for s in module.skills:
                    source = _skill_source_dir(local_module_path, s)
                    prefixed = f"{module.name}-{s}"
                    if assistant == "cursor":
                        ok = generate_cursor_rule(source, skill_dest, prefixed, project_path)
                    else:
                        ok = generate_claude_skill(source, skill_dest / prefixed)
                    if ok:
                        installed_skills.append(prefixed)
                    else:
                        failed_skills.append(s)

    # Commands
    if module.commands:
        try:
            command_dest = get_assistant_command_path(assistant, scope, project_path)
        except ValueError as e:
            console.print(f"[red]Commands: {e}[/red]")
            command_dest = None

        if command_dest:
            commands_dir = local_module_path / "commands"
            for cmd in module.commands:
                source = commands_dir / f"{cmd}.md"
                if assistant == "gemini-cli":
                    ok = generate_gemini_command(source, command_dest, cmd, module.name)
                elif assistant == "cursor":
                    ok = generate_cursor_command(source, command_dest, cmd, module.name)
                elif assistant == "opencode":
                    ok = generate_opencode_command(source, command_dest, cmd, module.name)
                else:
                    ok = generate_claude_command(source, command_dest, cmd, module.name)
                if ok:
                    installed_commands.append(cmd)
                else:
                    failed_commands.append(cmd)

    # Agents
    if module.agents:
        try:
            agent_dest = get_assistant_agent_path(assistant, scope, project_path)
        except ValueError as e:
            console.print(f"[red]Agents: {e}[/red]")
            agent_dest = None

        if agent_dest:
            agents_dir = local_module_path / "agents"
            for a in module.agents:
                source = agents_dir / f"{a}.md"
                if assistant == "claude-code":
                    ok = generate_claude_agent(source, agent_dest, a, module.name)
                elif assistant == "cursor":
                    ok = generate_cursor_agent(source, agent_dest, a, module.name)
                elif assistant == "opencode":
                    ok = generate_opencode_agent(source, agent_dest, a, module.name)
                else:
                    ok = False
                if ok:
                    installed_agents.append(a)
                else:
                    failed_agents.append(a)

    # Summary
    if installed_skills or installed_commands or installed_agents:
        parts: list[str] = []
        if installed_skills:
            parts.append(f"{len(installed_skills)} skill{'s' if len(installed_skills) != 1 else ''}")
        if installed_commands:
            parts.append(f"{len(installed_commands)} command{'s' if len(installed_commands) != 1 else ''}")
        if installed_agents:
            parts.append(f"{len(installed_agents)} agent{'s' if len(installed_agents) != 1 else ''}")
        console.print(f"  [green]{assistant}[/green] [dim]({', '.join(parts)})[/dim]")

        if verbose:
            for skill in installed_skills:
                console.print(f"    [green]{skill}[/green]")
            for cmd in installed_commands:
                console.print(f"    [green]/{module.name}-{cmd}[/green]")
            for agent in installed_agents:
                console.print(f"    [green]@{module.name}-{agent}[/green]")

        if failed_skills or failed_commands or failed_agents:
            for skill in failed_skills:
                console.print(f"    [red]{skill}[/red] [dim](source not found)[/dim]")
            for cmd in failed_commands:
                console.print(f"    [red]{cmd}[/red] [dim](source not found)[/dim]")
            for agent in failed_agents:
                console.print(f"    [red]{agent}[/red] [dim](source not found)[/dim]")

        registry.add(
            Installation(
                module_name=module.name,
                assistant=assistant,
                scope=scope,
                project_path=project_path,
                skills=installed_skills,
                commands=installed_commands,
                agents=installed_agents,
            )
        )

    return len(installed_skills) + len(installed_commands) + len(installed_agents)


