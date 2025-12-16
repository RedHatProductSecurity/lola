"""Tests for concrete target implementations in targets.py.

This module tests:
- ClaudeCodeTarget: skill directory copying, command passthrough, agent frontmatter
- CursorTarget: MDC format conversion, path rewriting, skill removal
- GeminiTarget: managed section generation, TOML command format
- OpenCodeTarget: managed section generation, agent frontmatter
- Helper functions: path rewriting, skill description extraction
"""

from pathlib import Path

import pytest

from lola.exceptions import UnknownAssistantError
from lola.targets import (
    ClaudeCodeTarget,
    CursorTarget,
    GeminiTarget,
    OpenCodeTarget,
    _convert_to_gemini_args,
    _get_skill_description,
    _rewrite_relative_paths,
    get_target,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def skill_source(tmp_path: Path) -> Path:
    """Create a skill source directory with SKILL.md and supporting files."""
    skill_dir = tmp_path / "source" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)

    # Main skill file
    (skill_dir / "SKILL.md").write_text("""---
description: Test skill for unit testing
---

# Test Skill

This is a test skill with some content.

## Usage

Read the helper file at ./scripts/helper.py for more info.
""")

    # Supporting files
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "helper.py").write_text("# Helper script\nprint('hello')")
    (skill_dir / "notes.md").write_text("# Notes\nSome notes here.")

    return skill_dir


@pytest.fixture
def command_source(tmp_path: Path) -> Path:
    """Create a command source file."""
    cmd_dir = tmp_path / "source" / "commands"
    cmd_dir.mkdir(parents=True)
    cmd_file = cmd_dir / "test-cmd.md"
    cmd_file.write_text("""---
description: Test command description
argument-hint: "[type]"
---

Execute a task with $ARGUMENTS.

Use $1 for the first argument and $2 for the second.
""")
    return cmd_file


@pytest.fixture
def agent_source(tmp_path: Path) -> Path:
    """Create an agent source file."""
    agent_dir = tmp_path / "source" / "agents"
    agent_dir.mkdir(parents=True)
    agent_file = agent_dir / "test-agent.md"
    agent_file.write_text("""---
description: Test agent for troubleshooting
---

# Test Agent

You are a helpful assistant.

## Workflow

1. Understand the problem
2. Propose a solution
""")
    return agent_file


@pytest.fixture
def dest_path(tmp_path: Path) -> Path:
    """Create a destination directory for generated files."""
    dest = tmp_path / "dest"
    dest.mkdir()
    return dest


# =============================================================================
# ClaudeCodeTarget Tests
# =============================================================================


