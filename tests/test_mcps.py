"""Tests for MCP server functionality."""

import json
from pathlib import Path

import pytest

from lola import frontmatter as fm
from lola.models import Installation, Module
from lola.targets import (
    ClaudeCodeTarget,
    CopilotVSCodeTarget,
    CursorTarget,
    GeminiTarget,
    OpenCodeTarget,
    _merge_mcps_into_file,
    _remove_mcps_from_file,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_mcps_json():
    """Return sample mcps.json content."""
    return {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
            },
            "git": {
                "command": "uvx",
                "args": ["mcp-server-git", "--repository", "."],
            },
        }
    }


@pytest.fixture
def module_with_mcps(tmp_path, sample_mcps_json):
    """Create a module with mcps.json for testing."""
    module_dir = tmp_path / "mcp-module"
    module_dir.mkdir()

    # Create a skill (required for valid module)
    skills_dir = module_dir / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "skill1"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---

# Skill 1

This is a test skill.
""")

    # Create mcps.json
    (module_dir / "mcps.json").write_text(json.dumps(sample_mcps_json, indent=2))

    return module_dir


@pytest.fixture
def module_only_mcps(tmp_path, sample_mcps_json):
    """Create a module that only has mcps.json (no skills/commands/agents)."""
    module_dir = tmp_path / "mcp-only-module"
    module_dir.mkdir()

    # Create only mcps.json
    (module_dir / "mcps.json").write_text(json.dumps(sample_mcps_json, indent=2))

    return module_dir


# =============================================================================
# MCP Discovery Tests
# =============================================================================


class TestMCPDiscovery:
    """Tests for Module.from_path() MCP discovery."""

    def test_module_discovers_mcps(self, module_with_mcps):
        """Module.from_path() finds mcps.json and lists server names."""
        module = Module.from_path(module_with_mcps)

        assert module is not None
        assert module.mcps == ["git", "github"]  # sorted

    def test_module_without_mcps(self, tmp_path):
        """Module works without mcps.json."""
        module_dir = tmp_path / "no-mcp-module"
        module_dir.mkdir()

        # Create a skill
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---
# Skill 1
""")

        module = Module.from_path(module_dir)

        assert module is not None
        assert module.mcps == []

    def test_module_with_only_mcps_is_valid(self, module_only_mcps):
        """A module with only mcps.json (no skills/commands/agents) is valid."""
        module = Module.from_path(module_only_mcps)

        assert module is not None
        assert module.mcps == ["git", "github"]
        assert module.skills == []
        assert module.commands == []
        assert module.agents == []

    def test_invalid_mcps_json_ignored(self, tmp_path):
        """Malformed mcps.json is ignored gracefully."""
        module_dir = tmp_path / "bad-mcp-module"
        module_dir.mkdir()

        # Create a skill
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---
# Skill 1
""")

        # Create invalid mcps.json
        (module_dir / "mcps.json").write_text("{ invalid json }")

        module = Module.from_path(module_dir)

        assert module is not None
        assert module.mcps == []  # Ignored due to parse error


# =============================================================================
# MCP Helper Function Tests
# =============================================================================


class TestMCPHelpers:
    """Tests for _merge_mcps_into_file and _remove_mcps_from_file."""

    def test_merge_creates_new_file(self, tmp_path):
        """_merge_mcps_into_file creates new file if it doesn't exist."""
        mcp_file = tmp_path / ".mcp.json"
        servers = {
            "server1": {"command": "test", "args": []},
        }

        result = _merge_mcps_into_file(mcp_file, "mymodule", servers)

        assert result is True
        assert mcp_file.exists()

        content = json.loads(mcp_file.read_text())
        assert "mcpServers" in content
        assert "server1" in content["mcpServers"]
        assert content["mcpServers"]["server1"]["command"] == "test"

    def test_merge_into_existing_file(self, tmp_path):
        """_merge_mcps_into_file merges into existing file."""
        mcp_file = tmp_path / ".mcp.json"

        # Create existing config
        existing = {
            "mcpServers": {
                "other-server": {"command": "existing", "args": []},
            }
        }
        mcp_file.write_text(json.dumps(existing))

        servers = {
            "new-server": {"command": "new", "args": []},
        }

        result = _merge_mcps_into_file(mcp_file, "mymodule", servers)

        assert result is True

        content = json.loads(mcp_file.read_text())
        assert "other-server" in content["mcpServers"]  # Preserved
        assert "new-server" in content["mcpServers"]  # Added (no prefix)

    def test_merge_preserves_non_mcp_keys(self, tmp_path):
        """_merge_mcps_into_file preserves other keys like theme."""
        mcp_file = tmp_path / "settings.json"

        # Create existing config with other settings
        existing = {
            "theme": "dark",
            "mcpServers": {},
        }
        mcp_file.write_text(json.dumps(existing))

        servers = {"server1": {"command": "test", "args": []}}

        _merge_mcps_into_file(mcp_file, "mymodule", servers)

        content = json.loads(mcp_file.read_text())
        assert content["theme"] == "dark"  # Preserved
        assert "server1" in content["mcpServers"]

    def test_remove_mcps_removes_module_servers(self, tmp_path):
        """_remove_mcps_from_file removes specific named servers."""
        mcp_file = tmp_path / ".mcp.json"

        # Create existing config with multiple servers
        existing = {
            "mcpServers": {
                "server1": {"command": "a", "args": []},
                "server2": {"command": "a", "args": []},
                "server3": {"command": "b", "args": []},
            }
        }
        mcp_file.write_text(json.dumps(existing))

        result = _remove_mcps_from_file(
            mcp_file, "modA", mcp_names=["server1", "server2"]
        )

        assert result is True

        content = json.loads(mcp_file.read_text())
        assert "server1" not in content["mcpServers"]
        assert "server2" not in content["mcpServers"]
        assert "server3" in content["mcpServers"]  # Preserved

    def test_remove_mcps_deletes_empty_file(self, tmp_path):
        """_remove_mcps_from_file deletes file if mcpServers becomes empty."""
        mcp_file = tmp_path / ".mcp.json"

        # Create config with only one server
        existing = {
            "mcpServers": {
                "server1": {"command": "a", "args": []},
            }
        }
        mcp_file.write_text(json.dumps(existing))

        result = _remove_mcps_from_file(mcp_file, "modA", mcp_names=["server1"])

        assert result is True
        assert not mcp_file.exists()  # File deleted

    def test_remove_mcps_preserves_other_keys(self, tmp_path):
        """_remove_mcps_from_file preserves other keys when mcpServers becomes empty."""
        mcp_file = tmp_path / "settings.json"

        existing = {
            "theme": "dark",
            "mcpServers": {
                "server1": {"command": "a", "args": []},
            },
        }
        mcp_file.write_text(json.dumps(existing))

        _remove_mcps_from_file(mcp_file, "modA", mcp_names=["server1"])

        assert mcp_file.exists()  # File preserved due to other keys
        content = json.loads(mcp_file.read_text())
        assert content["theme"] == "dark"
        assert content["mcpServers"] == {}

    def test_remove_mcps_none_is_noop(self, tmp_path):
        """_remove_mcps_from_file with mcp_names=None leaves file unchanged."""
        mcp_file = tmp_path / ".mcp.json"
        original = json.dumps({"mcpServers": {}})
        mcp_file.write_text(original)

        result = _remove_mcps_from_file(mcp_file, "modA", mcp_names=None)

        assert result is True
        assert mcp_file.exists()
        assert mcp_file.read_text() == original

    def test_remove_mcps_empty_list_is_noop(self, tmp_path):
        """_remove_mcps_from_file with mcp_names=[] leaves file unchanged."""
        mcp_file = tmp_path / ".mcp.json"
        original = json.dumps({"mcpServers": {}})
        mcp_file.write_text(original)

        result = _remove_mcps_from_file(mcp_file, "modA", mcp_names=[])

        assert result is True
        assert mcp_file.exists()
        assert mcp_file.read_text() == original


