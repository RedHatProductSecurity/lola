"""Tests for the config module."""

from pathlib import Path

import pytest

from lola.config import (
    LOLA_HOME,
    MODULES_DIR,
    INSTALLED_FILE,
    SKILL_FILE,
    ASSISTANTS,
    SOURCE_TYPES,
    get_assistant_command_path,
    get_assistant_skill_path,
)


class TestConfigConstants:
    """Tests for configuration constants."""

    def test_lola_home_is_path(self):
        """LOLA_HOME is a Path object."""
        assert isinstance(LOLA_HOME, Path)

    def test_modules_dir_under_lola_home(self):
        """MODULES_DIR is under LOLA_HOME."""
        assert MODULES_DIR.parent == LOLA_HOME

    def test_installed_file_under_lola_home(self):
        """INSTALLED_FILE is under LOLA_HOME."""
        assert INSTALLED_FILE.parent == LOLA_HOME

    def test_skill_file_name(self):
        """SKILL_FILE has correct name."""
        assert SKILL_FILE == "SKILL.md"

    def test_source_types(self):
        """SOURCE_TYPES contains expected types."""
        assert "git" in SOURCE_TYPES
        assert "zip" in SOURCE_TYPES
        assert "tar" in SOURCE_TYPES
        assert "folder" in SOURCE_TYPES


class TestAssistantsConfig:
    """Tests for ASSISTANTS configuration."""

    def test_claude_code_exists(self):
        """claude-code assistant is configured."""
        assert "claude-code" in ASSISTANTS

    def test_gemini_cli_exists(self):
        """gemini-cli assistant is configured."""
        assert "gemini-cli" in ASSISTANTS

    def test_cursor_exists(self):
        """cursor assistant is configured."""
        assert "cursor" in ASSISTANTS

    def test_claude_code_paths(self):
        """claude-code has required path configurations."""
        config = ASSISTANTS["claude-code"]
        assert "user" in config
        assert "project" in config
        assert "commands_user" in config
        assert "commands_project" in config
        assert isinstance(config["user"], Path)
        assert callable(config["project"])

    def test_gemini_cli_paths(self):
        """gemini-cli has required path configurations."""
        config = ASSISTANTS["gemini-cli"]
        assert "user" in config
        assert "project" in config
        assert "commands_user" in config
        assert "commands_project" in config

    def test_cursor_paths(self):
        """cursor has required path configurations."""
        config = ASSISTANTS["cursor"]
        assert "user" in config
        assert "project" in config
        assert "commands_user" in config
        assert "commands_project" in config


class TestGetAssistantCommandPath:
    """Tests for get_assistant_command_path()."""

    def test_claude_code_user(self):
        """Get claude-code user command path."""
        path = get_assistant_command_path("claude-code", "user")
        assert isinstance(path, Path)
        assert "commands" in str(path)

    def test_claude_code_project(self, tmp_path):
        """Get claude-code project command path."""
        path = get_assistant_command_path("claude-code", "project", str(tmp_path))
        assert isinstance(path, Path)
        assert str(tmp_path) in str(path)
        assert "commands" in str(path)

    def test_gemini_cli_user(self):
        """Get gemini-cli user command path."""
        path = get_assistant_command_path("gemini-cli", "user")
        assert isinstance(path, Path)
        assert "commands" in str(path)

    def test_gemini_cli_project(self, tmp_path):
        """Get gemini-cli project command path."""
        path = get_assistant_command_path("gemini-cli", "project", str(tmp_path))
        assert isinstance(path, Path)

    def test_cursor_user(self):
        """Get cursor user command path."""
        path = get_assistant_command_path("cursor", "user")
        assert isinstance(path, Path)
        assert "commands" in str(path)

    def test_cursor_project(self, tmp_path):
        """Get cursor project command path."""
        path = get_assistant_command_path("cursor", "project", str(tmp_path))
        assert isinstance(path, Path)

    def test_unknown_assistant(self):
        """Raise error for unknown assistant."""
        with pytest.raises(ValueError, match="Unknown assistant"):
            get_assistant_command_path("unknown", "user")

    def test_project_without_path(self):
        """Raise error for project scope without path."""
        with pytest.raises(ValueError, match="Project path required"):
            get_assistant_command_path("claude-code", "project")


class TestGetAssistantSkillPath:
    """Tests for get_assistant_skill_path()."""

    def test_claude_code_user(self):
        """Get claude-code user skill path."""
        path = get_assistant_skill_path("claude-code", "user")
        assert isinstance(path, Path)
        assert "skills" in str(path)

    def test_claude_code_project(self, tmp_path):
        """Get claude-code project skill path."""
        path = get_assistant_skill_path("claude-code", "project", str(tmp_path))
        assert isinstance(path, Path)
        assert str(tmp_path) in str(path)
        assert "skills" in str(path)

    def test_gemini_cli_user(self):
        """Get gemini-cli user skill path (GEMINI.md file)."""
        path = get_assistant_skill_path("gemini-cli", "user")
        assert isinstance(path, Path)
        assert "GEMINI.md" in str(path)

    def test_gemini_cli_project(self, tmp_path):
        """Get gemini-cli project skill path."""
        path = get_assistant_skill_path("gemini-cli", "project", str(tmp_path))
        assert isinstance(path, Path)
        assert "GEMINI.md" in str(path)

    def test_cursor_user(self):
        """Get cursor user skill path."""
        path = get_assistant_skill_path("cursor", "user")
        assert isinstance(path, Path)
        assert "rules" in str(path)

    def test_cursor_project(self, tmp_path):
        """Get cursor project skill path."""
        path = get_assistant_skill_path("cursor", "project", str(tmp_path))
        assert isinstance(path, Path)
        assert "rules" in str(path)

    def test_unknown_assistant(self):
        """Raise error for unknown assistant."""
        with pytest.raises(ValueError, match="Unknown assistant"):
            get_assistant_skill_path("unknown", "user")

    def test_project_without_path(self):
        """Raise error for project scope without path."""
        with pytest.raises(ValueError, match="Project path required"):
            get_assistant_skill_path("claude-code", "project")