class TestClaudeCodeTarget:
    """Tests for ClaudeCodeTarget implementation."""

    def test_name_and_attributes(self):
        """Verify target name and capability attributes."""
        target = ClaudeCodeTarget()
        assert target.name == "claude-code"
        assert target.supports_agents is True
        assert target.uses_managed_section is False

    def test_get_skill_path(self, tmp_path: Path):
        """Skill path should be .claude/skills."""
        target = ClaudeCodeTarget()
        path = target.get_skill_path(str(tmp_path))
        assert path == tmp_path / ".claude" / "skills"

    def test_get_command_path(self, tmp_path: Path):
        """Command path should be .claude/commands."""
        target = ClaudeCodeTarget()
        path = target.get_command_path(str(tmp_path))
        assert path == tmp_path / ".claude" / "commands"

    def test_get_agent_path(self, tmp_path: Path):
        """Agent path should be .claude/agents."""
        target = ClaudeCodeTarget()
        path = target.get_agent_path(str(tmp_path))
        assert path == tmp_path / ".claude" / "agents"

    def test_generate_skill_copies_skill_md(
        self, skill_source: Path, dest_path: Path
    ):
        """generate_skill should copy SKILL.md to destination."""
        target = ClaudeCodeTarget()
        result = target.generate_skill(skill_source, dest_path, "mymod-test-skill")

        assert result is True
        skill_dest = dest_path / "mymod-test-skill"
        assert skill_dest.exists()
        assert (skill_dest / "SKILL.md").exists()

        content = (skill_dest / "SKILL.md").read_text()
        assert "Test skill for unit testing" in content

    def test_generate_skill_copies_supporting_files(
        self, skill_source: Path, dest_path: Path
    ):
        """generate_skill should copy supporting files and directories."""
        target = ClaudeCodeTarget()
        target.generate_skill(skill_source, dest_path, "mymod-test-skill")

        skill_dest = dest_path / "mymod-test-skill"
        assert (skill_dest / "scripts" / "helper.py").exists()
        assert (skill_dest / "notes.md").exists()

    def test_generate_skill_returns_false_for_missing_source(
        self, dest_path: Path, tmp_path: Path
    ):
        """generate_skill should return False when source doesn't exist."""
        target = ClaudeCodeTarget()
        missing = tmp_path / "nonexistent"
        result = target.generate_skill(missing, dest_path, "missing-skill")
        assert result is False

    def test_generate_skill_overwrites_existing_directories(
        self, skill_source: Path, dest_path: Path
    ):
        """generate_skill should overwrite existing supporting directories."""
        target = ClaudeCodeTarget()
        skill_dest = dest_path / "mymod-test-skill"

        # First generation
        target.generate_skill(skill_source, dest_path, "mymod-test-skill")

        # Modify source
        (skill_source / "scripts" / "new_file.py").write_text("new content")

        # Second generation should overwrite
        target.generate_skill(skill_source, dest_path, "mymod-test-skill")

        assert (skill_dest / "scripts" / "new_file.py").exists()

    def test_generate_command_creates_file(
        self, command_source: Path, dest_path: Path
    ):
        """generate_command should create properly named markdown file."""
        target = ClaudeCodeTarget()
        result = target.generate_command(
            command_source, dest_path, "test-cmd", "mymod"
        )

        assert result is True
        cmd_file = dest_path / "mymod-test-cmd.md"
        assert cmd_file.exists()

        content = cmd_file.read_text()
        assert "Test command description" in content
        assert "$ARGUMENTS" in content

    def test_generate_command_returns_false_for_missing_source(
        self, dest_path: Path, tmp_path: Path
    ):
        """generate_command should return False when source doesn't exist."""
        target = ClaudeCodeTarget()
        missing = tmp_path / "nonexistent.md"
        result = target.generate_command(missing, dest_path, "missing", "mymod")
        assert result is False

    def test_generate_agent_adds_model_inherit(
        self, agent_source: Path, dest_path: Path
    ):
        """generate_agent should add model: inherit to frontmatter."""
        target = ClaudeCodeTarget()
        result = target.generate_agent(
            agent_source, dest_path, "test-agent", "mymod"
        )

        assert result is True
        agent_file = dest_path / "mymod-test-agent.md"
        assert agent_file.exists()

        content = agent_file.read_text()
        assert "model: inherit" in content
        assert "description: Test agent for troubleshooting" in content
        assert "# Test Agent" in content

    def test_generate_agent_preserves_existing_frontmatter(
        self, tmp_path: Path, dest_path: Path
    ):
        """generate_agent should preserve existing frontmatter fields."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        agent_file = agent_dir / "custom.md"
        agent_file.write_text("""---
description: Custom agent
custom_field: custom_value
tags:
  - tag1
  - tag2
---

Agent body content.
""")

        target = ClaudeCodeTarget()
        target.generate_agent(agent_file, dest_path, "custom", "mymod")

        result_file = dest_path / "mymod-custom.md"
        content = result_file.read_text()

        assert "model: inherit" in content
        assert "custom_field: custom_value" in content
        assert "tag1" in content

    def test_remove_skill_deletes_directory(self, dest_path: Path):
        """remove_skill should delete the skill directory."""
        target = ClaudeCodeTarget()
        skill_dir = dest_path / "mymod-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("content")

        result = target.remove_skill(dest_path, "mymod-skill")

        assert result is True
        assert not skill_dir.exists()

    def test_remove_skill_returns_false_when_not_exists(self, dest_path: Path):
        """remove_skill should return False when directory doesn't exist."""
        target = ClaudeCodeTarget()
        result = target.remove_skill(dest_path, "nonexistent")
        assert result is False

    def test_get_command_filename(self):
        """Command filename should be module-cmd.md."""
        target = ClaudeCodeTarget()
        filename = target.get_command_filename("mymod", "do-thing")
        assert filename == "mymod-do-thing.md"

    def test_get_agent_filename(self):
        """Agent filename should be module-agent.md."""
        target = ClaudeCodeTarget()
        filename = target.get_agent_filename("mymod", "helper")
        assert filename == "mymod-helper.md"