# =============================================================================
# Target MCP Path Tests
# =============================================================================


class TestTargetMCPPaths:
    """Tests for target get_mcp_path() methods."""

    def test_claude_mcp_path(self):
        """ClaudeCodeTarget returns correct MCP path."""
        target = ClaudeCodeTarget()
        path = target.get_mcp_path("/project")

        assert path == Path("/project/.mcp.json")

    def test_cursor_mcp_path(self):
        """CursorTarget returns correct MCP path."""
        target = CursorTarget()
        path = target.get_mcp_path("/project")

        assert path == Path("/project/.cursor/mcp.json")

    def test_gemini_mcp_path(self):
        """GeminiTarget returns correct MCP path."""
        target = GeminiTarget()
        path = target.get_mcp_path("/project")

        assert path == Path("/project/.gemini/settings.json")

    def test_opencode_mcp_path(self):
        """OpenCodeTarget returns correct MCP path (opencode.json at project root)."""
        target = OpenCodeTarget()
        path = target.get_mcp_path("/project")

        assert path == Path("/project/opencode.json")


# =============================================================================
# Target MCP Generation Tests
# =============================================================================


class TestTargetMCPGeneration:
    """Tests for target generate_mcps() methods."""

    def test_claude_generates_mcp_json(self, tmp_path):
        """ClaudeCodeTarget creates .mcp.json correctly."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        servers = {
            "github": {"command": "npx", "args": ["-y", "@mcp/github"]},
        }

        result = target.generate_mcps(servers, mcp_path, "git-tools")

        assert result is True
        assert mcp_path.exists()

        content = json.loads(mcp_path.read_text())
        assert "github" in content["mcpServers"]

    def test_cursor_generates_mcp_json(self, tmp_path):
        """CursorTarget creates .cursor/mcp.json correctly."""
        target = CursorTarget()
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_path = cursor_dir / "mcp.json"

        servers = {
            "github": {"command": "npx", "args": ["-y", "@mcp/github"]},
        }

        result = target.generate_mcps(servers, mcp_path, "git-tools")

        assert result is True
        assert mcp_path.exists()

        content = json.loads(mcp_path.read_text())
        assert "github" in content["mcpServers"]

    def test_cursor_converts_env_var_syntax(self, tmp_path):
        """CursorTarget converts ${VAR} to ${env:VAR} syntax in env values."""
        target = CursorTarget()
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_path = cursor_dir / "mcp.json"

        servers = {
            "jira": {
                "command": "uv",
                "args": ["run", "jira-mcp"],
                "env": {
                    "JIRA_URL": "https://issues.example.com",
                    "JIRA_TOKEN": "${JIRA_TOKEN}",
                },
            },
        }

        result = target.generate_mcps(servers, mcp_path, "tools")

        assert result is True
        content = json.loads(mcp_path.read_text())
        server = content["mcpServers"]["jira"]
        # Static values preserved, ${VAR} converted to ${env:VAR}
        assert server["env"]["JIRA_URL"] == "https://issues.example.com"
        assert server["env"]["JIRA_TOKEN"] == "${env:JIRA_TOKEN}"

    def test_cursor_converts_env_var_syntax_in_remote_headers_and_url(self, tmp_path):
        """CursorTarget converts ${VAR} in url/headers for remote HTTP servers."""
        target = CursorTarget()
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_path = cursor_dir / "mcp.json"

        servers = {
            "aap-mcp": {
                "type": "http",
                "url": "https://${AAP_MCP_SERVER}/job_management/mcp",
                "headers": {"Authorization": "Bearer ${AAP_API_TOKEN}"},
            },
        }

        result = target.generate_mcps(servers, mcp_path, "tools")

        assert result is True
        content = json.loads(mcp_path.read_text())
        server = content["mcpServers"]["aap-mcp"]
        assert server["url"] == "https://${env:AAP_MCP_SERVER}/job_management/mcp"
        assert server["headers"]["Authorization"] == "Bearer ${env:AAP_API_TOKEN}"

    def test_cursor_preserves_already_converted_env_var(self, tmp_path):
        """CursorTarget doesn't double-convert an already-${env:VAR} reference."""
        target = CursorTarget()
        cursor_dir = tmp_path / ".cursor"
        cursor_dir.mkdir()
        mcp_path = cursor_dir / "mcp.json"

        servers = {
            "server": {
                "command": "npx",
                "args": [],
                "env": {"TOKEN": "${env:TOKEN}"},
            },
        }

        target.generate_mcps(servers, mcp_path, "tools")

        content = json.loads(mcp_path.read_text())
        assert content["mcpServers"]["server"]["env"]["TOKEN"] == "${env:TOKEN}"

    def test_gemini_generates_settings_json(self, tmp_path):
        """GeminiTarget creates .gemini/settings.json correctly."""
        target = GeminiTarget()
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        mcp_path = gemini_dir / "settings.json"

        servers = {
            "github": {"command": "npx", "args": ["-y", "@mcp/github"]},
        }

        result = target.generate_mcps(servers, mcp_path, "git-tools")

        assert result is True
        assert mcp_path.exists()

        content = json.loads(mcp_path.read_text())
        assert "github" in content["mcpServers"]

    def test_gemini_preserves_existing_settings(self, tmp_path):
        """GeminiTarget doesn't overwrite theme and other settings."""
        target = GeminiTarget()
        gemini_dir = tmp_path / ".gemini"
        gemini_dir.mkdir()
        mcp_path = gemini_dir / "settings.json"

        # Create existing settings
        existing = {"theme": "dark", "codeStyle": "monokai"}
        mcp_path.write_text(json.dumps(existing))

        servers = {
            "github": {"command": "npx", "args": []},
        }

        target.generate_mcps(servers, mcp_path, "git-tools")

        content = json.loads(mcp_path.read_text())
        assert content["theme"] == "dark"
        assert content["codeStyle"] == "monokai"
        assert "github" in content["mcpServers"]

    def test_opencode_generates_mcp_json(self, tmp_path):
        """OpenCodeTarget creates opencode.json at project root in OpenCode format."""
        target = OpenCodeTarget()
        mcp_path = tmp_path / "opencode.json"

        servers = {
            "github": {"command": "npx", "args": ["-y", "@mcp/github"]},
        }

        result = target.generate_mcps(servers, mcp_path, "git-tools")

        assert result is True
        assert mcp_path.exists()

        content = json.loads(mcp_path.read_text())
        # OpenCode uses different format
        assert content["$schema"] == "https://opencode.ai/config.json"
        assert "github" in content["mcp"]
        server = content["mcp"]["github"]
        assert server["type"] == "local"
        assert server["command"] == ["npx", "-y", "@mcp/github"]

    def test_opencode_converts_env_var_syntax(self, tmp_path):
        """OpenCodeTarget converts ${VAR} to {env:VAR} syntax."""
        target = OpenCodeTarget()
        mcp_path = tmp_path / "opencode.json"

        servers = {
            "jira": {
                "command": "uv",
                "args": ["run", "jira-mcp"],
                "env": {
                    "JIRA_URL": "https://issues.example.com",
                    "JIRA_TOKEN": "${JIRA_TOKEN}",
                    "API_KEY": "${API_KEY}",
                },
            },
        }

        result = target.generate_mcps(servers, mcp_path, "tools")

        assert result is True
        content = json.loads(mcp_path.read_text())
        server = content["mcp"]["jira"]
        assert server["type"] == "local"
        assert server["command"] == ["uv", "run", "jira-mcp"]
        # Static values preserved, ${VAR} converted to {env:VAR}
        assert server["environment"]["JIRA_URL"] == "https://issues.example.com"
        assert server["environment"]["JIRA_TOKEN"] == "{env:JIRA_TOKEN}"
        assert server["environment"]["API_KEY"] == "{env:API_KEY}"

    def test_opencode_normalizes_cursor_style_env_var(self, tmp_path):
        """OpenCodeTarget maps ${env:VAR} to {env:VAR}, not {env:env:VAR}."""
        target = OpenCodeTarget()
        mcp_path = tmp_path / "opencode.json"

        servers = {
            "server": {
                "command": "npx",
                "args": [],
                "env": {"TOKEN": "${env:TOKEN}"},
            },
        }

        target.generate_mcps(servers, mcp_path, "tools")

        content = json.loads(mcp_path.read_text())
        assert content["mcp"]["server"]["environment"]["TOKEN"] == "{env:TOKEN}"

    def test_opencode_preserves_already_converted_env_var(self, tmp_path):
        """OpenCodeTarget leaves an already-{env:VAR} reference unchanged."""
        target = OpenCodeTarget()
        mcp_path = tmp_path / "opencode.json"

        servers = {
            "server": {
                "command": "npx",
                "args": [],
                "env": {"TOKEN": "{env:TOKEN}"},
            },
        }

        target.generate_mcps(servers, mcp_path, "tools")

        content = json.loads(mcp_path.read_text())
        assert content["mcp"]["server"]["environment"]["TOKEN"] == "{env:TOKEN}"


