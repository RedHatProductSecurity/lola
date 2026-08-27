"""Tests for ClaudeCodeTarget scope-aware path resolution."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from lola.targets.claude_code import ClaudeCodeTarget


def test_claude_code_skill_path_project_scope():
    target = ClaudeCodeTarget()
    path = target.get_skill_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.claude/skills")


def test_claude_code_skill_path_user_scope():
    target = ClaudeCodeTarget()
    path = target.get_skill_path("/home/user/project", "user")
    assert path == Path.home() / ".claude" / "skills"


def test_claude_code_command_path_user_scope():
    target = ClaudeCodeTarget()
    path = target.get_command_path("/home/user/project", "user")
    assert path == Path.home() / ".claude" / "commands"


def test_claude_code_agent_path_user_scope():
    target = ClaudeCodeTarget()
    path = target.get_agent_path("/home/user/project", "user")
    assert path == Path.home() / ".claude" / "agents"


def test_claude_code_instructions_path_user_scope():
    target = ClaudeCodeTarget()
    path = target.get_instructions_path("/home/user/project", "user")
    assert path == Path.home() / ".claude" / "CLAUDE.md"


def test_claude_code_mcp_path_user_scope():
    target = ClaudeCodeTarget()
    path = target.get_mcp_path("/home/user/project", "user")
    assert path == Path.home() / ".mcp.json"


# --- Project scope tests for remaining methods ---


def test_claude_code_command_path_project_scope():
    target = ClaudeCodeTarget()
    result = target.get_command_path("/home/user/project", scope="project")
    assert result == Path("/home/user/project/.claude/commands")


def test_claude_code_agent_path_project_scope():
    target = ClaudeCodeTarget()
    result = target.get_agent_path("/home/user/project", scope="project")
    assert result == Path("/home/user/project/.claude/agents")


def test_claude_code_instructions_path_project_scope():
    target = ClaudeCodeTarget()
    result = target.get_instructions_path("/home/user/project", scope="project")
    assert result == Path("/home/user/project/CLAUDE.md")


def test_claude_code_mcp_path_project_scope():
    target = ClaudeCodeTarget()
    result = target.get_mcp_path("/home/user/project", scope="project")
    assert result == Path("/home/user/project/.mcp.json")


# --- Default scope tests (no explicit scope argument) ---


def test_claude_code_skill_path_default_scope():
    target = ClaudeCodeTarget()
    result = target.get_skill_path("/home/user/project")
    assert result == Path("/home/user/project/.claude/skills")


def test_claude_code_command_path_default_scope():
    target = ClaudeCodeTarget()
    result = target.get_command_path("/home/user/project")
    assert result == Path("/home/user/project/.claude/commands")


def test_claude_code_agent_path_default_scope():
    target = ClaudeCodeTarget()
    result = target.get_agent_path("/home/user/project")
    assert result == Path("/home/user/project/.claude/agents")


def test_claude_code_instructions_path_default_scope():
    target = ClaudeCodeTarget()
    result = target.get_instructions_path("/home/user/project")
    assert result == Path("/home/user/project/CLAUDE.md")


def test_claude_code_mcp_path_default_scope():
    target = ClaudeCodeTarget()
    result = target.get_mcp_path("/home/user/project")
    assert result == Path("/home/user/project/.mcp.json")


# --- Plugin tests ---


def test_claude_code_plugin_layout_project():
    target = ClaudeCodeTarget()
    layout = target.get_plugin_layout("project")
    assert layout is not None
    root = layout.resolve_root("my-pack", "project", "/home/user/project")
    assert root == Path("/home/user/project/.claude/skills/my-pack")


def test_claude_code_plugin_layout_user():
    target = ClaudeCodeTarget()
    layout = target.get_plugin_layout("user")
    assert layout is not None
    root = layout.resolve_root("my-pack", "user", None)
    assert root == Path.home() / ".claude" / "skills" / "my-pack"


def test_claude_code_plugin_layout_manifest_path():
    target = ClaudeCodeTarget()
    layout = target.get_plugin_layout("project")
    assert layout is not None
    root = layout.resolve_root("my-pack", "project", "/project")
    paths = layout.resolve_paths(root)
    assert paths["manifest"] == root / ".claude-plugin"


def test_claude_code_plugin_layout_mcp_path():
    target = ClaudeCodeTarget()
    layout = target.get_plugin_layout("project")
    assert layout is not None
    root = layout.resolve_root("my-pack", "project", "/project")
    paths = layout.resolve_paths(root)
    assert paths["mcp"] == root / ".mcp.json"


def test_claude_code_build_manifest_uses_existing(tmp_path):
    target = ClaudeCodeTarget()
    (tmp_path / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "from-pack",
                "version": "2.0.0",
            }
        )
    )
    module = MagicMock()
    module.name = "my-pack"
    module.content_path = tmp_path
    manifest = target.build_plugin_manifest(module)
    assert manifest.name == "from-pack"
    assert manifest.version == "2.0.0"