# =============================================================================
# CursorTarget Tests
# =============================================================================


class TestCursorTarget:
    """Tests for CursorTarget implementation."""

    def test_name_and_attributes(self):
        """Verify target name and capability attributes."""
        target = CursorTarget()
        assert target.name == "cursor"
        assert target.supports_agents is False
        assert target.uses_managed_section is False

    def test_get_skill_path(self, tmp_path: Path):
        """Skill path should be .cursor/rules."""
        target = CursorTarget()
        path = target.get_skill_path(str(tmp_path))
        assert path == tmp_path / ".cursor" / "rules"

    def test_get_command_path(self, tmp_path: Path):
        """Command path should be .cursor/commands."""
        target = CursorTarget()
        path = target.get_command_path(str(tmp_path))
        assert path == tmp_path / ".cursor" / "commands"

    def test_get_agent_path_returns_none(self, tmp_path: Path):
        """Agent path should be None (agents not supported)."""
        target = CursorTarget()
        path = target.get_agent_path(str(tmp_path))
        assert path is None

    def test_generate_skill_creates_mdc_file(
        self, skill_source: Path, dest_path: Path, tmp_path: Path
    ):
        """generate_skill should create .mdc file with proper format."""
        target = CursorTarget()
        result = target.generate_skill(
            skill_source, dest_path, "mymod-test-skill", str(tmp_path)
        )

        assert result is True
        mdc_file = dest_path / "mymod-test-skill.mdc"
        assert mdc_file.exists()

        content = mdc_file.read_text()
        # Check MDC frontmatter structure
        assert "---" in content
        assert "description: Test skill for unit testing" in content
        assert "globs:" in content
        assert "alwaysApply: false" in content

    def test_generate_skill_mdc_format_structure(
        self, skill_source: Path, dest_path: Path, tmp_path: Path
    ):
        """MDC file should have correct structure: frontmatter + body."""
        target = CursorTarget()
        target.generate_skill(
            skill_source, dest_path, "mymod-test-skill", str(tmp_path)
        )

        mdc_file = dest_path / "mymod-test-skill.mdc"
        content = mdc_file.read_text()
        lines = content.split("\n")

        # Should start with ---
        assert lines[0] == "---"
        # Should have description, globs, alwaysApply
        assert any("description:" in line for line in lines)
        assert any("globs:" in line for line in lines)
        assert any("alwaysApply:" in line for line in lines)
        # Body should contain skill content
        assert "# Test Skill" in content

    def test_generate_skill_rewrites_relative_paths(
        self, skill_source: Path, dest_path: Path, tmp_path: Path
    ):
        """generate_skill should rewrite relative paths to point to source."""
        target = CursorTarget()
        target.generate_skill(
            skill_source, dest_path, "mymod-test-skill", str(tmp_path)
        )

        mdc_file = dest_path / "mymod-test-skill.mdc"
        content = mdc_file.read_text()

        # Original: ./scripts/helper.py should be rewritten
        # The path should contain the relative source path
        assert "source/skills/test-skill" in content or "scripts/helper.py" in content

    def test_generate_skill_returns_false_for_missing_skill_md(
        self, tmp_path: Path, dest_path: Path
    ):
        """generate_skill should return False when SKILL.md is missing."""
        empty_dir = tmp_path / "empty_skill"
        empty_dir.mkdir()

        target = CursorTarget()
        result = target.generate_skill(empty_dir, dest_path, "empty", str(tmp_path))
        assert result is False

    def test_generate_command_creates_file(
        self, command_source: Path, dest_path: Path
    ):
        """generate_command should create properly named markdown file."""
        target = CursorTarget()
        result = target.generate_command(
            command_source, dest_path, "test-cmd", "mymod"
        )

        assert result is True
        cmd_file = dest_path / "mymod-test-cmd.md"
        assert cmd_file.exists()

    def test_generate_agent_returns_false(
        self, agent_source: Path, dest_path: Path
    ):
        """generate_agent should return False (not supported)."""
        target = CursorTarget()
        result = target.generate_agent(
            agent_source, dest_path, "test-agent", "mymod"
        )
        assert result is False

    def test_remove_skill_deletes_mdc_file(self, dest_path: Path):
        """remove_skill should delete the .mdc file."""
        target = CursorTarget()
        mdc_file = dest_path / "mymod-skill.mdc"
        mdc_file.write_text("content")

        result = target.remove_skill(dest_path, "mymod-skill")

        assert result is True
        assert not mdc_file.exists()

    def test_remove_skill_returns_false_when_not_exists(self, dest_path: Path):
        """remove_skill should return False when file doesn't exist."""
        target = CursorTarget()
        result = target.remove_skill(dest_path, "nonexistent")
        assert result is False


