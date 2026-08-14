"""Tests for Agent Plugins v1 package support."""

import json
from pathlib import Path

import pytest

from lola.agent_plugins import (
    MCP_SCHEMA,
    PLUGIN_SCHEMA,
    load_agent_plugin,
    materialize_mcps,
)
from lola.agent_plugin_scaffold import ScaffoldOptions, scaffold_agent_plugin
from lola.cli.install import install_cmd, update_cmd
from lola.exceptions import ValidationError
from lola.models import Module


def _write_manifest(root: Path, **overrides: object) -> None:
    manifest = {
        "$schema": PLUGIN_SCHEMA,
        "name": "portable-plugin",
    }
    manifest.update(overrides)
    (root / "plugin.json").write_text(json.dumps(manifest))


def _write_skill(root: Path, name: str) -> Path:
    skill = root / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill\n---\n"
    )
    return skill


def test_loads_portable_core_and_manifest_name(tmp_path: Path) -> None:
    """Discover skills and MCP servers from their fixed v1 locations."""
    _write_manifest(tmp_path)
    _write_skill(tmp_path, "review")
    mcp = {
        "$schema": MCP_SCHEMA,
        "mcpServers": {
            "reviewer": {
                "type": "stdio",
                "command": "uvx",
                "args": ["review", "${PLUGIN_ROOT}/rules.json"],
            }
        },
    }
    (tmp_path / "mcp.json").write_text(json.dumps(mcp))

    plugin = load_agent_plugin(tmp_path)

    assert plugin.name == "portable-plugin"
    assert plugin.skills == ["review"]
    assert plugin.mcps == ["reviewer"]


def test_module_loads_plugin_from_content_dirname(tmp_path: Path) -> None:
    """A plugin selected by content_dirname uses the plugin adapter."""
    nested = tmp_path / "packages" / "plugin"
    nested.mkdir(parents=True)
    _write_manifest(nested)
    _write_skill(nested, "review")

    module = Module.from_path(tmp_path, content_dirname="packages/plugin")

    assert module is not None
    assert module.name == "portable-plugin"
    assert module.content_path == nested


def test_loopback_http_mcp_url_is_allowed(tmp_path: Path) -> None:
    """Plain HTTP is portable only for loopback hosts."""
    _write_manifest(tmp_path)
    (tmp_path / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "local": {
                        "type": "streamable-http",
                        "url": "http://127.0.0.1:8080/mcp",
                    }
                },
            }
        )
    )

    plugin = load_agent_plugin(tmp_path)

    assert plugin.mcps == ["local"]


def test_module_reads_lola_namespace(tmp_path: Path) -> None:
    """Lola extensions provide non-portable commands and agents."""
    _write_manifest(
        tmp_path,
        extensions={
            "dev.getlola": {
                "commands": "./dev.getlola/commands",
                "agents": "./dev.getlola/agents",
                "instructions": "./dev.getlola/AGENTS.md",
            }
        },
    )
    _write_skill(tmp_path, "review")
    extension = tmp_path / "dev.getlola"
    (extension / "commands").mkdir(parents=True)
    (extension / "agents").mkdir()
    (extension / "commands" / "check.md").write_text(
        "---\ndescription: Check code\n---\n"
    )
    (extension / "agents" / "reviewer.md").write_text(
        "---\ndescription: Review code\n---\n"
    )
    (extension / "AGENTS.md").write_text("# Instructions\n")

    module = Module.from_path(tmp_path)

    assert module is not None
    assert module.name == "portable-plugin"
    assert module.commands == ["check"]
    assert module.agents == ["reviewer"]
    assert module.get_command_paths() == [extension / "commands" / "check.md"]
    assert module.get_agent_paths() == [extension / "agents" / "reviewer.md"]
    assert module.instructions_path == extension / "AGENTS.md"


def test_reads_known_client_namespace_paths(tmp_path: Path) -> None:
    """Known client extension paths are translated through Lola."""
    _write_manifest(
        tmp_path,
        extensions={
            "com.anthropic.claude-code": {
                "commands": "./claude/commands",
                "agents": "./claude/agents",
            }
        },
    )
    (tmp_path / "claude" / "commands").mkdir(parents=True)
    (tmp_path / "claude" / "agents").mkdir()
    (tmp_path / "claude" / "commands" / "deploy.md").write_text("# Deploy")
    (tmp_path / "claude" / "agents" / "ops.md").write_text("# Ops")

    plugin = load_agent_plugin(tmp_path)

    assert plugin.commands == ["deploy"]
    assert plugin.agents == ["ops"]