# =============================================================================
# VS Code (Copilot) MCP Env Var Conversion Tests
# =============================================================================


class TestVSCodeMCPGeneration:
    """Tests for CopilotVSCodeTarget's env var syntax conversion."""

    def test_vscode_converts_env_var_syntax(self, tmp_path):
        """CopilotVSCodeTarget converts ${VAR} to ${env:VAR} syntax in env values."""
        target = CopilotVSCodeTarget()
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        mcp_path = vscode_dir / "mcp.json"

        servers = {
            "jira": {
                "command": "uv",
                "args": ["run", "jira-mcp"],
                "env": {
                    "JIRA_URL": "https://issues.example.com",
                    "JIRA_TOKEN": "${JIRA_TOKEN}",
                },
            },
        }

        result = target.generate_mcps(servers, mcp_path, "tools")

        assert result is True
        content = json.loads(mcp_path.read_text())
        server = content["servers"]["jira"]
        assert server["type"] == "stdio"
        assert server["env"]["JIRA_URL"] == "https://issues.example.com"
        assert server["env"]["JIRA_TOKEN"] == "${env:JIRA_TOKEN}"

    def test_vscode_converts_env_var_syntax_in_remote_headers_and_url(self, tmp_path):
        """CopilotVSCodeTarget converts ${VAR} in url/headers for remote servers."""
        target = CopilotVSCodeTarget()
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        mcp_path = vscode_dir / "mcp.json"

        servers = {
            "aap-mcp": {
                "type": "http",
                "url": "https://${AAP_MCP_SERVER}/job_management/mcp",
                "headers": {"Authorization": "Bearer ${AAP_API_TOKEN}"},
            },
        }

        result = target.generate_mcps(servers, mcp_path, "tools")

        assert result is True
        content = json.loads(mcp_path.read_text())
        server = content["servers"]["aap-mcp"]
        assert server["type"] == "http"
        assert server["url"] == "https://${env:AAP_MCP_SERVER}/job_management/mcp"
        assert server["headers"]["Authorization"] == "Bearer ${env:AAP_API_TOKEN}"

    def test_vscode_preserves_already_converted_env_var(self, tmp_path):
        """CopilotVSCodeTarget doesn't double-convert an already-${env:VAR} ref."""
        target = CopilotVSCodeTarget()
        vscode_dir = tmp_path / ".vscode"
        vscode_dir.mkdir()
        mcp_path = vscode_dir / "mcp.json"

        servers = {
            "server": {
                "command": "npx",
                "args": [],
                "env": {"TOKEN": "${env:TOKEN}"},
            },
        }

        target.generate_mcps(servers, mcp_path, "tools")

        content = json.loads(mcp_path.read_text())
        assert content["servers"]["server"]["env"]["TOKEN"] == "${env:TOKEN}"