# =============================================================================
# GeminiTarget Tests
# =============================================================================


class TestGeminiTarget:
    """Tests for GeminiTarget (ManagedSectionTarget) implementation."""

    def test_name_and_attributes(self):
        """Verify target name and capability attributes."""
        target = GeminiTarget()
        assert target.name == "gemini-cli"
        assert target.supports_agents is False
        assert target.uses_managed_section is True
        assert target.MANAGED_FILE == "GEMINI.md"

    def test_get_skill_path(self, tmp_path: Path):
        """Skill path should be GEMINI.md file."""
        target = GeminiTarget()
        path = target.get_skill_path(str(tmp_path))
        assert path == tmp_path / "GEMINI.md"

    def test_get_command_path(self, tmp_path: Path):
        """Command path should be .gemini/commands."""
        target = GeminiTarget()
        path = target.get_command_path(str(tmp_path))
        assert path == tmp_path / ".gemini" / "commands"

    def test_generate_skill_raises_not_implemented(
        self, skill_source: Path, dest_path: Path
    ):
        """generate_skill should raise NotImplementedError."""
        target = GeminiTarget()
        with pytest.raises(NotImplementedError):
            target.generate_skill(skill_source, dest_path, "skill", str(dest_path))

    def test_generate_skills_batch_creates_file(
        self, tmp_path: Path, skill_source: Path
    ):
        """generate_skills_batch should create GEMINI.md with skill listings."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        skills = [
            ("test-skill", "Test skill description", skill_source),
        ]

        result = target.generate_skills_batch(
            dest_file, "mymod", skills, str(tmp_path)
        )

        assert result is True
        assert dest_file.exists()

        content = dest_file.read_text()
        assert target.START_MARKER in content
        assert target.END_MARKER in content
        assert "### mymod" in content
        assert "#### test-skill" in content
        assert "Test skill description" in content

    def test_generate_skills_batch_updates_existing_file(
        self, tmp_path: Path, skill_source: Path
    ):
        """generate_skills_batch should update existing file content."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        # Create existing content
        dest_file.write_text("""# My Project

Some existing content here.
""")

        skills = [("skill1", "Description 1", skill_source)]
        target.generate_skills_batch(dest_file, "mymod", skills, str(tmp_path))

        content = dest_file.read_text()
        assert "# My Project" in content
        assert "Some existing content here" in content
        assert target.START_MARKER in content
        assert "### mymod" in content

    def test_generate_skills_batch_replaces_module_section(
        self, tmp_path: Path, skill_source: Path
    ):
        """generate_skills_batch should replace existing module section."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        # First batch
        skills1 = [("skill1", "Old description", skill_source)]
        target.generate_skills_batch(dest_file, "mymod", skills1, str(tmp_path))

        # Second batch with different skills
        skills2 = [("skill2", "New description", skill_source)]
        target.generate_skills_batch(dest_file, "mymod", skills2, str(tmp_path))

        content = dest_file.read_text()
        # Should have new skill, not old
        assert "skill2" in content
        assert "New description" in content
        # Old skill should be replaced
        assert content.count("### mymod") == 1

    def test_generate_skills_batch_preserves_other_modules(
        self, tmp_path: Path, skill_source: Path
    ):
        """generate_skills_batch should preserve other modules' sections."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        # Add first module
        skills1 = [("skill1", "Module 1 skill", skill_source)]
        target.generate_skills_batch(dest_file, "module1", skills1, str(tmp_path))

        # Add second module
        skills2 = [("skill2", "Module 2 skill", skill_source)]
        target.generate_skills_batch(dest_file, "module2", skills2, str(tmp_path))

        content = dest_file.read_text()
        assert "### module1" in content
        assert "### module2" in content
        assert "Module 1 skill" in content
        assert "Module 2 skill" in content

    def test_generate_command_creates_toml_file(
        self, command_source: Path, dest_path: Path
    ):
        """generate_command should create TOML file with proper format."""
        target = GeminiTarget()
        result = target.generate_command(
            command_source, dest_path, "test-cmd", "mymod"
        )

        assert result is True
        toml_file = dest_path / "mymod-test-cmd.toml"
        assert toml_file.exists()

        content = toml_file.read_text()
        assert 'description = "Test command description"' in content
        assert 'prompt = """' in content
        assert "{{args}}" in content  # $ARGUMENTS should be converted

    def test_generate_command_escapes_special_chars_in_description(
        self, tmp_path: Path, dest_path: Path
    ):
        """generate_command should escape special characters in description."""
        cmd_dir = tmp_path / "commands"
        cmd_dir.mkdir()
        cmd_file = cmd_dir / "special.md"
        cmd_file.write_text("""---
description: Test with "quotes" and \\backslash
---

Command body.
""")

        target = GeminiTarget()
        target.generate_command(cmd_file, dest_path, "special", "mymod")

        toml_file = dest_path / "mymod-special.toml"
        content = toml_file.read_text()
        assert '\\"quotes\\"' in content
        assert "\\\\backslash" in content

    def test_get_command_filename_uses_toml_extension(self):
        """Command filename should use .toml extension."""
        target = GeminiTarget()
        filename = target.get_command_filename("mymod", "do-thing")
        assert filename == "mymod-do-thing.toml"

    def test_remove_skill_removes_module_section(
        self, tmp_path: Path, skill_source: Path
    ):
        """remove_skill should remove module section from managed file."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        # Add two modules
        target.generate_skills_batch(
            dest_file, "module1", [("s1", "desc1", skill_source)], str(tmp_path)
        )
        target.generate_skills_batch(
            dest_file, "module2", [("s2", "desc2", skill_source)], str(tmp_path)
        )

        # Remove module1
        result = target.remove_skill(dest_file, "module1")

        assert result is True
        content = dest_file.read_text()
        assert "### module1" not in content
        assert "### module2" in content

    def test_remove_skill_returns_true_when_file_not_exists(self, tmp_path: Path):
        """remove_skill should return True when file doesn't exist."""
        target = GeminiTarget()
        dest_file = tmp_path / "nonexistent.md"
        result = target.remove_skill(dest_file, "mymod")
        assert result is True


