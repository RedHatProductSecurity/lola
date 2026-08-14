"""Agent Plugins v1 package loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from typing import cast

from lola import config
from lola import frontmatter as fm
from lola.config import SKILL_FILE
from lola.exceptions import ValidationError

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
LOLA_NAMESPACE = "dev.getlola"

_PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
_METADATA_STRING_FIELDS = {
    "version",
    "description",
    "homepage",
    "repository",
    "license",
}
_CLIENT_NAMESPACES = (
    "com.anthropic.claude",
    "com.anthropic.claude-code",
    "com.cursor.editor",
    "com.github.copilot",
    "com.google.gemini-cli",
    "com.openai",
    "com.openai.codex",
    "ai.opencode",
    LOLA_NAMESPACE,
)
_NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")


@dataclass
class AgentPlugin:
    """Normalized data discovered from an Agent Plugins package."""

    name: str
    skills: list[str] = field(default_factory=list)
    command_paths: dict[str, Path] = field(default_factory=dict)
    agent_paths: dict[str, Path] = field(default_factory=dict)
    mcps_data: dict[str, dict[str, object]] = field(default_factory=dict)
    instructions_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def commands(self) -> list[str]:
        """Return sorted command names."""
        return sorted(self.command_paths)

    @property
    def agents(self) -> list[str]:
        """Return sorted agent names."""
        return sorted(self.agent_paths)

    @property
    def mcps(self) -> list[str]:
        """Return sorted MCP server names."""
        return sorted(self.mcps_data)


def is_agent_plugin(root: Path) -> bool:
    """Return whether a path declares an Agent Plugins manifest."""
    return (root / "plugin.json").is_file()


def validate_plugin_name(name: str) -> bool:
    """Return whether a name satisfies Agent Plugins v1 constraints."""
    return len(name) <= 64 and bool(_NAME_PATTERN.fullmatch(name))


def load_agent_plugin(root: Path) -> AgentPlugin:
    """Load and validate an Agent Plugins v1 package."""
    manifest_path = root / "plugin.json"
    manifest = _read_json_object(manifest_path, "plugin.json")
    errors, warnings = _validate_manifest(manifest)
    if errors:
        raise ValidationError(root.name, errors)

    name = cast(str, manifest["name"])
    plugin = AgentPlugin(name=name, warnings=warnings)
    plugin.skills = _discover_skills(root, plugin.warnings)

    extensions = manifest.get("extensions")
    if isinstance(extensions, dict):
        typed_extensions = cast(dict[str, object], extensions)
        _discover_extensions(root, typed_extensions, plugin)

    mcp_path = root / "mcp.json"
    if mcp_path.exists():
        plugin.mcps_data = _load_mcps(root, mcp_path, plugin.warnings)
    return plugin


def materialize_module_mcps(
    servers: dict[str, dict[str, object]],
    plugin_root: Path,
    module_name: str,
    scope: str,
    project_path: str | None,
) -> dict[str, dict[str, object]]:
    """Materialize a plugin's MCP servers with its data directory."""
    if scope == "user":
        plugin_data = config.LOLA_HOME / "plugin-data" / module_name
    else:
        plugin_data = Path(project_path or ".") / ".lola" / "plugin-data" / module_name
    plugin_data.mkdir(parents=True, exist_ok=True)
    return materialize_mcps(servers, plugin_root, plugin_data)


def materialize_mcps(
    servers: dict[str, dict[str, object]],
    plugin_root: Path,
    plugin_data: Path,
) -> dict[str, dict[str, object]]:
    """Translate portable MCP values to Lola's target-neutral shape."""
    root_value = str(plugin_root.resolve())
    data_value = str(plugin_data.resolve())
    result: dict[str, dict[str, object]] = {}
    for name, source in servers.items():
        server = dict(source)
        server_type = server.get("type")
        if server_type == "stdio":
            del server["type"]
        elif server_type == "streamable-http":
            server["type"] = "http"

        command = server.get("command")
        if isinstance(command, str):
            if command.startswith("./"):
                server["command"] = str(plugin_root / command[2:])
            else:
                server["command"] = _expand_plugin_value(
                    command, root_value, data_value
                )

        values = server.get("args")
        if isinstance(values, list):
            server["args"] = [
                _expand_plugin_value(cast(str, value), root_value, data_value)
                for value in values
            ]
        env = server.get("env", {})
        if server_type == "stdio" and isinstance(env, dict):
            materialized_env = {
                key: _expand_plugin_value(cast(str, value), root_value, data_value)
                for key, value in env.items()
            }
            materialized_env["PLUGIN_ROOT"] = root_value
            materialized_env["PLUGIN_DATA"] = data_value
            server["env"] = materialized_env
        cwd = server.get("cwd")
        if isinstance(cwd, str):
            if cwd.startswith("./"):
                server["cwd"] = str(plugin_root / cwd[2:])
            else:
                server["cwd"] = _expand_plugin_value(cwd, root_value, data_value)
        elif server_type == "stdio":
            server["cwd"] = root_value
        result[name] = server
    return result