# =============================================================================
# Merge Tests
# =============================================================================


class TestMCPMerging:
    """Tests for merging MCPs from multiple modules."""

    def test_merge_multiple_modules_mcps(self, tmp_path):
        """Two modules with different server names can install MCPs to same file."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        # Install first module
        servers1 = {"server1": {"command": "cmd1", "args": []}}
        target.generate_mcps(servers1, mcp_path, "module-a")

        # Install second module
        servers2 = {"server2": {"command": "cmd2", "args": []}}
        target.generate_mcps(servers2, mcp_path, "module-b")

        content = json.loads(mcp_path.read_text())
        assert "server1" in content["mcpServers"]
        assert "server2" in content["mcpServers"]

    def test_server_name_stored_without_prefix(self, tmp_path):
        """Servers are stored using their original name (no module prefix)."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        servers = {"github": {"command": "npx", "args": []}}
        target.generate_mcps(servers, mcp_path, "git-tools")

        content = json.loads(mcp_path.read_text())
        # Original name "github" is stored as-is
        assert "github" in content["mcpServers"]

    def test_both_modules_mcps_present(self, tmp_path):
        """MCPs from multiple modules with distinct server names are both present."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        # Both modules define servers with distinct names
        servers1 = {"github": {"command": "cmd1", "args": []}}
        servers2 = {"gitlab": {"command": "cmd2", "args": []}}

        target.generate_mcps(servers1, mcp_path, "module-a")
        target.generate_mcps(servers2, mcp_path, "module-b")

        content = json.loads(mcp_path.read_text())
        assert "github" in content["mcpServers"]
        assert "gitlab" in content["mcpServers"]
        assert content["mcpServers"]["github"]["command"] == "cmd1"
        assert content["mcpServers"]["gitlab"]["command"] == "cmd2"


# =============================================================================
# Uninstall Tests
# =============================================================================


class TestMCPUninstall:
    """Tests for uninstalling MCPs."""

    def test_uninstall_removes_module_mcps(self, tmp_path):
        """Uninstall removes only the specified servers by name."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        # Install two modules with distinct server names
        target.generate_mcps({"s1": {"command": "c1", "args": []}}, mcp_path, "mod-a")
        target.generate_mcps({"s2": {"command": "c2", "args": []}}, mcp_path, "mod-b")

        # Remove mod-a's servers by name
        target.remove_mcps(mcp_path, "mod-a", mcp_names=["s1"])

        content = json.loads(mcp_path.read_text())
        assert "s1" not in content["mcpServers"]
        assert "s2" in content["mcpServers"]

    def test_uninstall_preserves_other_module_mcps(self, tmp_path):
        """Uninstalling one module's servers by name doesn't affect another's MCPs."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        # Install two modules
        target.generate_mcps(
            {"s1": {"command": "c1", "args": []}, "s2": {"command": "c2", "args": []}},
            mcp_path,
            "mod-a",
        )
        target.generate_mcps({"s3": {"command": "c3", "args": []}}, mcp_path, "mod-b")

        # Remove mod-a's servers by name
        target.remove_mcps(mcp_path, "mod-a", mcp_names=["s1", "s2"])

        content = json.loads(mcp_path.read_text())
        assert len(content["mcpServers"]) == 1
        assert "s3" in content["mcpServers"]

    def test_uninstall_deletes_empty_mcp_file(self, tmp_path):
        """File is deleted when no servers remain."""
        target = ClaudeCodeTarget()
        mcp_path = tmp_path / ".mcp.json"

        # Install one module
        target.generate_mcps({"s1": {"command": "c1", "args": []}}, mcp_path, "mod-a")
        assert mcp_path.exists()

        # Remove it by name
        target.remove_mcps(mcp_path, "mod-a", mcp_names=["s1"])

        assert not mcp_path.exists()


# =============================================================================
# Installation Model Tests
# =============================================================================


class TestInstallationModel:
    """Tests for Installation dataclass with mcps field."""

    def test_installation_to_dict_includes_mcps(self):
        """Installation.to_dict() includes mcps field."""
        inst = Installation(
            module_name="test",
            assistant="claude-code",
            scope="project",
            project_path="/test",
            mcps=["github", "git"],
        )

        data = inst.to_dict()

        assert "mcps" in data
        assert data["mcps"] == ["github", "git"]

    def test_installation_from_dict_includes_mcps(self):
        """Installation.from_dict() reads mcps field."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
            "mcps": ["github", "git"],
        }

        inst = Installation.from_dict(data)

        assert inst.mcps == ["github", "git"]

    def test_installation_from_dict_defaults_mcps_to_empty(self):
        """Installation.from_dict() defaults mcps to empty list."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
        }

        inst = Installation.from_dict(data)

        assert inst.mcps == []


# =============================================================================
# MCP Validator Tests
# =============================================================================


class TestMCPValidator:
    """Tests for validate_mcps() function."""

    def test_valid_mcps_json(self, tmp_path):
        """validate_mcps() returns no errors for valid mcps.json."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "npx",
                            "args": ["-y", "@mcp/github"],
                            "env": {"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert errors == []

    def test_missing_mcp_servers_key(self, tmp_path):
        """validate_mcps() errors on missing mcpServers key."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(json.dumps({}))

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Missing required 'mcpServers' key" in errors[0]

    def test_invalid_json(self, tmp_path):
        """validate_mcps() errors on invalid JSON."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text("{ invalid json }")

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]

    def test_mcp_servers_not_object(self, tmp_path):
        """validate_mcps() errors when mcpServers is not an object."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(json.dumps({"mcpServers": "not an object"}))

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "'mcpServers' must be an object" in errors[0]

    def test_missing_command_field(self, tmp_path):
        """validate_mcps() errors when server is missing command field."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "args": ["-y", "@mcp/github"],
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Server 'github': missing required 'command' field" in errors[0]

    def test_empty_command_field(self, tmp_path):
        """validate_mcps() errors when command is empty."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Server 'github': 'command' must be a non-empty string" in errors[0]

    def test_invalid_args_type(self, tmp_path):
        """validate_mcps() errors when args is not an array."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "npx",
                            "args": "not an array",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Server 'github': 'args' must be an array" in errors[0]

    def test_invalid_env_type(self, tmp_path):
        """validate_mcps() errors when env is not an object."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "npx",
                            "env": "not an object",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Server 'github': 'env' must be an object" in errors[0]

    def test_invalid_env_value_type(self, tmp_path):
        """validate_mcps() errors when env values are not strings."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "command": "npx",
                            "env": {
                                "TOKEN": 123,  # Should be string
                            },
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) == 1
        assert "Server 'github': env['TOKEN'] must be a string" in errors[0]

    def test_multiple_errors(self, tmp_path):
        """validate_mcps() returns multiple errors for multiple issues."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "server1": {
                            # Missing command
                            "args": "not an array",
                        },
                        "server2": {
                            "command": "",  # Empty command
                            "env": "not an object",
                        },
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) >= 3
        assert any(
            "server1" in err and "missing required 'command' field" in err
            for err in errors
        )
        assert any(
            "server1" in err and "'args' must be an array" in err for err in errors
        )
        assert any(
            "server2" in err and "'command' must be a non-empty string" in err
            for err in errors
        )
        assert any(
            "server2" in err and "'env' must be an object" in err for err in errors
        )

    def test_module_validate_includes_mcps(self, module_with_mcps):
        """Module.validate() includes MCP validation errors."""
        module = Module.from_path(module_with_mcps)
        assert module is not None

        is_valid, errors = module.validate()

        # Should be valid since we have a valid mcps.json
        assert is_valid is True
        assert len(errors) == 0

    def test_module_validate_catches_invalid_mcps(self, tmp_path):
        """Module.validate() catches invalid mcps.json."""
        module_dir = tmp_path / "bad-mcp-module"
        module_dir.mkdir()

        # Create a skill (required for valid module)
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---
# Skill 1
""")

        # Create invalid mcps.json (missing command)
        (module_dir / "mcps.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "github": {
                            "args": ["-y", "@mcp/github"],
                        }
                    }
                }
            )
        )

        module = Module.from_path(module_dir)
        assert module is not None

        is_valid, errors = module.validate()

        assert is_valid is False
        assert any("mcps.json" in err for err in errors)
        assert any("missing required 'command' field" in err for err in errors)

    def test_validate_mcps_accepts_remote_http_server(self, tmp_path):
        """validate_mcps() accepts remote HTTP MCP server (type, url, headers, no command)."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "aap-mcp-job-management": {
                            "type": "http",
                            "url": "https://${AAP_MCP_SERVER}/job_management/mcp",
                            "headers": {
                                "Authorization": "Bearer ${AAP_API_TOKEN}",
                            },
                            "description": "AAP job management MCP server",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert errors == []

    def test_validate_mcps_rejects_remote_server_without_url(self, tmp_path):
        """validate_mcps() rejects remote server missing required url."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps({"mcpServers": {"broken-remote": {"type": "http"}}})
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) >= 1
        assert any("requires 'url' field" in err for err in errors)

    def test_validate_mcps_rejects_remote_server_with_local_fields(self, tmp_path):
        """validate_mcps() rejects remote server that has command, args, or env."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "mixed-remote": {
                            "type": "http",
                            "url": "https://example.com/mcp",
                            "command": "npx",
                            "args": ["-y", "mcp-server"],
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) >= 1
        assert any("must not have 'command', 'args', or 'env'" in err for err in errors)

    def test_validate_mcps_rejects_local_server_with_remote_fields(self, tmp_path):
        """validate_mcps() rejects local server that has url or headers."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "mixed-local": {
                            "command": "npx",
                            "args": ["-y", "@mcp/github"],
                            "url": "https://example.com/mcp",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) >= 1
        assert any("must not have 'url' or 'headers'" in err for err in errors)

    def test_module_validate_accepts_remote_http_server(self, tmp_path):
        """Module.validate() accepts module with remote HTTP MCP server in mcps.json."""
        module_dir = tmp_path / "remote-mcp-module"
        module_dir.mkdir()

        # Create a skill (required for valid module)
        skills_dir = module_dir / "skills"
        skills_dir.mkdir()
        skill_dir = skills_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
