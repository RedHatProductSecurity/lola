"""
models:
    Data models for lola modules, skills, and installations
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

from lola.config import SKILL_FILE
from lola import frontmatter as fm


@dataclass
class Skill:
    """Represents a skill within a module."""

    name: str
    path: Path
    description: Optional[str] = None

    @classmethod
    def from_path(cls, skill_path: Path) -> "Skill":
        """Load a skill from its directory path."""
        skill_file = skill_path / SKILL_FILE
        description = None

        if skill_file.exists():
            description = fm.get_description(skill_file)

        return cls(name=skill_path.name, path=skill_path, description=description)


@dataclass
class Command:
    """Represents a slash command within a module."""

    name: str
    path: Path
    description: Optional[str] = None
    argument_hint: Optional[str] = None

    @classmethod
    def from_path(cls, command_path: Path) -> "Command":
        """Load a command from its file path."""
        description = None
        argument_hint = None

        if command_path.exists():
            metadata = fm.get_metadata(command_path)
            description = metadata.get("description")
            argument_hint = metadata.get("argument-hint")

        # Command name derived from filename (without .md extension)
        name = command_path.stem

        return cls(
            name=name,
            path=command_path,
            description=description,
            argument_hint=argument_hint,
        )


VALID_AGENT_MODELS = {"inherit", "sonnet", "opus", "haiku"}


@dataclass
class Agent:
    """Represents a subagent within a module."""

    name: str
    path: Path
    description: Optional[str] = None
    model: Optional[str] = None  # inherit, sonnet, opus, haiku

    @classmethod
    def from_path(cls, agent_path: Path) -> "Agent":
        """Load an agent from its file path."""
        description = None
        model = None

        if agent_path.exists():
            metadata = fm.get_metadata(agent_path)
            description = metadata.get("description")
            model = metadata.get("model")

        # Agent name derived from filename (without .md extension)
        name = agent_path.stem

        return cls(
            name=name,
            path=agent_path,
            description=description,
            model=model,
        )


@dataclass
class Module:
    """Represents a lola module."""

    name: str
    path: Path
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    version: str = "0.1.0"
    description: str = ""

    @classmethod
    def from_path(cls, module_path: Path) -> Optional["Module"]:
        """
        Load a module from its directory path.

        Auto-discovers skills (folders containing SKILL.md), commands
        (.md files in commands/ folder), and agents (.md files in agents/ folder).
        """
        if not module_path.exists() or not module_path.is_dir():
            return None

        # Auto-discover skills: subdirs containing SKILL.md
        skills = []
        for subdir in module_path.iterdir():
            # Skip hidden directories and special folders
            if subdir.name.startswith(".") or subdir.name in ("commands", "agents"):
                continue
            if subdir.is_dir() and (subdir / SKILL_FILE).exists():
                skills.append(subdir.name)

        # Auto-discover commands: .md files in commands/
        commands = []
        commands_dir = module_path / "commands"
        if commands_dir.exists() and commands_dir.is_dir():
            for cmd_file in commands_dir.glob("*.md"):
                commands.append(cmd_file.stem)

        # Auto-discover agents: .md files in agents/
        agents = []
        agents_dir = module_path / "agents"
        if agents_dir.exists() and agents_dir.is_dir():
            for agent_file in agents_dir.glob("*.md"):
                agents.append(agent_file.stem)

        # Only valid if has at least one skill, command, or agent
        if not skills and not commands and not agents:
            return None

        return cls(
            name=module_path.name,
            path=module_path,
            skills=sorted(skills),
            commands=sorted(commands),
            agents=sorted(agents),
        )

    def get_skill_paths(self) -> list[Path]:
        """Get the full paths to all skills in this module."""
        return [self.path / skill for skill in self.skills]

    def get_command_paths(self) -> list[Path]:
        """Get the full paths to all commands in this module."""
        commands_dir = self.path / "commands"
        return [commands_dir / f"{cmd}.md" for cmd in self.commands]

    def get_agent_paths(self) -> list[Path]:
        """Get the full paths to all agents in this module."""
        agents_dir = self.path / "agents"
        return [agents_dir / f"{agent}.md" for agent in self.agents]

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the module structure.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check each skill exists and has SKILL.md with valid frontmatter
        for skill_rel in self.skills:
            skill_path = self.path / skill_rel
            if not skill_path.exists():
                errors.append(f"Skill directory not found: {skill_rel}")
            elif not (skill_path / SKILL_FILE).exists():
                errors.append(f"Missing {SKILL_FILE} in skill: {skill_rel}")
            else:
                # Validate SKILL.md frontmatter
                skill_errors = validate_skill_frontmatter(skill_path / SKILL_FILE)
                for err in skill_errors:
                    errors.append(f"{skill_rel}/{SKILL_FILE}: {err}")

        # Check each command exists and has valid frontmatter
        commands_dir = self.path / "commands"
        for cmd_name in self.commands:
            cmd_path = commands_dir / f"{cmd_name}.md"
            if not cmd_path.exists():
                errors.append(f"Command file not found: commands/{cmd_name}.md")
            else:
                cmd_errors = validate_command_frontmatter(cmd_path)
                for err in cmd_errors:
                    errors.append(f"commands/{cmd_name}.md: {err}")

        # Check each agent exists and has valid frontmatter
        agents_dir = self.path / "agents"
        for agent_name in self.agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if not agent_path.exists():
                errors.append(f"Agent file not found: agents/{agent_name}.md")
            else:
                agent_errors = validate_agent_frontmatter(agent_path)
                for err in agent_errors:
                    errors.append(f"agents/{agent_name}.md: {err}")

        return len(errors) == 0, errors


def validate_skill_frontmatter(skill_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in a SKILL.md file.

    Args:
        skill_file: Path to the SKILL.md file

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    try:
        content = skill_file.read_text()
    except Exception as e:
        return [f"Cannot read file: {e}"]

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (file should start with '---')")
        return errors

    # Find the closing ---
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        errors.append("Unclosed YAML frontmatter (missing closing '---')")
        return errors

    frontmatter_text = "\n".join(lines[1:end_idx])

    # Try to parse as YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        # Extract useful error info
        error_msg = str(e)
        if "mapping values are not allowed" in error_msg:
            errors.append(
                "Invalid YAML: values containing colons must be quoted. "
                'Example: description: "Text with: colons"'
            )
        else:
            errors.append(f"Invalid YAML frontmatter: {error_msg}")
        return errors

    # Check required fields
    if not frontmatter.get("description"):
        errors.append("Missing required field: 'description'")

    return errors


def validate_command_frontmatter(command_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in a command .md file.

    Args:
        command_file: Path to the command .md file

    Returns:
        List of error messages (empty if valid)
    """
    return fm.validate_command(command_file)