def _expand_plugin_value(value: str, root: str, data: str) -> str:
    return value.replace("${PLUGIN_ROOT}", root).replace("${PLUGIN_DATA}", data)


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as error:
        raise ValidationError(path.parent.name, [f"{label}: {error}"]) from error
    if not isinstance(data, dict):
        raise ValidationError(
            path.parent.name,
            [f"{label}: expected a JSON object"],
        )
    return data


def _validate_manifest(
    manifest: dict[str, object],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings = [
        f"plugin.json: ignoring unknown field '{field}'"
        for field in manifest
        if field not in _PLUGIN_FIELDS
    ]
    if manifest.get("$schema") != PLUGIN_SCHEMA:
        errors.append("plugin.json: unsupported or missing $schema")

    name = manifest.get("name")
    if not isinstance(name, str) or not validate_plugin_name(name):
        errors.append("plugin.json: invalid name")

    for field_name in _METADATA_STRING_FIELDS:
        if field_name in manifest and not isinstance(manifest[field_name], str):
            errors.append(f"plugin.json: {field_name} must be a string")

    author = manifest.get("author")
    if author is not None:
        if not isinstance(author, dict):
            errors.append("plugin.json: author must be an object")
        else:
            invalid = set(author) - {"name", "email", "url"}
            if invalid or any(not isinstance(value, str) for value in author.values()):
                errors.append("plugin.json: invalid author")

    keywords = manifest.get("keywords")
    if keywords is not None and (
        not isinstance(keywords, list)
        or any(not isinstance(value, str) for value in keywords)
    ):
        errors.append("plugin.json: keywords must be an array of strings")

    extensions = manifest.get("extensions")
    if isinstance(extensions, dict):
        typed_extensions = cast(dict[str, object], extensions)
        for namespace in _CLIENT_NAMESPACES:
            value = typed_extensions.get(namespace)
            if value is not None and not isinstance(value, dict):
                warnings.append(
                    f"plugin.json: ignoring invalid extension '{namespace}'"
                )
    elif extensions is not None:
        warnings.append("plugin.json: ignoring non-object extensions")
    return errors, warnings


def _discover_skills(root: Path, warnings: list[str]) -> list[str]:
    skills_root = root / "skills"
    if not skills_root.exists():
        return []
    if not skills_root.is_dir() or not _is_contained(root, skills_root):
        warnings.append("skills/: invalid or outside plugin root")
        return []

    skills: list[str] = []
    for skill_dir in sorted(skills_root.iterdir()):
        skill_file = skill_dir / SKILL_FILE
        if not skill_dir.is_dir() or not skill_file.is_file():
            continue
        if not _is_contained(root, skill_file):
            warnings.append(
                f"skills/{skill_dir.name}/{SKILL_FILE}: outside plugin root"
            )
            continue
        errors = fm.validate_skill(skill_file)
        if errors:
            warnings.append(
                f"skills/{skill_dir.name}/{SKILL_FILE}: " + "; ".join(errors)
            )
            continue
        skills.append(skill_dir.name)
    return skills


def _discover_extensions(
    root: Path,
    extensions: dict[str, object],
    plugin: AgentPlugin,
) -> None:
    for namespace in _CLIENT_NAMESPACES:
        config = extensions.get(namespace)
        if not isinstance(config, dict):
            typed_config: dict[str, object] = {}
        else:
            typed_config = cast(dict[str, object], config)
        extension_root = root / namespace
        for component, destination in (
            ("commands", plugin.command_paths),
            ("agents", plugin.agent_paths),
        ):
            configured = typed_config.get(component)
            directory = _extension_path(
                root,
                configured,
                extension_root / component,
                f"extensions.{namespace}.{component}",
                plugin.warnings,
            )
            if directory is None:
                continue
            for item in sorted(directory.glob("*.md")):
                if item.is_file() and _is_contained(root, item):
                    destination[item.stem] = item

        configured_instructions = typed_config.get("instructions")
        default_instructions = extension_root / "AGENTS.md"
        instructions = _extension_path(
            root,
            configured_instructions,
            default_instructions,
            f"extensions.{namespace}.instructions",
            plugin.warnings,
            expect_directory=False,
        )
        if instructions is not None:
            plugin.instructions_path = instructions


def _extension_path(
    root: Path,
    configured: object,
    default: Path,
    label: str,
    warnings: list[str],
    *,
    expect_directory: bool = True,
) -> Path | None:
    path = default
    if configured is not None:
        if not isinstance(configured, str) or not configured.startswith("./"):
            warnings.append(f"{label}: expected a './' plugin-relative path")
            return None
        path = root / configured[2:]

    exists_as_kind = path.is_dir() if expect_directory else path.is_file()
    if not exists_as_kind:
        return None
    if not _is_contained(root, path):
        warnings.append(f"{label}: outside plugin root")
        return None
    return path


def _load_mcps(
    root: Path,
    path: Path,
    warnings: list[str],
) -> dict[str, dict[str, object]]:
    if not path.is_file() or not _is_contained(root, path):
        warnings.append("mcp.json: invalid or outside plugin root")
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as error:
        warnings.append(f"mcp.json: {error}")
        return {}
    if not isinstance(data, dict):
        warnings.append("mcp.json: expected a JSON object")
        return {}
    if data.get("$schema") != MCP_SCHEMA:
        warnings.append("mcp.json: unsupported or missing $schema")
        return {}
    if set(data) != {"$schema", "mcpServers"}:
        warnings.append("mcp.json: invalid top-level fields")
        return {}
    raw_servers = data.get("mcpServers")
    if not isinstance(raw_servers, dict):
        warnings.append("mcp.json: mcpServers must be an object")
        return {}

    servers: dict[str, dict[str, object]] = {}
    for name, server in raw_servers.items():
        validation_error = _validate_mcp_server(root, name, server)
        if validation_error:
            warnings.append(f"mcp.json: server '{name}': {validation_error}")
            continue
        servers[cast(str, name)] = dict(cast("dict[str, object]", server))
    return servers


def _validate_mcp_server(root: Path, name: object, config: object) -> str | None:
    if not isinstance(name, str) or not name:
        return "server name must be a non-empty string"
    if not isinstance(config, dict):
        return "configuration must be an object"
    typed_config = cast(dict[object, object], config)
    server_type = typed_config.get("type")
    if server_type == "stdio":
        return _validate_stdio_server(root, typed_config)
    if server_type in {"streamable-http", "sse"}:
        return _validate_remote_server(typed_config)
    return "unsupported type"


def _validate_stdio_server(root: Path, config: dict[object, object]) -> str | None:
    allowed = {"type", "command", "args", "env", "cwd"}
    if set(config) - allowed:
        return "unknown field"
    command = config.get("command")
    if (
        not isinstance(command, str)
        or not command
        or any(char.isspace() for char in command)
    ):
        return "command must be one executable token"
    if command.startswith("./") and not _valid_package_path(root, command):
        return "command is outside plugin root"
    args = config.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        return "args must be an array of strings"
    env = config.get("env", {})
    if not isinstance(env, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in env.items()
    ):
        return "env must contain string values"
    if "PLUGIN_ROOT" in env or "PLUGIN_DATA" in env:
        return "env contains a reserved variable"
    cwd = config.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not _valid_cwd(root, cwd)):
        return "invalid cwd"
    return None


def _validate_remote_server(config: dict[object, object]) -> str | None:
    if set(config) - {"type", "url", "headers"}:
        return "unknown field"
    url = config.get("url")
    if not isinstance(url, str) or urlparse(url).scheme not in {
        "http",
        "https",
    }:
        return "url must use http or https"
    headers = config.get("headers", {})
    if not isinstance(headers, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in headers.items()
    ):
        return "headers must contain literal string values"
    typed_headers = cast(dict[str, str], headers)
    if any("${" in value for value in typed_headers.values()):
        return "headers cannot contain placeholders"
    return None


def _valid_cwd(root: Path, value: str) -> bool:
    if value.startswith("./"):
        return _valid_package_path(root, value)
    return (
        value == "${PLUGIN_ROOT}"
        or value.startswith("${PLUGIN_ROOT}/")
        or value == "${PLUGIN_DATA}"
        or value.startswith("${PLUGIN_DATA}/")
    )


def _valid_package_path(root: Path, value: str) -> bool:
    return _is_contained(root, root / value[2:])


def _is_contained(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True
