"""Tests for CursorTarget scope-aware path resolution."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from lola.targets.cursor import CursorTarget


# --- User scope tests ---


def test_cursor_skill_path_user_scope():
    target = CursorTarget()
    path = target.get_skill_path("/home/user/project", "user")
    assert path == Path.home() / ".cursor" / "skills"


def test_cursor_command_path_user_scope():
    target = CursorTarget()
    path = target.get_command_path("/home/user/project", "user")
    assert path == Path.home() / ".cursor" / "commands"


def test_cursor_agent_path_user_scope():
    target = CursorTarget()
    path = target.get_agent_path("/home/user/project", "user")
    assert path == Path.home() / ".cursor" / "agents"


def test_cursor_instructions_path_user_scope():
    target = CursorTarget()
    path = target.get_instructions_path("/home/user/project", "user")
    assert path == Path.home() / ".cursor" / "rules"


def test_cursor_mcp_path_user_scope():
    target = CursorTarget()
    path = target.get_mcp_path("/home/user/project", "user")
    assert path == Path.home() / ".cursor" / "mcp.json"


# --- Project scope tests ---


def test_cursor_skill_path_project_scope():
    target = CursorTarget()
    path = target.get_skill_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.cursor/skills")


def test_cursor_command_path_project_scope():
    target = CursorTarget()
    path = target.get_command_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.cursor/commands")


def test_cursor_agent_path_project_scope():
    target = CursorTarget()
    path = target.get_agent_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.cursor/agents")


def test_cursor_instructions_path_project_scope():
    target = CursorTarget()
    path = target.get_instructions_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.cursor/rules")


def test_cursor_mcp_path_project_scope():
    target = CursorTarget()
    path = target.get_mcp_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.cursor/mcp.json")


# --- Default scope tests (no explicit scope argument) ---


def test_cursor_skill_path_default_scope():
    target = CursorTarget()
    result = target.get_skill_path("/home/user/project")
    assert result == Path("/home/user/project/.cursor/skills")


def test_cursor_command_path_default_scope():
    target = CursorTarget()
    result = target.get_command_path("/home/user/project")
    assert result == Path("/home/user/project/.cursor/commands")


def test_cursor_agent_path_default_scope():
    target = CursorTarget()
    result = target.get_agent_path("/home/user/project")
    assert result == Path("/home/user/project/.cursor/agents")


def test_cursor_instructions_path_default_scope():
    target = CursorTarget()
    result = target.get_instructions_path("/home/user/project")
    assert result == Path("/home/user/project/.cursor/rules")


def test_cursor_mcp_path_default_scope():
    target = CursorTarget()
    result = target.get_mcp_path("/home/user/project")
    assert result == Path("/home/user/project/.cursor/mcp.json")


# --- Plugin tests ---


def test_cursor_plugin_layout_project_not_supported():
    target = CursorTarget()
    assert target.get_plugin_layout("project") is None


def test_cursor_plugin_layout_user():
    target = CursorTarget()
    layout = target.get_plugin_layout("user")
    assert layout is not None
    root = layout.resolve_root("my-pack", "user", None)
    assert root == Path.home() / ".cursor" / "plugins" / "local" / "my-pack"


def test_cursor_plugin_layout_manifest_path():
    target = CursorTarget()
    layout = target.get_plugin_layout("user")
    assert layout is not None
    root = layout.resolve_root("my-pack", "user", None)
    paths = layout.resolve_paths(root)
    # Global spec: plugin.json at root, not .cursor-plugin/
    assert paths["manifest"] == root


def test_cursor_plugin_layout_mcp_path():
    target = CursorTarget()
    layout = target.get_plugin_layout("user")
    assert layout is not None
    root = layout.resolve_root("my-pack", "user", None)
    paths = layout.resolve_paths(root)
    assert paths["mcp"] == root / "mcp.json"


def test_cursor_build_manifest_uses_existing(tmp_path):
    target = CursorTarget()
    (tmp_path / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "from-pack",
                "version": "3.0.0",
            }
        )
    )
    module = MagicMock()
    module.name = "my-pack"
    module.content_path = tmp_path
    manifest = target.build_plugin_manifest(module)
    assert manifest.name == "from-pack"
    assert manifest.version == "3.0.0"