# =============================================================================
# OpenCodeTarget Tests
# =============================================================================


class TestOpenCodeTarget:
    """Tests for OpenCodeTarget (ManagedSectionTarget) implementation."""

    def test_name_and_attributes(self):
        """Verify target name and capability attributes."""
        target = OpenCodeTarget()
        assert target.name == "opencode"
        assert target.supports_agents is True
        assert target.uses_managed_section is True
        assert target.MANAGED_FILE == "AGENTS.md"

    def test_get_skill_path(self, tmp_path: Path):
        """Skill path should be AGENTS.md file."""
        target = OpenCodeTarget()
        path = target.get_skill_path(str(tmp_path))
        assert path == tmp_path / "AGENTS.md"

    def test_get_command_path(self, tmp_path: Path):
        """Command path should be .opencode/commands."""
        target = OpenCodeTarget()
        path = target.get_command_path(str(tmp_path))
        assert path == tmp_path / ".opencode" / "commands"

    def test_get_agent_path(self, tmp_path: Path):
        """Agent path should be .opencode/agent."""
        target = OpenCodeTarget()
        path = target.get_agent_path(str(tmp_path))
        assert path == tmp_path / ".opencode" / "agent"

    def test_generate_skills_batch_creates_agents_md(
        self, tmp_path: Path, skill_source: Path
    ):
        """generate_skills_batch should create AGENTS.md."""
        target = OpenCodeTarget()
        dest_file = tmp_path / "AGENTS.md"

        skills = [("test-skill", "Test skill", skill_source)]
        result = target.generate_skills_batch(
            dest_file, "mymod", skills, str(tmp_path)
        )

        assert result is True
        assert dest_file.exists()
        content = dest_file.read_text()
        assert "### mymod" in content

    def test_generate_command_creates_markdown_file(
        self, command_source: Path, dest_path: Path
    ):
        """generate_command should create markdown file (passthrough)."""
        target = OpenCodeTarget()
        result = target.generate_command(
            command_source, dest_path, "test-cmd", "mymod"
        )

        assert result is True
        cmd_file = dest_path / "mymod-test-cmd.md"
        assert cmd_file.exists()

        # Should be passthrough (not converted to TOML)
        content = cmd_file.read_text()
        assert "---" in content
        assert "description:" in content

    def test_generate_agent_adds_mode_subagent(
        self, agent_source: Path, dest_path: Path
    ):
        """generate_agent should add mode: subagent to frontmatter."""
        target = OpenCodeTarget()
        result = target.generate_agent(
            agent_source, dest_path, "test-agent", "mymod"
        )

        assert result is True
        agent_file = dest_path / "mymod-test-agent.md"
        assert agent_file.exists()

        content = agent_file.read_text()
        assert "mode: subagent" in content
        assert "description: Test agent for troubleshooting" in content