description: A test skill
---
# Skill 1
""")

        # Remote HTTP MCP server config (no command)
        (module_dir / "mcps.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "aap-mcp-job-management": {
                            "type": "http",
                            "url": "https://${AAP_MCP_SERVER}/job_management/mcp",
                            "headers": {
                                "Authorization": "Bearer ${AAP_API_TOKEN}",
                            },
                            "description": "AAP job management MCP server",
                        }
                    }
                }
            )
        )

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.mcps == ["aap-mcp-job-management"]

        is_valid, errors = module.validate()

        assert is_valid is True, f"Expected valid, got errors: {errors}"


# =============================================================================
# Remote HTTP MCP Server Behavior Tests
# =============================================================================


class TestRemoteHttpMCPBehavior:
    """Tests for remote HTTP MCP config handling across targets."""

    def test_merge_passes_through_remote_http_config(self, tmp_path):
        """_merge_mcps_into_file passes through remote HTTP config as-is for Claude/Cursor."""
        mcp_file = tmp_path / ".mcp.json"
        remote_config = {
            "aap-mcp": {
                "type": "http",
                "url": "https://${AAP_MCP_SERVER}/job_management/mcp",
                "headers": {
                    "Authorization": "Bearer ${AAP_API_TOKEN}",
                },
                "description": "AAP job management MCP server",
            }
        }

        result = _merge_mcps_into_file(mcp_file, "mymodule", remote_config)

        assert result is True
        assert mcp_file.exists()
        content = json.loads(mcp_file.read_text())
        server = content["mcpServers"]["aap-mcp"]
        assert server["type"] == "http"
        assert "url" in server
        assert "headers" in server
        assert "command" not in server

    def test_merge_passes_through_remote_sse_config(self, tmp_path):
        """_merge_mcps_into_file passes through remote SSE config as-is for Claude/Cursor."""
        mcp_file = tmp_path / ".mcp.json"
        remote_config = {
            "sse-mcp": {
                "type": "sse",
                "url": "https://example.com/sse",
                "headers": {"Authorization": "Bearer token"},
            }
        }

        result = _merge_mcps_into_file(mcp_file, "mymodule", remote_config)

        assert result is True
        content = json.loads(mcp_file.read_text())
        server = content["mcpServers"]["sse-mcp"]
        assert server["type"] == "sse"
        assert server["url"] == "https://example.com/sse"

    def test_opencode_transform_converts_http_to_remote(self, tmp_path):
        """OpenCode converts Lola's http type to OpenCode's remote type."""
        from lola.targets.opencode import _merge_mcps_into_opencode_file

        mcp_path = tmp_path / "opencode.json"
        remote_config = {
            "aap-mcp": {
                "type": "http",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer token"},
            }
        }

        _merge_mcps_into_opencode_file(mcp_path, "mymodule", remote_config)

        content = json.loads(mcp_path.read_text())
        server = content["mcp"]["aap-mcp"]
        assert server["type"] == "remote"
        assert server["url"] == "https://example.com/mcp"
        assert server["headers"] == {"Authorization": "Bearer token"}
        assert "command" not in server

    def test_opencode_transform_converts_sse_to_remote(self, tmp_path):
        """OpenCode converts Lola's sse type to OpenCode's remote type."""
        from lola.targets.opencode import _merge_mcps_into_opencode_file

        mcp_path = tmp_path / "opencode.json"
        remote_config = {
            "sse-server": {
                "type": "sse",
                "url": "https://example.com/sse",
                "headers": {"X-API-Key": "secret"},
            }
        }

        _merge_mcps_into_opencode_file(mcp_path, "mymodule", remote_config)

        content = json.loads(mcp_path.read_text())
        server = content["mcp"]["sse-server"]
        assert server["type"] == "remote"
        assert server["url"] == "https://example.com/sse"
        assert server["headers"] == {"X-API-Key": "secret"}

    def test_validate_mcps_rejects_remote_type(self, tmp_path):
        """validate_mcps() rejects type 'remote'; Lola standard uses http/sse only."""
        mcps_file = tmp_path / "mcps.json"
        mcps_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "opencode-style": {
                            "type": "remote",
                            "url": "https://example.com/mcp",
                        }
                    }
                }
            )
        )

        errors = fm.validate_mcps(mcps_file)

        assert len(errors) >= 1
        assert any(
            "type 'remote' is not supported" in err and "use 'http' or 'sse'" in err
            for err in errors
        )
