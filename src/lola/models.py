"""
models:
    Data models for lola modules, skills, and installations
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Optional
import yaml

from lola.config import MCPS_FILE, SKILL_FILE
from lola import frontmatter as fm
from lola.exceptions import ValidationError

SKILLS_DIRNAME = "skills"
MODULE_CONTENT_DIRNAME = "module"


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


@dataclass
class Agent:
    """Represents a subagent within a module."""

    name: str
    path: Path
    description: Optional[str] = None
    model: Optional[str] = None

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
class MCPServer:
    """Represents an MCP server definition within a module."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "MCPServer":
        """Create from a dictionary entry in mcps.json."""
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
        )


INSTRUCTIONS_FILE = "AGENTS.md"


@dataclass
class Module:
    """Represents a lola module."""

    name: str
    path: Path
    content_path: Path  # Path to the directory containing lola content (module/ or root)
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    has_instructions: bool = False
    uses_module_subdir: bool = False  # True if content is in module/ subdirectory

    @classmethod
    def from_path(cls, module_path: Path) -> Optional["Module"]:
        """
        Load a module from its directory path.

        Checks for module/ subdirectory first (new structure), falls back to
        root-level content (legacy structure).

        Auto-discovers:
        - skills (folders containing SKILL.md) under skills/<skill_name>/
        - commands (.md files in commands/ folder)
        - agents (.md files in agents/ folder)
        """
        if not module_path.exists() or not module_path.is_dir():
            return None

        # Check for module/ subdirectory first (new structure)
        module_subdir = module_path / MODULE_CONTENT_DIRNAME
        if module_subdir.exists() and module_subdir.is_dir():
            content_path = module_subdir
            uses_module_subdir = True
        else:
            content_path = module_path
            uses_module_subdir = False

        skills = []
        skills_root = content_path / SKILLS_DIRNAME
        if skills_root.exists() and skills_root.is_dir():
            for subdir in skills_root.iterdir():
                if subdir.name.startswith("."):
                    continue
                if subdir.is_dir() and (subdir / SKILL_FILE).exists():
                    skills.append(subdir.name)

        # Auto-discover commands: .md files in commands/
        commands = []
        commands_dir = content_path / "commands"
        if commands_dir.exists() and commands_dir.is_dir():
            for cmd_file in commands_dir.glob("*.md"):
                commands.append(cmd_file.stem)

        # Auto-discover agents: .md files in agents/
        agents = []
        agents_dir = content_path / "agents"
        if agents_dir.exists() and agents_dir.is_dir():
            for agent_file in agents_dir.glob("*.md"):
                agents.append(agent_file.stem)

        # Check for module instructions (AGENTS.md)
        instructions_file = content_path / INSTRUCTIONS_FILE
        has_instructions = instructions_file.exists() and instructions_file.stat().st_size > 0

        # Auto-discover MCP servers from mcps.json
        mcps: list[str] = []
        mcps_file = content_path / MCPS_FILE
        if mcps_file.exists():
            try:
                data = json.loads(mcps_file.read_text())
                mcps = sorted(data.get("mcpServers", {}).keys())
            except (json.JSONDecodeError, OSError):
                # Ignore malformed mcps.json
                pass

        # Only valid if has at least one skill, command, agent, mcp, or instructions
        if not skills and not commands and not agents and not mcps and not has_instructions:
            return None

        return cls(
            name=module_path.name,
            path=module_path,
            content_path=content_path,
            skills=sorted(skills),
            commands=sorted(commands),
            agents=sorted(agents),
            mcps=mcps,
            has_instructions=has_instructions,
            uses_module_subdir=uses_module_subdir,
        )

    def _skills_root_dir(self) -> Path:
        """Get the directory that contains skill folders."""
        return self.content_path / SKILLS_DIRNAME

    def get_skill_paths(self) -> list[Path]:
        """Get the full paths to all skills in this module."""
        root = self._skills_root_dir()
        return [root / skill for skill in self.skills]

    def get_command_paths(self) -> list[Path]:
        """Get the full paths to all commands in this module."""
        commands_dir = self.content_path / "commands"
        return [commands_dir / f"{cmd}.md" for cmd in self.commands]

    def get_agent_paths(self) -> list[Path]:
        """Get the full paths to all agents in this module."""
        agents_dir = self.content_path / "agents"
        return [agents_dir / f"{agent}.md" for agent in self.agents]

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the module structure.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check each skill exists and has SKILL.md with valid frontmatter
        skills_root = self._skills_root_dir()
        for skill_rel in self.skills:
            skill_path = skills_root / skill_rel
            if not skill_path.exists():
                errors.append(f"Skill directory not found: {skill_rel}")
            elif not (skill_path / SKILL_FILE).exists():
                errors.append(f"Missing {SKILL_FILE} in skill: {skill_rel}")
            else:
                # Validate SKILL.md frontmatter
                skill_errors = fm.validate_skill(skill_path / SKILL_FILE)
                for err in skill_errors:
                    errors.append(f"{skill_rel}/{SKILL_FILE}: {err}")

        # Check each command exists and has valid frontmatter
        commands_dir = self.content_path / "commands"
        for cmd_name in self.commands:
            cmd_path = commands_dir / f"{cmd_name}.md"
            if not cmd_path.exists():
                errors.append(f"Command file not found: commands/{cmd_name}.md")
            else:
                cmd_errors = fm.validate_command(cmd_path)
                for err in cmd_errors:
                    errors.append(f"commands/{cmd_name}.md: {err}")

        # Check each agent exists and has valid frontmatter
        agents_dir = self.content_path / "agents"
        for agent_name in self.agents:
            agent_path = agents_dir / f"{agent_name}.md"
            if not agent_path.exists():
                errors.append(f"Agent file not found: agents/{agent_name}.md")
            else:
                agent_errors = fm.validate_agent(agent_path)
                for err in agent_errors:
                    errors.append(f"agents/{agent_name}.md: {err}")

        # Check mcps.json if module has MCPs
        if self.mcps:
            mcps_file = self.content_path / MCPS_FILE
            if not mcps_file.exists():
                errors.append(f"MCP file not found: {MCPS_FILE}")
            else:
                mcp_errors = fm.validate_mcps(mcps_file)
                for err in mcp_errors:
                    errors.append(f"{MCPS_FILE}: {err}")

        return len(errors) == 0, errors

    def validate_or_raise(self) -> None:
        """
        Validate the module structure.

        Raises:
            ValidationError: If the module has validation errors.
        """
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValidationError(self.name, errors)


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
    mcps: list[str] = field(default_factory=list)
    has_instructions: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        result = {
            "module": self.module_name,
            "assistant": self.assistant,
            "scope": self.scope,
            "skills": self.skills,
            "commands": self.commands,
            "agents": self.agents,
            "mcps": self.mcps,
            "has_instructions": self.has_instructions,
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
            mcps=data.get("mcps", []),
            has_instructions=data.get("has_instructions", False),
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