# =============================================================================
# ManagedSectionTarget Base Class Tests
# =============================================================================


class TestManagedSectionTarget:
    """Tests for ManagedSectionTarget base class functionality."""

    def test_start_and_end_markers(self):
        """Verify default markers."""
        target = GeminiTarget()  # Using concrete subclass
        assert target.START_MARKER == "<!-- lola:skills:start -->"
        assert target.END_MARKER == "<!-- lola:skills:end -->"

    def test_header_content(self):
        """Verify header contains usage instructions."""
        target = GeminiTarget()
        assert "## Lola Skills" in target.HEADER
        assert "read_file" in target.HEADER

    def test_generate_skills_batch_includes_relative_path(
        self, tmp_path: Path, skill_source: Path
    ):
        """Skills should include relative path to SKILL.md."""
        target = GeminiTarget()
        dest_file = tmp_path / "GEMINI.md"

        skills = [("test-skill", "Description", skill_source)]
        target.generate_skills_batch(dest_file, "mymod", skills, str(tmp_path))

        content = dest_file.read_text()
        assert "SKILL.md" in content
        assert "**Instructions:**" in content


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestRewriteRelativePaths:
    """Tests for _rewrite_relative_paths helper."""

    def test_rewrites_dot_slash_paths(self):
        """Should rewrite ./path to assets/path."""
        content = "Read ./scripts/helper.py for details."
        result = _rewrite_relative_paths(content, "assets/skill")
        assert "assets/skill/scripts/helper.py" in result

    def test_rewrites_dot_dot_slash_paths(self):
        """Should rewrite ../path to assets/../path."""
        content = "See ../shared/utils.py"
        result = _rewrite_relative_paths(content, "assets/skill")
        assert "assets/skill/../shared/utils.py" in result

    def test_handles_quoted_paths(self):
        """Should rewrite paths in quotes."""
        content = 'Read "./data/config.json" now.'
        result = _rewrite_relative_paths(content, "assets")
        assert "assets/data/config.json" in result

    def test_handles_backtick_paths(self):
        """Should rewrite paths in backticks."""
        content = "Run `./scripts/run.sh` to start."
        result = _rewrite_relative_paths(content, "assets")
        assert "assets/scripts/run.sh" in result

    def test_preserves_absolute_paths(self):
        """Should not modify absolute paths."""
        content = "Config at /etc/myapp/config.yml"
        result = _rewrite_relative_paths(content, "assets")
        assert "/etc/myapp/config.yml" in result

    def test_removes_double_slashes(self):
        """Should clean up double slashes."""
        content = "./path//to//file"
        result = _rewrite_relative_paths(content, "assets")
        # Should not have // (except in protocols)
        assert "//" not in result or "://" in result


