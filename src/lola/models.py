"""
models:
    Data models for lola modules, skills, and installations
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import re
import yaml

from lola.config import MCPS_FILE, SKILL_FILE
from lola import frontmatter as fm
from lola.exceptions import ValidationError

SKILLS_DIRNAME = "skills"
MODULE_CONTENT_DIRNAME = "module"
LOLA_MODULE_CONTENT_DIRNAME = "lola-module"


def _is_scp_style_git_url(url: str) -> bool:
    """Detect git@host:org/repo.git SCP-style URLs."""
    return bool(re.match(r"^[^/]+@[^:]+:.+", url)) and "://" not in url


@dataclass
class Skill:
    """Represents a skill within a module."""

    name: str
    path: Path
    description: str | None = None

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
    description: str | None = None
    argument_hint: str | None = None

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
    description: str | None = None
    model: str | None = None

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
    content_path: (
        Path  # Path to the directory containing lola content (module/ or root)
    )
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    has_instructions: bool = False
    uses_module_subdir: bool = False  # True if content is in module/ subdirectory
    is_single_skill: bool = (
        False  # True if SKILL.md at content_path root (agentskills.io standard)
    )
    pre_install_hook: str | None = (
        None  # Path to pre-install script (relative to content_path)
    )
    post_install_hook: str | None = (
        None  # Path to post-install script (relative to content_path)
    )

    @classmethod
    def from_path(
        cls, module_path: Path, content_dirname: str | None = None
    ) -> "Module | None":
        """
        Load a module from its directory path.

        Args:
            module_path: Path to the module directory
            content_dirname: Optional custom directory for content
                            "/" = use root, otherwise subdirectory name

        Auto-discovers:
        - skills (folders containing SKILL.md) under skills/<skill_name>/
        - commands (.md files in commands/ folder)
        - agents (.md files in agents/ folder)
        """
        if not module_path.exists() or not module_path.is_dir():
            return None

        content_path, uses_module_subdir = cls._resolve_content_path(
            module_path, content_dirname
        )

        if content_path is None:
            return None

        skills = []
        is_single_skill = False

        # Check for skill bundle (skills/ subdirectory)
        skills_root = content_path / SKILLS_DIRNAME
        if skills_root.exists() and skills_root.is_dir():
            for subdir in skills_root.iterdir():
                if subdir.name.startswith("."):
                    continue
                if subdir.is_dir() and (subdir / SKILL_FILE).exists():
                    skills.append(subdir.name)

        # If no bundle found, check for single skill at root (agentskills.io standard)
        if not skills:
            single_skill_file = content_path / SKILL_FILE
            if single_skill_file.exists() and single_skill_file.is_file():
                metadata = fm.get_metadata(single_skill_file)
                skill_name = module_path.name
                meta_name = metadata.get("name")
                if meta_name and isinstance(meta_name, str):
                    skill_name = meta_name
                skills.append(skill_name)
                is_single_skill = True

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
        has_instructions = (
            instructions_file.exists() and instructions_file.stat().st_size > 0
        )

        # Auto-discover MCP servers from mcps.json
        mcps: list[str] = []
        mcps_file = content_path / MCPS_FILE
        if mcps_file.exists():
            try:
                data = json.loads(mcps_file.read_text(encoding="utf-8-sig"))
                mcps = sorted(data.get("mcpServers", {}).keys())
            except (json.JSONDecodeError, OSError):
                pass

        # Auto-discover hooks from lola.yaml
        pre_install_hook = None
        post_install_hook = None
        lola_yaml = content_path / "lola.yaml"
        if not lola_yaml.exists():
            lola_yaml = content_path / "lola.yml"
        if lola_yaml.exists():
            try:
                with open(lola_yaml, encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                hooks = config.get("hooks", {})
                pre_install_hook = (
                    hooks.get("pre-install") if isinstance(hooks, dict) else None
                )
                post_install_hook = (
                    hooks.get("post-install") if isinstance(hooks, dict) else None
                )
            except (yaml.YAMLError, OSError):
                pass  # hooks are optional; malformed lola.yaml is non-fatal

        # Only valid if has at least one skill, command, agent, mcp, or instructions
        if (
            not skills
            and not commands
            and not agents
            and not mcps
            and not has_instructions
        ):
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
            is_single_skill=is_single_skill,
            pre_install_hook=pre_install_hook,
            post_install_hook=post_install_hook,
        )

    @classmethod
    def _resolve_content_path(
        cls, module_path: Path, content_dirname: str | None
    ) -> tuple[Path | None, bool]:
        """
        Resolve content path from module path and optional content dirname.

        Args:
            module_path: Path to the module directory
            content_dirname: Optional custom directory name
                            "/" = use root, otherwise subdirectory name

        Returns:
            (content_path, uses_module_subdir) or (None, False) if invalid
        """
        # Custom content directory specified
        if content_dirname is not None:
            # Root directory requested
            if content_dirname == "/":
                return module_path, False

            # Custom subdirectory path
            custom_subdir = module_path / content_dirname
            if not custom_subdir.exists() or not custom_subdir.is_dir():
                return None, False

            return custom_subdir, True

        # Default discovery: try module/ then fallback to root
        module_subdir = module_path / MODULE_CONTENT_DIRNAME
        if module_subdir.exists() and module_subdir.is_dir():
            return module_subdir, True

        return module_path, False

    def _skills_root_dir(self) -> Path:
        """Get the directory that contains skill folders."""
        if self.is_single_skill:
            return self.content_path
        return self.content_path / SKILLS_DIRNAME

    def get_skill_paths(self) -> list[Path]:
        """Get the full paths to all skills in this module."""
        if self.is_single_skill:
            return [self.content_path]
        return [self.content_path / SKILLS_DIRNAME / skill for skill in self.skills]

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
        for skill_name, skill_path in zip(self.skills, self.get_skill_paths()):
            if not skill_path.exists():
                errors.append(f"Skill directory not found: {skill_name}")
            elif not (skill_path / SKILL_FILE).exists():
                errors.append(f"Missing {SKILL_FILE} in skill: {skill_name}")
            else:
                # Validate SKILL.md frontmatter
                skill_errors = fm.validate_skill(skill_path / SKILL_FILE)
                for err in skill_errors:
                    errors.append(f"{skill_name}/{SKILL_FILE}: {err}")

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

        # Validate hooks if defined
        for hook_type, hook_path in [
            ("pre-install", self.pre_install_hook),
            ("post-install", self.post_install_hook),
        ]:
            if not hook_path:
                continue

            full_path = self.content_path / hook_path
            if not full_path.exists():
                errors.append(f"{hook_type} hook script not found: {hook_path}")
                continue

            try:
                full_path.resolve().relative_to(self.path.resolve())
            except ValueError:
                errors.append(f"{hook_type} hook outside module directory: {hook_path}")

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
class Marketplace:
    """Represents a marketplace catalog with modules."""

    name: str
    url: str
    enabled: bool = True
    description: str = ""
    version: str = ""
    modules: list[dict] = field(default_factory=list)

    @classmethod
    def from_reference(cls, ref_file: Path) -> "Marketplace":
        """Load marketplace from reference file."""
        with open(ref_file) as f:
            data = yaml.safe_load(f) or {}
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
        )

    @classmethod
    def from_cache(cls, cache_file: Path) -> "Marketplace":
        """Load marketplace from cache file."""
        with open(cache_file) as f:
            data = yaml.safe_load(f) or {}
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            version=data.get("version", ""),
            modules=data.get("modules", []),
        )

    @classmethod
    def from_url(cls, url: str, name: str) -> "Marketplace":
        """Load marketplace from URL (http/https), git repo (git+https/git+ssh), or local file path."""
        from urllib.request import urlopen
        from urllib.error import URLError

        from urllib.parse import urlparse

        # Git-based fetch: git+https://, git+ssh://, SCP-style, or .git-suffixed URLs
        # Uses git clone to leverage existing credentials (SSH keys, credential
        # helpers, .netrc) — required for self-hosted GitLab/GitHub instances
        # that don't allow unauthenticated HTTP access.
        if url.startswith("git+") or _is_scp_style_git_url(url):
            return cls._from_git_url(url, name)

        parsed = urlparse(url)
        stored_url = url

        # Auto-detect .git-suffixed HTTPS/HTTP URLs as git sources
        # (e.g. https://github.com/org/marketplace.git)
        if parsed.scheme in ("http", "https") and parsed.path.rstrip("/").endswith(
            ".git"
        ):
            return cls._from_git_url(url, name)

        if parsed.scheme in ("http", "https"):
            try:
                with urlopen(url, timeout=10) as response:  # nosec B310 - scheme validated above
                    data = yaml.safe_load(response.read()) or {}
            except URLError as e:
                raise ValueError(f"Failed to download marketplace: {e}")
        elif parsed.scheme == "file" or parsed.scheme == "":
            if parsed.scheme == "":
                file_path = Path(url).resolve()
            else:
                file_path = Path(parsed.path)
            if not file_path.exists():
                raise ValueError(f"Marketplace file not found: {file_path}")
            try:
                with open(file_path) as f:
                    data = yaml.safe_load(f) or {}
            except OSError as e:
                raise ValueError(f"Failed to read marketplace file: {e}")
            stored_url = file_path.as_uri()
        else:
            raise ValueError(
                f"Marketplace URL must use http(s), git+https, git+ssh, "
                f"or file/local path, got: {parsed.scheme!r}"
            )

        return cls(
            name=name,
            url=stored_url,
            enabled=True,
            description=data.get("description", ""),
            version=data.get("version", ""),
            modules=data.get("modules", []),
        )

    @classmethod
    def _from_git_url(cls, url: str, name: str) -> "Marketplace":
        """Fetch marketplace YAML from a git repository.

        Supports URLs like:
            git+https://gitlab.internal/org/marketplace.git
            git+ssh://git@gitlab.internal/org/marketplace.git
            git+https://gitlab.internal/org/marketplace.git#path/to/market.yml
            git@gitlab.internal:org/marketplace.git (SCP-style)
            https://github.com/org/marketplace.git (auto-detected by .git suffix)

        The optional fragment (#path/to/file.yml) specifies which file in the
        repo contains the marketplace catalog. Without it, auto-detection is
        used (see _find_marketplace_yaml).
        """
        import shutil
        import subprocess  # nosec B404 - required for git clone
        from urllib.parse import urlparse, urlunparse

        # Prevent git from prompting for credentials interactively
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

        # Strip "git+" prefix if present: git+https://... → https://...
        # SCP-style URLs (git@host:path) are passed through as-is.
        if url.startswith("git+"):
            git_url = url[4:]
        else:
            git_url = url

        # SCP-style URLs don't support fragments; only parse for git+ URLs
        if _is_scp_style_git_url(git_url):
            file_fragment = None
            git_url_clean = git_url
        else:
            # Extract optional fragment for file path within the repo
            parsed = urlparse(git_url)
            file_fragment = parsed.fragment or None
            git_url_clean = urlunparse(parsed._replace(fragment=""))

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            # Sparse clone: fetch only metadata, no file content
            clone_cmd = [
                "git",
                "clone",
                "--filter=blob:none",
                "--sparse",
                "--depth",
                "1",
                "--",
                git_url_clean,
                str(repo_dir),
            ]
            result = subprocess.run(  # nosec B603 B607 - list args (no shell), git from PATH
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=git_env,
            )
            if result.returncode != 0:
                raise ValueError(
                    f"Failed to clone marketplace repository: {result.stderr.strip()}"
                )
            try:
                if file_fragment:
                    # Guard against path traversal via fragment
                    target_path = (repo_dir / file_fragment).resolve()
                    if (
                        not str(target_path).startswith(
                            str(repo_dir.resolve()) + os.sep
                        )
                        and target_path != repo_dir.resolve()
                    ):
                        raise ValueError(
                            f"Path traversal detected in fragment: {file_fragment}"
                        )
                    checkout_path = file_fragment
                else:
                    # Use git ls-tree to list files without downloading them
                    checkout_path = cls._pick_marketplace_yaml(repo_dir, name)

                # Sparse checkout: fetch only the file we need
                # Use --no-cone because cone mode only supports directories,
                # but marketplace YAML files are individual files at repo root.
                sparse_cmd = [
                    "git",
                    "-C",
                    str(repo_dir),
                    "sparse-checkout",
                    "set",
                    "--no-cone",
                    checkout_path,
                ]
                result = subprocess.run(  # nosec B603 B607
                    sparse_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=git_env,
                )
                if result.returncode != 0:
                    raise ValueError(
                        f"Failed to sparse-checkout file: {result.stderr.strip()}"
                    )

                yaml_file = repo_dir / checkout_path
                if not yaml_file.exists():
                    raise ValueError(f"File '{checkout_path}' not found in repository")
                with open(yaml_file) as f:
                    data = yaml.safe_load(f) or {}
            finally:
                # Clean up .git before the temp dir context manager does it,
                # to avoid issues with read-only git objects on some platforms.
                git_dir = repo_dir / ".git"
                if git_dir.exists():
                    shutil.rmtree(git_dir, ignore_errors=True)

        return cls(
            name=name,
            url=url,  # Store the original git+ URL for future updates
            enabled=True,
            description=data.get("description", ""),
            version=data.get("version", ""),
            modules=data.get("modules", []),
        )

    @staticmethod
    def _pick_marketplace_yaml(repo_dir: Path, name: str) -> str:
        """Pick the marketplace YAML file path from a sparse-cloned repo using git ls-tree.

        Search order:
        1. <name>.yml / <name>.yaml (matches the marketplace name)
        2. marketplace.yml / marketplace.yaml (common convention)
        3. Single .yml/.yaml file at repo root (unambiguous auto-detect)

        Returns the relative path string for sparse-checkout.
        """
        import subprocess  # nosec B404

        # List all files at the repo root via git ls-tree
        ls_cmd = [
            "git",
            "-C",
            str(repo_dir),
            "ls-tree",
            "--name-only",
            "HEAD",
        ]
        result = subprocess.run(  # nosec B603 B607
            ls_cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise ValueError(
                f"Failed to list repository contents: {result.stderr.strip()}"
            )

        root_files = [f for f in result.stdout.splitlines() if f]

        # Try name-specific file first
        for ext in (".yml", ".yaml"):
            candidate = f"{name}{ext}"
            if candidate in root_files:
                return candidate

        # Try common conventional names
        for common_name in ("marketplace.yml", "marketplace.yaml"):
            if common_name in root_files:
                return common_name

        # Auto-detect: single YAML file at repo root
        yml_files = [
            f
            for f in root_files
            if (f.endswith(".yml") or f.endswith(".yaml"))
            and f != ".pre-commit-config.yaml"
        ]
        if len(yml_files) == 1:
            return yml_files[0]
        elif len(yml_files) == 0:
            raise ValueError("No YAML files found in repository root")
        else:
            file_list = ", ".join(sorted(yml_files))
            raise ValueError(
                f"Multiple YAML files found in repository root: {file_list}. "
                f"Specify the file with a fragment: git+<url>#filename.yml"
            )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate marketplace structure."""
        errors = []

        if not self.name:
            errors.append("Missing required field: name")
        if not self.url:
            errors.append("Missing required field: url")

        if self.modules and not self.version:
            errors.append("Missing version for marketplace catalog")

        for i, mod in enumerate(self.modules):
            required = ["name", "description", "version", "repository"]
            for field_name in required:
                if field_name not in mod:
                    errors.append(f"Module {i}: missing '{field_name}'")

            ref = mod.get("ref")
            if ref is not None:
                if not isinstance(ref, str) or not ref.strip():
                    errors.append(
                        f"Module {i} ({mod.get('name', '?')}): 'ref' must be a non-empty string"
                    )
                elif any(ord(c) < 32 for c in ref):
                    errors.append(
                        f"Module {i} ({mod.get('name', '?')}): 'ref' contains control characters"
                    )

        return len(errors) == 0, errors

    def to_reference_dict(self) -> dict:
        """Convert to dict for reference file."""
        return {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
        }

    def to_cache_dict(self) -> dict:
        """Convert to dict for cache file."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "enabled": self.enabled,
            "modules": self.modules,
        }


@dataclass
class Installation:
    """Represents an installed module."""

    module_name: str
    assistant: str
    scope: str
    project_path: str | None = None
    version: str | None = None
    ref: str | None = None
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    has_instructions: bool = False
    append_context: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate append_context items are strings."""
        if self.append_context is not None:
            for item in self.append_context:
                if not isinstance(item, str):
                    raise TypeError(
                        f"append_context items must be str, "
                        f"got {type(item).__name__}: {item!r}"
                    )

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
        if self.version:
            result["version"] = self.version
        if self.ref:
            result["ref"] = self.ref
        if self.append_context:
            result["append_context"] = self.append_context
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Installation":
        """Create from dictionary.

        Handles backward compatibility: old format had a single string,
        new format is a list of strings.
        """
        raw = data.get("append_context")
        if raw is None:
            append_context: list[str] | None = None
        elif isinstance(raw, list):
            append_context = raw
        else:
            # Old format: single string → wrap in list
            append_context = [raw]

        return cls(
            module_name=data.get("module", ""),
            assistant=data.get("assistant", ""),
            scope=data.get("scope", "project"),
            project_path=data.get("project_path"),
            version=data.get("version"),
            ref=data.get("ref"),
            skills=data.get("skills", []),
            commands=data.get("commands", []),
            agents=data.get("agents", []),
            mcps=data.get("mcps", []),
            has_instructions=data.get("has_instructions", False),
            append_context=append_context,
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
        """Save installations to file atomically.

        Uses a temporary file and atomic rename to prevent corruption
        if the process is interrupted during write.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "installations": [inst.to_dict() for inst in self._installations],
        }

        # Write to a temporary file in the same directory (same filesystem)
        # then atomically replace the target file
        fd, tmp_path_str = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            text=True,
        )
        tmp_path = Path(tmp_path_str)

        try:
            # Write to the temporary file
            with os.fdopen(fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Atomically replace the target file
            # On POSIX systems, this is atomic even if target exists
            tmp_path.replace(self.path)
        except Exception:
            # Clean up temporary file on failure
            tmp_path.unlink(missing_ok=True)
            raise

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
