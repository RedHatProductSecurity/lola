"""Tests for AssistantTarget ABC scope parameter support."""

import json
from pathlib import Path

import pytest

from lola.targets.base import (
    _PLUGIN_SCHEMA,
    AssistantTarget,
    PluginLayout,
    PluginManifest,
)


class MockTarget(AssistantTarget):
    """Mock target for testing ABC."""

    name = "mock"
    supports_agents = True
    uses_managed_section = False

    def get_skill_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".mock" / "skills"
        return Path(project_path) / ".mock" / "skills"

    def get_command_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".mock" / "commands"
        return Path(project_path) / ".mock" / "commands"

    def get_agent_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".mock" / "agents"
        return Path(project_path) / ".mock" / "agents"

    def get_instructions_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / "MOCK.md"
        return Path(project_path) / "MOCK.md"

    def get_mcp_path(self, project_path: str, scope: str = "project") -> Path:
        if scope == "user":
            return Path.home() / ".mock.json"
        return Path(project_path) / ".mock.json"

    # Minimal stubs for other required methods
    def generate_skill(self, source_path, dest_path, skill_name, project_path=None):
        return True

    def generate_command(self, source_path, dest_dir, cmd_name, module_name):
        return True

    def generate_agent(self, source_path, dest_dir, agent_name, module_name):
        return True

    def generate_instructions(
        self, source: Path | str | list[str], dest_path: Path, module_name: str
    ) -> bool:
        return True

    def remove_skill(self, dest_path, skill_name):
        return True

    def remove_instructions(self, dest_path, module_name):
        return True

    def generate_skills_batch(self, dest_file, module_name, skills, project_path):
        return True

    def get_command_filename(self, module_name, cmd_name):
        return f"{module_name}.{cmd_name}.md"

    def get_agent_filename(self, module_name, agent_name):
        return f"{module_name}.{agent_name}.md"

    def generate_mcps(self, mcps, dest_path, module_name):
        return True

    def remove_mcps(
        self, dest_path: Path, module_name: str, mcp_names: list[str] | None = None
    ) -> bool:
        return True

    def remove_command(self, dest_dir, cmd_name, module_name):
        return True

    def remove_agent(self, dest_dir, agent_name, module_name):
        return True


def test_get_skill_path_project_scope():
    target = MockTarget()
    path = target.get_skill_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.mock/skills")


def test_get_skill_path_user_scope():
    target = MockTarget()
    path = target.get_skill_path("/home/user/project", "user")
    assert path == Path.home() / ".mock" / "skills"


def test_get_command_path_project_scope():
    target = MockTarget()
    path = target.get_command_path("/home/user/project", "project")
    assert path == Path("/home/user/project/.mock/commands")


def test_get_command_path_user_scope():
    target = MockTarget()
    path = target.get_command_path("/home/user/project", "user")
    assert path == Path.home() / ".mock" / "commands"


# =============================================================================
# PluginManifest tests
# =============================================================================