class TestGetSkillDescription:
    """Tests for _get_skill_description helper."""

    def test_extracts_description_from_skill_md(self, skill_source: Path):
        """Should extract description from SKILL.md frontmatter."""
        description = _get_skill_description(skill_source)
        assert description == "Test skill for unit testing"

    def test_returns_empty_for_missing_skill_md(self, tmp_path: Path):
        """Should return empty string when SKILL.md doesn't exist."""
        description = _get_skill_description(tmp_path)
        assert description == ""

    def test_returns_empty_for_missing_description(self, tmp_path: Path):
        """Should return empty string when description field is missing."""
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
title: No description
---

Content here.
""")
        description = _get_skill_description(skill_dir)
        assert description == ""


class TestConvertToGeminiArgs:
    """Tests for _convert_to_gemini_args helper."""

    def test_converts_arguments_placeholder(self):
        """Should convert $ARGUMENTS to {{args}}."""
        content = "Execute $ARGUMENTS now."
        result = _convert_to_gemini_args(content)
        assert "{{args}}" in result
        assert "$ARGUMENTS" not in result

    def test_adds_args_header_for_positional_args(self):
        """Should add Arguments header when $1, $2, etc. are present."""
        content = "First arg: $1, second: $2"
        result = _convert_to_gemini_args(content)
        assert "Arguments: {{args}}" in result

    def test_no_args_header_without_positional_args(self):
        """Should not add header when no positional args present."""
        content = "No positional arguments here."
        result = _convert_to_gemini_args(content)
        assert "Arguments:" not in result


# =============================================================================
# get_target Function Tests
# =============================================================================


class TestGetTarget:
    """Tests for get_target function."""

    def test_returns_correct_target_types(self):
        """Should return correct target instances."""
        assert isinstance(get_target("claude-code"), ClaudeCodeTarget)
        assert isinstance(get_target("cursor"), CursorTarget)
        assert isinstance(get_target("gemini-cli"), GeminiTarget)
        assert isinstance(get_target("opencode"), OpenCodeTarget)

    def test_raises_for_unknown_assistant(self):
        """Should raise UnknownAssistantError for unknown assistant."""
        with pytest.raises(UnknownAssistantError, match="Unknown assistant"):
            get_target("unknown-assistant")

    def test_error_message_lists_supported_assistants(self):
        """Error message should list supported assistants."""
        with pytest.raises(UnknownAssistantError) as exc_info:
            get_target("bad")
        assert "claude-code" in str(exc_info.value)
        assert "cursor" in str(exc_info.value)
        assert "gemini-cli" in str(exc_info.value)
        assert "opencode" in str(exc_info.value)


# =============================================================================
# Integration-Style Tests
# =============================================================================


class TestTargetIntegration:
    """Integration-style tests verifying complete workflows."""

    def test_full_skill_installation_workflow_claude(
        self, skill_source: Path, tmp_path: Path
    ):
        """Test complete skill installation for Claude Code."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        target = ClaudeCodeTarget()
        skill_dest = target.get_skill_path(str(project_path))
        skill_dest.mkdir(parents=True)

        # Generate skill
        result = target.generate_skill(
            skill_source, skill_dest, "mymod-test-skill", str(project_path)
        )

        assert result is True
        skill_dir = skill_dest / "mymod-test-skill"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "scripts" / "helper.py").exists()

        # Remove skill
        result = target.remove_skill(skill_dest, "mymod-test-skill")
        assert result is True
        assert not skill_dir.exists()

    def test_full_skill_installation_workflow_cursor(
        self, skill_source: Path, tmp_path: Path
    ):
        """Test complete skill installation for Cursor."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        target = CursorTarget()
        skill_dest = target.get_skill_path(str(project_path))
        skill_dest.mkdir(parents=True)

        # Generate skill
        result = target.generate_skill(
            skill_source, skill_dest, "mymod-test-skill", str(project_path)
        )

        assert result is True
        mdc_file = skill_dest / "mymod-test-skill.mdc"
        assert mdc_file.exists()

        content = mdc_file.read_text()
        assert "alwaysApply: false" in content

        # Remove skill
        result = target.remove_skill(skill_dest, "mymod-test-skill")
        assert result is True
        assert not mdc_file.exists()

    def test_full_skill_installation_workflow_gemini(
        self, skill_source: Path, tmp_path: Path
    ):
        """Test complete skill installation for Gemini CLI."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        target = GeminiTarget()
        skill_dest = target.get_skill_path(str(project_path))

        # Generate skills batch
        skills = [
            ("skill1", "First skill", skill_source),
            ("skill2", "Second skill", skill_source),
        ]
        result = target.generate_skills_batch(
            skill_dest, "mymod", skills, str(project_path)
        )

        assert result is True
        assert skill_dest.exists()
        content = skill_dest.read_text()
        assert "#### skill1" in content
        assert "#### skill2" in content

        # Remove module
        result = target.remove_skill(skill_dest, "mymod")
        assert result is True
        content = skill_dest.read_text()
        assert "### mymod" not in content

    def test_command_generation_all_targets(
        self, command_source: Path, tmp_path: Path
    ):
        """Test command generation for all targets."""
        targets = [
            (ClaudeCodeTarget(), "mymod-cmd.md"),
            (CursorTarget(), "mymod-cmd.md"),
            (GeminiTarget(), "mymod-cmd.toml"),
            (OpenCodeTarget(), "mymod-cmd.md"),
        ]

        for target, expected_filename in targets:
            dest = tmp_path / f"dest_{target.name}"
            dest.mkdir()

            result = target.generate_command(command_source, dest, "cmd", "mymod")
            assert result is True, f"Failed for {target.name}"

            expected_file = dest / expected_filename
            assert expected_file.exists(), f"File not created for {target.name}"

    def test_agent_generation_supported_targets(
        self, agent_source: Path, tmp_path: Path
    ):
        """Test agent generation for targets that support agents."""
        # Claude Code - should add model: inherit
        claude_dest = tmp_path / "claude"
        claude_dest.mkdir()
        claude_target = ClaudeCodeTarget()
        result = claude_target.generate_agent(
            agent_source, claude_dest, "agent", "mymod"
        )
        assert result is True
        content = (claude_dest / "mymod-agent.md").read_text()
        assert "model: inherit" in content

        # OpenCode - should add mode: subagent
        opencode_dest = tmp_path / "opencode"
        opencode_dest.mkdir()
        opencode_target = OpenCodeTarget()
        result = opencode_target.generate_agent(
            agent_source, opencode_dest, "agent", "mymod"
        )
        assert result is True
        content = (opencode_dest / "mymod-agent.md").read_text()
        assert "mode: subagent" in content

        # Cursor - should return False (not supported)
        cursor_dest = tmp_path / "cursor"
        cursor_dest.mkdir()
        cursor_target = CursorTarget()
        result = cursor_target.generate_agent(
            agent_source, cursor_dest, "agent", "mymod"
        )
        assert result is False