def test_lola_namespace_wins_duplicate_component_names(tmp_path: Path) -> None:
    """The Lola-owned namespace has deterministic precedence."""
    _write_manifest(
        tmp_path,
        extensions={
            "com.anthropic.claude-code": {
                "commands": "./claude/commands",
            },
            "dev.getlola": {
                "commands": "./dev.getlola/commands",
            },
        },
    )
    for directory in ("claude", "dev.getlola"):
        commands = tmp_path / directory / "commands"
        commands.mkdir(parents=True)
        (commands / "review.md").write_text(f"# {directory}")

    plugin = load_agent_plugin(tmp_path)

    assert plugin.command_paths["review"] == (
        tmp_path / "dev.getlola" / "commands" / "review.md"
    )


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ({"name": "valid-name"}, r"unsupported or missing \$schema"),
        ({"$schema": PLUGIN_SCHEMA, "name": "Bad Name"}, "invalid name"),
        ({"$schema": PLUGIN_SCHEMA, "name": "ok", "version": 1}, "version"),
    ],
)
def test_rejects_invalid_manifest(
    tmp_path: Path, manifest: dict[str, object], message: str
) -> None:
    """Fatal manifest schema violations reject the entire plugin."""
    (tmp_path / "plugin.json").write_text(json.dumps(manifest))

    with pytest.raises(ValidationError, match=message):
        load_agent_plugin(tmp_path)


def test_ignores_unknown_manifest_fields_with_warning(tmp_path: Path) -> None:
    """Unknown core fields are reported but do not reject the plugin."""
    _write_manifest(tmp_path, typo=True)
    _write_skill(tmp_path, "review")

    plugin = load_agent_plugin(tmp_path)

    assert plugin.skills == ["review"]
    assert plugin.warnings == ["plugin.json: ignoring unknown field 'typo'"]


def test_rejects_extension_path_outside_plugin(tmp_path: Path) -> None:
    """Extension paths cannot escape the plugin root through symlinks."""
    outside = tmp_path.parent / "outside-commands"
    outside.mkdir()
    (outside / "bad.md").write_text("# Bad")
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    _write_manifest(
        tmp_path,
        extensions={
            "dev.getlola": {"commands": "./escape"},
        },
    )

    plugin = load_agent_plugin(tmp_path)

    assert plugin.commands == []
    assert "outside plugin root" in plugin.warnings[0]


def test_skips_invalid_mcp_entries_independently(tmp_path: Path) -> None:
    """One bad MCP server does not suppress independent valid servers."""
    _write_manifest(tmp_path)
    (tmp_path / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "good": {"type": "stdio", "command": "uvx"},
                    "bad": {"type": "stdio", "command": "uvx extra"},
                },
            }
        )
    )

    plugin = load_agent_plugin(tmp_path)

    assert plugin.mcps == ["good"]
    assert "bad" in plugin.warnings[0]


def test_skips_nonconforming_skill_independently(tmp_path: Path) -> None:
    """Invalid skills are skipped without rejecting the plugin."""
    _write_manifest(tmp_path)
    _write_skill(tmp_path, "good")
    bad = tmp_path / "skills" / "bad"
    bad.mkdir()
    (bad / "SKILL.md").write_text("# Missing frontmatter")

    plugin = load_agent_plugin(tmp_path)

    assert plugin.skills == ["good"]
    assert "skills/bad/SKILL.md" in plugin.warnings[0]


def test_materializes_portable_mcp_values(tmp_path: Path) -> None:
    """Portable types, paths, and placeholders become target-neutral data."""
    root = tmp_path / "plugin"
    data = tmp_path / "data"
    root.mkdir()
    servers = {
        "local": {
            "type": "stdio",
            "command": "./bin/server",
            "args": ["${PLUGIN_ROOT}/config.json"],
            "env": {"CACHE": "${PLUGIN_DATA}/cache"},
            "cwd": "./work",
        },
        "remote": {
            "type": "streamable-http",
            "url": "https://example.com/mcp",
        },
    }

    result = materialize_mcps(servers, root, data)

    assert "type" not in result["local"]
    assert result["local"]["command"] == str(root / "bin/server")
    assert result["local"]["args"] == [str(root.resolve() / "config.json")]
    assert result["local"]["env"] == {
        "CACHE": str(data.resolve() / "cache"),
        "PLUGIN_ROOT": str(root.resolve()),
        "PLUGIN_DATA": str(data.resolve()),
    }
    assert result["local"]["cwd"] == str(root / "work")
    assert result["remote"]["type"] == "http"


def test_manifest_metadata_validation_and_non_object_extensions(
    tmp_path: Path,
) -> None:
    """Validate typed metadata while treating extensions as non-fatal."""
    _write_manifest(
        tmp_path,
        author={"name": 1},
        keywords="not-a-list",
    )

    with pytest.raises(ValidationError) as error:
        load_agent_plugin(tmp_path)

    assert "invalid author" in str(error.value)
    assert "keywords must be an array" in str(error.value)

    _write_manifest(tmp_path, extensions="invalid")
    plugin = load_agent_plugin(tmp_path)
    assert plugin.warnings == ["plugin.json: ignoring non-object extensions"]


