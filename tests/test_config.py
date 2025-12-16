"""Tests for the config module."""

from pathlib import Path

import pytest

from lola.config import LOLA_HOME, MODULES_DIR, INSTALLED_FILE, SKILL_FILE
from lola.parsers import SOURCE_TYPES
from lola.targets import TARGETS, get_target


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


class TestTargetsConfig:
    """Tests for TARGETS configuration."""

    def test_claude_code_exists(self):
        """claude-code target is configured."""
        assert "claude-code" in TARGETS

    def test_gemini_cli_exists(self):
        """gemini-cli target is configured."""
        assert "gemini-cli" in TARGETS

    def test_cursor_exists(self):
        """cursor target is configured."""
        assert "cursor" in TARGETS

    def test_opencode_exists(self):
        """opencode target is configured."""
        assert "opencode" in TARGETS

    def test_claude_code_has_required_methods(self):
        """claude-code target has required methods."""
        target = get_target("claude-code")
        assert hasattr(target, "get_skill_path")
        assert hasattr(target, "get_command_path")
        assert hasattr(target, "get_agent_path")
        assert hasattr(target, "generate_skill")
        assert hasattr(target, "generate_command")
        assert hasattr(target, "generate_agent")

    def test_gemini_cli_no_agent_support(self):
        """gemini-cli target does not support agents."""
        target = get_target("gemini-cli")
        assert target.supports_agents is False


class TestGetCommandPath:
    """Tests for target.get_command_path()."""

    def test_claude_code_project(self, tmp_path):
        """Get claude-code project command path."""
        target = get_target("claude-code")
        path = target.get_command_path(str(tmp_path))
        assert isinstance(path, Path)
        assert str(tmp_path) in str(path)
        assert "commands" in str(path)

    def test_gemini_cli_project(self, tmp_path):
        """Get gemini-cli project command path."""
        target = get_target("gemini-cli")
        path = target.get_command_path(str(tmp_path))
        assert isinstance(path, Path)

    def test_cursor_project(self, tmp_path):
        """Get cursor project command path."""
        target = get_target("cursor")
        path = target.get_command_path(str(tmp_path))
        assert isinstance(path, Path)

    def test_unknown_assistant(self):
        """Raise error for unknown assistant."""
        with pytest.raises(ValueError, match="Unknown assistant"):
            get_target("unknown")


class TestGetSkillPath:
    """Tests for target.get_skill_path()."""

    def test_claude_code_project(self, tmp_path):
        """Get claude-code project skill path."""
        target = get_target("claude-code")
        path = target.get_skill_path(str(tmp_path))
        assert isinstance(path, Path)
        assert str(tmp_path) in str(path)
        assert "skills" in str(path)

    def test_gemini_cli_project(self, tmp_path):
        """Get gemini-cli project skill path."""
        target = get_target("gemini-cli")
        path = target.get_skill_path(str(tmp_path))
        assert isinstance(path, Path)
        assert "GEMINI.md" in str(path)

    def test_cursor_project(self, tmp_path):
        """Get cursor project skill path."""
        target = get_target("cursor")
        path = target.get_skill_path(str(tmp_path))
        assert isinstance(path, Path)
        assert "rules" in str(path)

    def test_unknown_assistant(self):
        """Raise error for unknown assistant."""
        with pytest.raises(ValueError, match="Unknown assistant"):
            get_target("unknown")