def validate_agent_frontmatter(agent_file: Path) -> list[str]:
    """
    Validate the YAML frontmatter in an agent .md file.

    Args:
        agent_file: Path to the agent .md file

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    try:
        content = agent_file.read_text()
    except Exception as e:
        return [f"Cannot read file: {e}"]

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (file should start with '---')")
        return errors

    # Find the closing ---
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        errors.append("Unclosed YAML frontmatter (missing closing '---')")
        return errors

    frontmatter_text = "\n".join(lines[1:end_idx])

    # Try to parse as YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        error_msg = str(e)
        if "mapping values are not allowed" in error_msg:
            errors.append(
                "Invalid YAML: values containing colons must be quoted. "
                'Example: description: "Text with: colons"'
            )
        else:
            errors.append(f"Invalid YAML frontmatter: {error_msg}")
        return errors

    # Check required fields
    if not frontmatter.get("description"):
        errors.append("Missing required field: 'description'")

    # Validate model field if present
    model = frontmatter.get("model")
    if model and model not in VALID_AGENT_MODELS:
        errors.append(
            f"Invalid model '{model}'. Must be one of: {', '.join(sorted(VALID_AGENT_MODELS))}"
        )

    return errors


@dataclass
class Installation:
    """Represents an installed module."""

    module_name: str
    assistant: str
    scope: str
    project_path: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        result = {
            "module": self.module_name,
            "assistant": self.assistant,
            "scope": self.scope,
            "skills": self.skills,
            "commands": self.commands,
            "agents": self.agents,
        }
        if self.project_path:
            result["project_path"] = self.project_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Installation":
        """Create from dictionary."""
        return cls(
            module_name=data.get("module", ""),
            assistant=data.get("assistant", ""),
            scope=data.get("scope", "user"),
            project_path=data.get("project_path"),
            skills=data.get("skills", []),
            commands=data.get("commands", []),
            agents=data.get("agents", []),
        )


class InstallationRegistry:
    """Manages the installed.yml file."""

    def __init__(self, registry_path: Path):
        self.path = registry_path
        self._installations: list[Installation] = []
        self._load()

    def _load(self):
        """Load installations from file."""
        if not self.path.exists():
            self._installations = []
            return

        with open(self.path, "r") as f:
            data = yaml.safe_load(f) or {}

        self._installations = [
            Installation.from_dict(inst) for inst in data.get("installations", [])
        ]

    def _save(self):
        """Save installations to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "installations": [inst.to_dict() for inst in self._installations],
        }

        with open(self.path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def add(self, installation: Installation):
        """Add an installation record."""
        # Remove any existing installation with same key
        self._installations = [
            inst
            for inst in self._installations
            if not (
                inst.module_name == installation.module_name
                and inst.assistant == installation.assistant
                and inst.scope == installation.scope
                and inst.project_path == installation.project_path
            )
        ]
        self._installations.append(installation)
        self._save()

    def remove(
        self,
        module_name: str,
        assistant: str | None = None,
        scope: str | None = None,
        project_path: str | None = None,
    ) -> list[Installation]:
        """
        Remove installation records matching the criteria.

        Returns list of removed installations.
        """
        removed = []
        kept = []

        for inst in self._installations:
            matches = inst.module_name == module_name
            if assistant:
                matches = matches and inst.assistant == assistant
            if scope:
                matches = matches and inst.scope == scope
            if project_path:
                matches = matches and inst.project_path == project_path

            if matches:
                removed.append(inst)
            else:
                kept.append(inst)

        self._installations = kept
        self._save()
        return removed

    def find(self, module_name: str) -> list[Installation]:
        """Find all installations of a module."""
        return [inst for inst in self._installations if inst.module_name == module_name]

    def all(self) -> list[Installation]:
        """Get all installations."""
        return self._installations.copy()