def test_ignores_unimplemented_extension_value(tmp_path: Path) -> None:
    """Unknown namespace values are opaque even when not objects."""
    _write_manifest(tmp_path, extensions={"org.example.client": "opaque"})

    plugin = load_agent_plugin(tmp_path)

    assert plugin.warnings == []


def test_extension_path_validation_and_conventional_directory(
    tmp_path: Path,
) -> None:
    """Read conventional extension directories and report invalid paths."""
    _write_manifest(
        tmp_path,
        extensions={
            "dev.getlola": {
                "commands": "commands",
                "instructions": 42,
            }
        },
    )
    commands = tmp_path / "dev.getlola" / "commands"
    commands.mkdir(parents=True)
    (commands / "check.md").write_text("# Check")

    plugin = load_agent_plugin(tmp_path)

    assert plugin.commands == []
    assert len(plugin.warnings) == 2
    assert "expected a './'" in plugin.warnings[0]


@pytest.mark.parametrize(
    ("mcp", "warning"),
    [
        ({"mcpServers": {}}, "unsupported or missing $schema"),
        (
            {"$schema": MCP_SCHEMA, "mcpServers": {}, "extra": True},
            "invalid top-level fields",
        ),
        ({"$schema": MCP_SCHEMA, "mcpServers": []}, "must be an object"),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "stdio",
                        "command": "uvx",
                        "env": {"PLUGIN_ROOT": "bad"},
                    }
                },
            },
            "reserved variable",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "streamable-http",
                        "url": "file:///bad",
                    }
                },
            },
            "http or https",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "sse",
                        "url": "https://example.com",
                        "headers": {"Authorization": "${TOKEN}"},
                    }
                },
            },
            "cannot contain placeholders",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {"type": "stdio", "command": "/tmp/server"},
                },
            },
            "bare name or a ./ plugin path",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {"type": "stdio", "command": "bin/server"},
                },
            },
            "bare name or a ./ plugin path",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "streamable-http",
                        "url": "http://example.com/mcp",
                    }
                },
            },
            "https for non-loopback hosts",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "sse",
                        "url": "https://user:pw@example.com/mcp",
                    }
                },
            },
            "userinfo or a fragment",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {
                        "type": "sse",
                        "url": "https://example.com/mcp#frag",
                    }
                },
            },
            "userinfo or a fragment",
        ),
        (
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "bad": {"type": "sse", "url": "https:///mcp"},
                },
            },
            "absolute http or https URL",
        ),
    ],
)
def test_invalid_mcp_shapes_are_component_failures(
    tmp_path: Path,
    mcp: dict[str, object],
    warning: str,
) -> None:
    """Malformed MCP documents and entries are reported and skipped."""
    _write_manifest(tmp_path)
    (tmp_path / "mcp.json").write_text(json.dumps(mcp))

    plugin = load_agent_plugin(tmp_path)

    assert plugin.mcps == []
    assert warning in plugin.warnings[0]


def test_materializes_default_stdio_environment(tmp_path: Path) -> None:
    """Stdio servers receive required runtime variables and default cwd."""
    root = tmp_path / "plugin"
    data = tmp_path / "data"
    root.mkdir()

    result = materialize_mcps(
        {"local": {"type": "stdio", "command": "uvx"}},
        root,
        data,
    )

    assert result["local"]["cwd"] == str(root.resolve())
    assert result["local"]["env"] == {
        "PLUGIN_ROOT": str(root.resolve()),
        "PLUGIN_DATA": str(data.resolve()),
    }


def test_scaffold_minimal_and_invalid_name(tmp_path: Path) -> None:
    """Minimal scaffolds stay conformant and reject invalid names."""
    options = ScaffoldOptions(
        skill_name=None,
        command_name=None,
        agent_name=None,
        include_mcps=False,
        include_instructions=False,
    )

    scaffold_agent_plugin(tmp_path / "valid", "valid.plugin", options)

    assert (tmp_path / "valid" / "plugin.json").exists()
    assert not (tmp_path / "valid" / "mcp.json").exists()
    with pytest.raises(ValidationError, match="invalid Agent Plugins name"):
        scaffold_agent_plugin(tmp_path / "bad", "Bad_Name", options)


def test_scaffold_is_rerunnable(tmp_path: Path) -> None:
    """Re-scaffolding an existing package refreshes files, not crash."""
    options = ScaffoldOptions(
        skill_name="example-skill",
        command_name="example-command",
        agent_name="example-agent",
        include_mcps=True,
        include_instructions=True,
    )

    scaffold_agent_plugin(tmp_path, "portable-plugin", options)
    scaffold_agent_plugin(tmp_path, "portable-plugin", options)

    assert (tmp_path / "skills" / "example-skill" / "SKILL.md").exists()