class TestPluginManifest:
    def test_name_required(self):
        with pytest.raises(ValueError, match="non-empty name"):
            PluginManifest(name="")

    def test_to_dict_minimal(self):
        m = PluginManifest(name="my-plugin")
        d = m.to_dict()
        assert d["$schema"] == _PLUGIN_SCHEMA
        assert d["name"] == "my-plugin"
        assert "version" not in d

    def test_to_dict_all_fields(self):
        m = PluginManifest(
            name="my-plugin",
            version="1.0.0",
            description="A test plugin",
            author={"name": "Test", "email": "t@t.com", "extra": "ignored"},
            homepage="https://example.com",
            repository="https://github.com/test/plugin",
            license="MIT",
            keywords=["test", "plugin"],
            extensions={"com.example": {"key": "value"}},
        )
        d = m.to_dict()
        assert d["version"] == "1.0.0"
        assert d["description"] == "A test plugin"
        assert d["author"] == {"name": "Test", "email": "t@t.com"}
        assert "extra" not in d["author"]
        assert d["homepage"] == "https://example.com"
        assert d["repository"] == "https://github.com/test/plugin"
        assert d["license"] == "MIT"
        assert d["keywords"] == ["test", "plugin"]
        assert d["extensions"] == {"com.example": {"key": "value"}}

    def test_write(self, tmp_path):
        m = PluginManifest(name="my-plugin", version="1.0.0")
        manifest_dir = tmp_path / "manifest"
        result = m.write(manifest_dir)
        assert result is True
        assert (manifest_dir / "plugin.json").exists()
        data = json.loads((manifest_dir / "plugin.json").read_text())
        assert data["name"] == "my-plugin"
        assert data["version"] == "1.0.0"

    def test_from_file(self, tmp_path):
        plugin_json = tmp_path / "plugin.json"
        plugin_json.write_text(
            json.dumps(
                {
                    "$schema": _PLUGIN_SCHEMA,
                    "name": "existing-plugin",
                    "version": "2.0.0",
                    "description": "From file",
                }
            )
        )
        m = PluginManifest.from_file(plugin_json)
        assert m is not None
        assert m.name == "existing-plugin"
        assert m.version == "2.0.0"
        assert m.description == "From file"

    def test_from_file_missing(self, tmp_path):
        m = PluginManifest.from_file(tmp_path / "nonexistent.json")
        assert m is None

    def test_from_file_invalid_json(self, tmp_path):
        bad_file = tmp_path / "plugin.json"
        bad_file.write_text("not json")
        m = PluginManifest.from_file(bad_file)
        assert m is None

    def test_from_file_no_name(self, tmp_path):
        no_name = tmp_path / "plugin.json"
        no_name.write_text(json.dumps({"version": "1.0.0"}))
        m = PluginManifest.from_file(no_name)
        assert m is None


# =============================================================================
# PluginLayout tests
# =============================================================================


class TestPluginLayout:
    def test_resolve_root_project(self):
        layout = PluginLayout(
            plugin_root_template=".test/plugins/{name}",
            manifest_path=".test-plugin",
            mcp_path="mcp-config.json",
        )
        root = layout.resolve_root("my-pack", "project", "/home/user/project")
        assert root == Path("/home/user/project/.test/plugins/my-pack")

    def test_resolve_root_user(self):
        layout = PluginLayout(
            plugin_root_template="~/.test/plugins/{name}",
            manifest_path=".test-plugin",
            mcp_path="mcp-config.json",
        )
        root = layout.resolve_root("my-pack", "user", None)
        assert root == Path.home() / ".test" / "plugins" / "my-pack"

    def test_resolve_paths_all(self):
        layout = PluginLayout(
            plugin_root_template=".test/plugins/{name}",
            manifest_path=".test-plugin",
            mcp_path="mcp-config.json",
        )
        root = Path("/project/.test/plugins/my-pack")
        paths = layout.resolve_paths(root)
        assert paths["skills"] == root / "skills"
        assert paths["agents"] == root / "agents"
        assert paths["commands"] == root / "commands"
        assert paths["mcp"] == root / "mcp-config.json"
        assert paths["manifest"] == root / ".test-plugin"
        assert paths["instructions"] is None

    def test_resolve_paths_none_components(self):
        layout = PluginLayout(
            plugin_root_template=".test/{name}",
            manifest_path=None,
            mcp_path=None,
            agents_path=None,
            commands_path=None,
        )
        root = Path("/project/.test/my-pack")
        paths = layout.resolve_paths(root)
        assert paths["skills"] == root / "skills"
        assert paths["agents"] is None
        assert paths["commands"] is None
        assert paths["mcp"] is None
        assert paths["manifest"] == root

    def test_defaults(self):
        layout = PluginLayout(
            plugin_root_template=".test/{name}",
            manifest_path=".test-plugin",
            mcp_path="mcp.json",
        )
        assert layout.skills_path == "skills"
        assert layout.agents_path == "agents"
        assert layout.commands_path == "commands"
        assert layout.instructions_path is None


# =============================================================================
# AssistantTarget plugin support tests
# =============================================================================


def test_get_plugin_layout_default_none():
    target = MockTarget()
    assert target.get_plugin_layout() is None
    assert target.get_plugin_layout("user") is None


def test_build_plugin_manifest_raises_for_unsupported():
    from unittest.mock import MagicMock

    target = MockTarget()
    mock_module = MagicMock()
    with pytest.raises(NotImplementedError, match="mock does not support plugins"):
        target.build_plugin_manifest(mock_module)