def _register_plugin(modules_dir: Path) -> Path:
    """Register a plugin with MCP servers in the mock registry."""
    root = modules_dir / "portable-plugin"
    root.mkdir()
    _write_manifest(root)
    _write_skill(root, "review")
    (root / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": MCP_SCHEMA,
                "mcpServers": {
                    "local": {
                        "type": "stdio",
                        "command": "uvx",
                        "args": ["serve", "${PLUGIN_ROOT}/rules.json"],
                    },
                    "remote": {
                        "type": "streamable-http",
                        "url": "https://example.com/mcp",
                    },
                },
            }
        )
    )
    return root


def test_install_materializes_plugin_mcps(
    tmp_path: Path, mock_lola_home: dict, cli_runner
) -> None:
    """Install writes target MCP config with expanded plugin paths."""
    _register_plugin(mock_lola_home["modules"])
    project = tmp_path / "project"
    project.mkdir()

    result = cli_runner.invoke(
        install_cmd,
        ["portable-plugin", str(project), "-a", "claude-code", "-f"],
    )

    assert result.exit_code == 0, result.output
    servers = json.loads((project / ".mcp.json").read_text())["mcpServers"]
    local_copy = (project / ".lola" / "modules" / "portable-plugin").resolve()
    assert servers["local"]["args"] == [
        "serve",
        str(local_copy / "rules.json"),
    ]
    assert servers["local"]["env"]["PLUGIN_ROOT"] == str(local_copy)
    assert servers["local"]["cwd"] == str(local_copy)
    assert servers["remote"] == {
        "type": "http",
        "url": "https://example.com/mcp",
    }
    assert (project / ".lola" / "plugin-data" / "portable-plugin").is_dir()


def test_update_rematerializes_plugin_mcps(
    tmp_path: Path, mock_lola_home: dict, cli_runner
) -> None:
    """Update regenerates target MCP config from the plugin source."""
    root = _register_plugin(mock_lola_home["modules"])
    project = tmp_path / "project"
    project.mkdir()
    result = cli_runner.invoke(
        install_cmd,
        ["portable-plugin", str(project), "-a", "claude-code", "-f"],
    )
    assert result.exit_code == 0, result.output

    mcp = json.loads((root / "mcp.json").read_text())
    mcp["mcpServers"]["extra"] = {
        "type": "sse",
        "url": "https://example.com/sse",
    }
    (root / "mcp.json").write_text(json.dumps(mcp))

    result = cli_runner.invoke(update_cmd, ["portable-plugin"])

    assert result.exit_code == 0, result.output
    servers = json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert servers["extra"] == {
        "type": "sse",
        "url": "https://example.com/sse",
    }
    local_copy = (project / ".lola" / "modules" / "portable-plugin").resolve()
    assert servers["local"]["env"]["PLUGIN_ROOT"] == str(local_copy)


def test_command_expands_plugin_root_placeholder(tmp_path: Path) -> None:
    """${PLUGIN_ROOT} is expanded in command, not just in args."""
    servers = materialize_mcps(
        {"s": {"type": "stdio", "command": "${PLUGIN_ROOT}/bin/serve"}},
        tmp_path / "root",
        tmp_path / "data",
    )
    assert servers["s"]["command"] == str((tmp_path / "root").resolve()) + (
        "/bin/serve"
    )


def test_empty_plugin_is_not_a_module(tmp_path: Path) -> None:
    """A manifest with no installable content yields no module."""
    root = tmp_path / "empty"
    root.mkdir()
    _write_manifest(root)
    assert Module.from_path(root) is None


@pytest.mark.parametrize(
    ("dirname", "expected"),
    [
        ("My_Project", "my-project"),
        ("my-plugin", "my-plugin"),
        ("_weird__name_", "weird-name"),
    ],
)
def test_plugin_name_from_directory(dirname: str, expected: str) -> None:
    """Inferred names are slugified rather than rejected."""
    from lola.agent_plugin_scaffold import plugin_name_from_directory

    assert plugin_name_from_directory(dirname) == expected


def test_folder_source_finds_plugin_root_without_skills(tmp_path: Path) -> None:
    """A commands-only plugin registers as the package root, not dev.getlola."""
    from lola.parsers import FolderSourceHandler

    source = tmp_path / "repository-name"
    (source / "dev.getlola" / "commands").mkdir(parents=True)
    _write_manifest(source, name="cmdonly")
    (source / "dev.getlola" / "commands" / "foo.md").write_text(
        "---\ndescription: x\n---\n"
    )

    dest = tmp_path / "modules"
    dest.mkdir()
    fetched = FolderSourceHandler().fetch(str(source), dest)

    assert (fetched / "plugin.json").is_file()
