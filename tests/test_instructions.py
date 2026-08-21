"""Tests for the module instructions feature."""

import shutil
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from lola.models import Installation, InstallationRegistry, Module
from lola.targets import (
    ClaudeCodeTarget,
    CursorTarget,
    GeminiTarget,
    OpenCodeTarget,
)
from lola.targets.base import _resolve_source_content


# =============================================================================
# Module Model Tests
# =============================================================================


class TestModuleHasInstructions:
    """Tests for Module.has_instructions detection."""

    def test_module_from_path_with_instructions(self, tmp_path):
        """Module with AGENTS.md has has_instructions=True."""
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()

        # Create a skill (required for valid module)
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")

        # Create AGENTS.md
        (module_dir / "AGENTS.md").write_text("# Test Module\n\nInstructions here.")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.has_instructions is True

    def test_module_from_path_without_instructions(self, tmp_path):
        """Module without AGENTS.md has has_instructions=False."""
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()

        # Create a skill (required for valid module)
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.has_instructions is False

    def test_module_from_path_with_empty_instructions(self, tmp_path):
        """Module with empty AGENTS.md has has_instructions=False."""
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()

        # Create a skill (required for valid module)
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")

        # Create empty AGENTS.md
        (module_dir / "AGENTS.md").write_text("")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.has_instructions is False

    def test_module_with_only_instructions_is_valid(self, tmp_path):
        """Module with only AGENTS.md (no skills/commands/agents) is valid."""
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()

        # Create only AGENTS.md
        (module_dir / "AGENTS.md").write_text("# Test Module\n\nInstructions here.")

        module = Module.from_path(module_dir)
        assert module is not None
        assert module.has_instructions is True
        assert module.skills == []
        assert module.commands == []
        assert module.agents == []


# =============================================================================
# Installation Model Tests
# =============================================================================


class TestInstallationHasInstructions:
    """Tests for Installation.has_instructions serialization."""

    def test_to_dict_includes_has_instructions(self):
        """Installation.to_dict() includes has_instructions."""
        inst = Installation(
            module_name="test",
            assistant="claude-code",
            scope="project",
            project_path="/test",
            has_instructions=True,
        )
        data = inst.to_dict()
        assert "has_instructions" in data
        assert data["has_instructions"] is True

    def test_from_dict_reads_has_instructions(self):
        """Installation.from_dict() reads has_instructions."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
            "has_instructions": True,
        }
        inst = Installation.from_dict(data)
        assert inst.has_instructions is True

    def test_from_dict_defaults_has_instructions_to_false(self):
        """Installation.from_dict() defaults has_instructions to False."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
        }
        inst = Installation.from_dict(data)
        assert inst.has_instructions is False

    def test_to_dict_includes_append_context(self):
        """Installation.to_dict() includes append_context when set."""
        inst = Installation(
            module_name="test",
            assistant="claude-code",
            scope="project",
            project_path="/test",
            append_context=["module/AGENTS.md"],
        )
        data = inst.to_dict()
        assert data["append_context"] == ["module/AGENTS.md"]

    def test_to_dict_includes_multiple_append_context(self):
        """Installation.to_dict() includes multiple append_context values."""
        inst = Installation(
            module_name="test",
            assistant="claude-code",
            scope="project",
            project_path="/test",
            append_context=["module/AGENTS.md", "/abs/path/GUIDE.md"],
        )
        data = inst.to_dict()
        assert data["append_context"] == ["module/AGENTS.md", "/abs/path/GUIDE.md"]

    def test_to_dict_omits_append_context_when_none(self):
        """Installation.to_dict() omits append_context when not set."""
        inst = Installation(
            module_name="test",
            assistant="claude-code",
            scope="project",
            project_path="/test",
        )
        data = inst.to_dict()
        assert "append_context" not in data

    def test_from_dict_reads_append_context(self):
        """Installation.from_dict() reads append_context as list."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
            "append_context": ["module/AGENTS.md"],
        }
        inst = Installation.from_dict(data)
        assert inst.append_context == ["module/AGENTS.md"]

    def test_from_dict_reads_multiple_append_context(self):
        """Installation.from_dict() reads multiple append_context values."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
            "append_context": ["module/AGENTS.md", "/abs/path/GUIDE.md"],
        }
        inst = Installation.from_dict(data)
        assert inst.append_context == ["module/AGENTS.md", "/abs/path/GUIDE.md"]

    def test_from_dict_backward_compat_string(self):
        """Installation.from_dict() converts old single-string append_context to list."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
            "append_context": "module/AGENTS.md",
        }
        inst = Installation.from_dict(data)
        assert inst.append_context == ["module/AGENTS.md"]

    def test_from_dict_defaults_append_context_to_none(self):
        """Installation.from_dict() defaults append_context to None."""
        data = {
            "module": "test",
            "assistant": "claude-code",
            "scope": "project",
        }
        inst = Installation.from_dict(data)
        assert inst.append_context is None


# =============================================================================
# _resolve_source_content Tests
# =============================================================================


class TestResolveSourceContent:
    """Tests for _resolve_source_content helper."""

    def test_resolves_string(self):
        """String source returns stripped content."""
        assert _resolve_source_content("  hello  ") == "hello"

    def test_resolves_path(self, tmp_path):
        """Path source reads and strips file content."""
        f = tmp_path / "test.md"
        f.write_text("  file content  ")
        assert _resolve_source_content(f) == "file content"

    def test_missing_path_returns_none(self, tmp_path):
        """Non-existent path returns None."""
        assert _resolve_source_content(tmp_path / "missing.md") is None

    def test_empty_string_returns_empty(self):
        """Empty string returns empty string."""
        assert _resolve_source_content("   ") == ""

    def test_resolves_list(self):
        """List source joins items with newlines, strips, returns None if empty."""
        result = _resolve_source_content(["line1", "  line2  ", "line3"])
        assert result == "line1\n  line2  \nline3"

    def test_resolves_empty_list_returns_none(self):
        """Empty list returns None."""
        assert _resolve_source_content([]) is None

    def test_resolves_list_with_empty_items(self):
        """List of empty strings returns empty string (not None — joined is empty)."""
        assert _resolve_source_content(["", "  ", ""]) == ""


# =============================================================================
# Dedup regression test
# =============================================================================


class TestAppendContextDedup:
    """Regression test: duplicate append_context entries must be deduplicated."""

    def test_dedup_identical_context_paths(self, tmp_path):
        """Two identical --append-context paths produce one reference in CLAUDE.md."""
        from lola.cli.install import update_cmd
        from lola.models import Installation, InstallationRegistry
        from unittest.mock import patch, MagicMock

        # Setup
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        module_dir = modules_dir / "dedup-test"
        context_dir = module_dir / "module"
        context_dir.mkdir(parents=True)
        (context_dir / "AGENTS.md").write_text("# Module Instructions")
        (module_dir / "skills" / "skill1").mkdir(parents=True)
        (module_dir / "skills" / "skill1" / "SKILL.md").write_text(
            "---\ndescription: Test\n---\nContent"
        )

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "dedup-test")

        installed_file = project_dir / "installed.yml"
        registry = InstallationRegistry(installed_file)
        # Same context path passed TWICE
        inst = Installation(
            module_name="dedup-test",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            has_instructions=True,
            append_context=[
                str(context_dir / "AGENTS.md"),
                str(context_dir / "AGENTS.md"),
            ],
        )
        registry.add(inst)

        runner = CliRunner()
        real_target = MagicMock(spec=ClaudeCodeTarget)
        real_target.uses_managed_section = False
        real_target.supports_agents = True
        real_target.get_instructions_path = ClaudeCodeTarget().get_instructions_path
        real_target.generate_instructions = ClaudeCodeTarget().generate_instructions
        real_target.remove_instructions = ClaudeCodeTarget().remove_instructions
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=real_target),
        ):
            result = runner.invoke(update_cmd, ["dedup-test"])

        assert result.exit_code == 0
        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text()
        # The reference should appear exactly ONCE, not twice
        count = content.count("Read the module context from")
        assert count == 1, f"Expected 1 reference, found {count}: {content}"


# =============================================================================
# =============================================================================


class TestClaudeCodeInstructions:
    """Tests for Claude Code target instructions generation."""

    def test_get_instructions_path(self, tmp_path):
        """get_instructions_path returns CLAUDE.md."""
        target = ClaudeCodeTarget()
        path = target.get_instructions_path(str(tmp_path))
        assert path == tmp_path / "CLAUDE.md"

    def test_generate_instructions_creates_file(self, tmp_path):
        """generate_instructions creates CLAUDE.md with managed section."""
        target = ClaudeCodeTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Test Module\n\nThese are instructions.")

        dest = tmp_path / "project" / "CLAUDE.md"

        result = target.generate_instructions(source, dest, "test-module")

        assert result is True
        assert dest.exists()
        content = dest.read_text()
        assert "<!-- lola:instructions:start -->" in content
        assert "<!-- lola:instructions:end -->" in content
        assert "<!-- lola:module:test-module:start -->" in content
        assert "<!-- lola:module:test-module:end -->" in content
        assert "# Test Module" in content

    def test_generate_instructions_preserves_existing_content(self, tmp_path):
        """generate_instructions preserves existing content outside managed section."""
        target = ClaudeCodeTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# New Module\n\nNew instructions.")

        dest = tmp_path / "project" / "CLAUDE.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("# My Project\n\nExisting content here.")

        result = target.generate_instructions(source, dest, "new-module")

        assert result is True
        content = dest.read_text()
        assert "# My Project" in content
        assert "Existing content here." in content
        assert "# New Module" in content

    def test_generate_instructions_multiple_modules(self, tmp_path):
        """generate_instructions handles multiple modules sorted alphabetically."""
        target = ClaudeCodeTarget()
        dest = tmp_path / "project" / "CLAUDE.md"

        # Add first module (zeta)
        source1 = tmp_path / "source1" / "AGENTS.md"
        source1.parent.mkdir()
        source1.write_text("# Zeta Module")
        target.generate_instructions(source1, dest, "zeta-module")

        # Add second module (alpha)
        source2 = tmp_path / "source2" / "AGENTS.md"
        source2.parent.mkdir()
        source2.write_text("# Alpha Module")
        target.generate_instructions(source2, dest, "alpha-module")

        content = dest.read_text()
        # Alpha should come before Zeta (sorted)
        alpha_pos = content.find("alpha-module")
        zeta_pos = content.find("zeta-module")
        assert alpha_pos < zeta_pos

    def test_remove_instructions(self, tmp_path):
        """remove_instructions removes module and cleans up empty section."""
        target = ClaudeCodeTarget()
        dest = tmp_path / "CLAUDE.md"

        # First add instructions
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Test Module")
        target.generate_instructions(source, dest, "test-module")

        # Then remove
        result = target.remove_instructions(dest, "test-module")

        assert result is True
        content = dest.read_text()
        assert "test-module" not in content
        # Managed section markers should be removed when empty
        assert "<!-- lola:instructions:start -->" not in content
        assert "<!-- lola:instructions:end -->" not in content

    def test_remove_instructions_keeps_other_modules(self, tmp_path):
        """remove_instructions keeps section when other modules remain."""
        target = ClaudeCodeTarget()
        dest = tmp_path / "CLAUDE.md"

        # Add two modules
        source1 = tmp_path / "source1" / "AGENTS.md"
        source1.parent.mkdir()
        source1.write_text("# Module One")
        target.generate_instructions(source1, dest, "module-one")

        source2 = tmp_path / "source2" / "AGENTS.md"
        source2.parent.mkdir()
        source2.write_text("# Module Two")
        target.generate_instructions(source2, dest, "module-two")

        # Remove one module
        result = target.remove_instructions(dest, "module-one")

        assert result is True
        content = dest.read_text()
        assert "module-one" not in content
        assert "module-two" in content
        # Managed section markers should still exist
        assert "<!-- lola:instructions:start -->" in content

    def test_generate_instructions_empty_source_returns_false(self, tmp_path):
        """generate_instructions returns False for empty source."""
        target = ClaudeCodeTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("")

        dest = tmp_path / "CLAUDE.md"
        result = target.generate_instructions(source, dest, "test-module")

        assert result is False

    def test_generate_instructions_missing_source_returns_false(self, tmp_path):
        """generate_instructions returns False for missing source."""
        target = ClaudeCodeTarget()
        source = tmp_path / "nonexistent" / "AGENTS.md"
        dest = tmp_path / "CLAUDE.md"

        result = target.generate_instructions(source, dest, "test-module")

        assert result is False


# =============================================================================
# Cursor Target Tests
# =============================================================================


class TestCursorInstructions:
    """Tests for Cursor target instructions generation."""

    def test_get_instructions_path(self, tmp_path):
        """get_instructions_path returns .cursor/rules directory."""
        target = CursorTarget()
        path = target.get_instructions_path(str(tmp_path))
        assert path == tmp_path / ".cursor" / "rules"

    def test_generate_instructions_creates_mdc_file(self, tmp_path):
        """generate_instructions creates .mdc file with alwaysApply: true."""
        target = CursorTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Test Module\n\nInstructions here.")

        dest = tmp_path / "project" / ".cursor" / "rules"

        result = target.generate_instructions(source, dest, "test-module")

        assert result is True
        mdc_file = dest / "test-module-instructions.mdc"
        assert mdc_file.exists()
        content = mdc_file.read_text()
        assert "alwaysApply: true" in content
        assert "description: test-module module instructions" in content
        assert "# Test Module" in content

    def test_remove_instructions_deletes_mdc_file(self, tmp_path):
        """remove_instructions deletes the .mdc file."""
        target = CursorTarget()

        # Create the file first
        dest = tmp_path / ".cursor" / "rules"
        dest.mkdir(parents=True)
        mdc_file = dest / "test-module-instructions.mdc"
        mdc_file.write_text("content")

        result = target.remove_instructions(dest, "test-module")

        assert result is True
        assert not mdc_file.exists()

    def test_remove_instructions_nonexistent_returns_false(self, tmp_path):
        """remove_instructions returns False when file doesn't exist."""
        target = CursorTarget()
        dest = tmp_path / ".cursor" / "rules"
        dest.mkdir(parents=True)

        result = target.remove_instructions(dest, "test-module")

        assert result is False


# =============================================================================
# Gemini Target Tests
# =============================================================================


class TestGeminiInstructions:
    """Tests for Gemini target instructions generation."""

    def test_get_instructions_path(self, tmp_path):
        """get_instructions_path returns GEMINI.md."""
        target = GeminiTarget()
        path = target.get_instructions_path(str(tmp_path))
        assert path == tmp_path / "GEMINI.md"

    def test_generate_instructions_creates_managed_section(self, tmp_path):
        """generate_instructions creates managed section in GEMINI.md."""
        target = GeminiTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Test Module\n\nInstructions.")

        dest = tmp_path / "GEMINI.md"

        result = target.generate_instructions(source, dest, "test-module")

        assert result is True
        content = dest.read_text()
        assert "<!-- lola:instructions:start -->" in content
        assert "<!-- lola:module:test-module:start -->" in content
        assert "# Test Module" in content


# =============================================================================
# OpenCode Target Tests
# =============================================================================


class TestOpenCodeInstructions:
    """Tests for OpenCode target instructions generation."""

    def test_get_instructions_path(self, tmp_path):
        """get_instructions_path returns AGENTS.md."""
        target = OpenCodeTarget()
        path = target.get_instructions_path(str(tmp_path))
        assert path == tmp_path / "AGENTS.md"

    def test_generate_instructions_creates_managed_section(self, tmp_path):
        """generate_instructions creates managed section in AGENTS.md."""
        target = OpenCodeTarget()
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Test Module\n\nInstructions.")

        dest = tmp_path / "AGENTS.md"

        result = target.generate_instructions(source, dest, "test-module")

        assert result is True
        content = dest.read_text()
        assert "<!-- lola:instructions:start -->" in content
        assert "<!-- lola:module:test-module:start -->" in content


# =============================================================================
# CLI Integration Tests
# =============================================================================


class TestInstallWithInstructions:
    """Tests for install command with instructions."""

    def test_install_with_instructions(self, tmp_path):
        """Install command includes instructions in summary."""
        from lola.cli.install import install_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module with instructions
        module_dir = modules_dir / "test-module"
        module_dir.mkdir()
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")
        (module_dir / "AGENTS.md").write_text("# Test Module\n\nInstructions.")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.config.INSTALLED_FILE", installed_file),
        ):
            result = runner.invoke(
                install_cmd, ["test-module", "-a", "claude-code", str(project_dir)]
            )

        assert result.exit_code == 0
        assert "instructions" in result.output


class TestUninstallWithInstructions:
    """Tests for uninstall command with instructions."""

    def test_uninstall_removes_instructions(self, tmp_path):
        """Uninstall command removes instructions files."""
        from lola.cli.install import uninstall_cmd

        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installation that has instructions
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(tmp_path / "project"),
            skills=["test-module-skill1"],
            has_instructions=True,
        )
        registry.add(inst)

        # Create project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        skill_dest = project_dir / ".claude" / "skills" / "test-module-skill1"
        skill_dest.mkdir(parents=True)
        (skill_dest / "SKILL.md").write_text("content")

        # Create instructions file
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text(
            "<!-- lola:instructions:start -->\n"
            "<!-- lola:module:test-module:start -->\n"
            "# Test Module\n"
            "<!-- lola:module:test-module:end -->\n"
            "<!-- lola:instructions:end -->\n"
        )

        # Create mock target
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.get_skill_path.return_value = project_dir / ".claude" / "skills"
        mock_target.get_command_path.return_value = project_dir / ".claude" / "commands"
        mock_target.get_agent_path.return_value = project_dir / ".claude" / "agents"
        mock_target.get_instructions_path.return_value = claude_md
        mock_target.remove_skill.return_value = True
        mock_target.remove_instructions.return_value = True
        mock_target.get_plugin_layout.return_value = None

        runner = CliRunner()
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(uninstall_cmd, ["test-module", "-f"])

        assert result.exit_code == 0
        mock_target.remove_instructions.assert_called_once()


class TestUpdateWithInstructions:
    """Tests for update command with instructions."""

    def test_update_regenerates_instructions(self, tmp_path):
        """Update command regenerates instructions."""
        from lola.cli.install import update_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module with instructions
        module_dir = modules_dir / "test-module"
        module_dir.mkdir()
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")
        (module_dir / "AGENTS.md").write_text("# Updated Instructions")

        # Create project dir
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            skills=["test-module-skill1"],
            has_instructions=True,
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = project_dir / ".claude" / "skills"
        skill_dest.mkdir(parents=True)
        command_dest = project_dir / ".claude" / "commands"
        command_dest.mkdir()
        agent_dest = project_dir / ".claude" / "agents"
        agent_dest.mkdir()

        # Create local module copy
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "test-module")

        # Create mock target
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.supports_agents = True
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_agent_path.return_value = agent_dest
        mock_target.get_instructions_path.return_value = project_dir / "CLAUDE.md"
        mock_target.remove_skill.return_value = True
        mock_target.generate_skill.return_value = True
        mock_target.generate_command.return_value = True
        mock_target.generate_agent.return_value = True
        mock_target.generate_instructions.return_value = True

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(update_cmd, ["test-module"])

        assert result.exit_code == 0
        assert "instructions" in result.output
        mock_target.generate_instructions.assert_called()

    def test_update_installs_new_instructions(self, tmp_path):
        """Update installs instructions if module now has AGENTS.md."""
        from lola.cli.install import update_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module that now has instructions
        module_dir = modules_dir / "test-module"
        module_dir.mkdir()
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")
        (module_dir / "AGENTS.md").write_text("# New Instructions")

        # Create project dir
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create registry with installation that didn't have instructions
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            skills=["test-module-skill1"],
            has_instructions=False,  # Originally no instructions
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = project_dir / ".claude" / "skills"
        skill_dest.mkdir(parents=True)
        command_dest = project_dir / ".claude" / "commands"
        command_dest.mkdir()

        # Create local module copy
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "test-module")

        # Create mock target
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.supports_agents = True
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_agent_path.return_value = None
        mock_target.get_instructions_path.return_value = project_dir / "CLAUDE.md"
        mock_target.remove_skill.return_value = True
        mock_target.generate_skill.return_value = True
        mock_target.generate_instructions.return_value = True

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(update_cmd, ["test-module"])

        assert result.exit_code == 0
        mock_target.generate_instructions.assert_called()

        # Verify registry was updated
        updated = registry.find("test-module")[0]
        assert updated.has_instructions is True

    def test_update_preserves_append_context(self, tmp_path):
        """Update respects append_context from installation record."""
        from lola.cli.install import update_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module with context file
        module_dir = modules_dir / "test-module"
        context_dir = module_dir / "module"
        context_dir.mkdir(parents=True)
        (context_dir / "AGENTS.md").write_text("# Context\nRead context/foo.md")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create registry with append_context set
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            has_instructions=True,
            append_context=["module/AGENTS.md"],
        )
        registry.add(inst)

        # Create local module copy
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "test-module")

        # Use real ClaudeCodeTarget for instructions
        real_target = ClaudeCodeTarget()
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.supports_agents = True
        mock_target.get_skill_path.return_value = project_dir / ".claude" / "skills"
        mock_target.get_command_path.return_value = project_dir / ".claude" / "commands"
        mock_target.get_agent_path.return_value = None
        mock_target.get_mcp_path.return_value = None
        mock_target.get_instructions_path = real_target.get_instructions_path
        mock_target.generate_instructions = real_target.generate_instructions
        mock_target.remove_instructions = real_target.remove_instructions

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(update_cmd, ["test-module"])

        assert result.exit_code == 0

        # Verify CLAUDE.md has a reference, not verbatim content
        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text()
        assert "Read the module context from" in content
        assert "module/AGENTS.md" in content
        assert "Read context/foo.md" not in content

    def test_update_preserves_multiple_append_context(self, tmp_path):
        """Update respects multiple append_context values from installation record."""
        from lola.cli.install import update_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module with context file
        module_dir = modules_dir / "test-module"
        context_dir = module_dir / "module"
        context_dir.mkdir(parents=True)
        (context_dir / "AGENTS.md").write_text("# Context")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # External context file (absolute path test)
        ext_file = project_dir / "external-AGENTS.md"
        ext_file.write_text("# External Context")

        # Create registry with multiple append_context values
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            has_instructions=True,
            append_context=["module/AGENTS.md", str(ext_file)],
        )
        registry.add(inst)

        # Create local module copy
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "test-module")

        # Use real ClaudeCodeTarget for instructions
        real_target = ClaudeCodeTarget()
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.supports_agents = True
        mock_target.get_skill_path.return_value = project_dir / ".claude" / "skills"
        mock_target.get_command_path.return_value = project_dir / ".claude" / "commands"
        mock_target.get_agent_path.return_value = None
        mock_target.get_mcp_path.return_value = None
        mock_target.get_instructions_path = real_target.get_instructions_path
        mock_target.generate_instructions = real_target.generate_instructions
        mock_target.remove_instructions = real_target.remove_instructions

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(update_cmd, ["test-module"])

        assert result.exit_code == 0

        # Verify CLAUDE.md has references for both contexts
        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text()
        assert "Read the module context from" in content
        # Both contexts should be present — with fix #1, absolute paths
        # inside project_root resolve to relative paths
        assert "module/AGENTS.md" in content
        assert "external-AGENTS.md" in content


# =============================================================================
# ManagedInstructionsTarget Mixin Tests
# =============================================================================


class TestManagedInstructionsTarget:
    """Tests for the ManagedInstructionsTarget mixin."""

    def test_extract_module_blocks(self, tmp_path):
        """_extract_module_blocks correctly parses module sections."""
        target = ClaudeCodeTarget()  # Uses ManagedInstructionsTarget

        content = """
<!-- lola:module:alpha:start -->
Alpha content
<!-- lola:module:alpha:end -->

<!-- lola:module:beta:start -->
Beta content
<!-- lola:module:beta:end -->
"""
        blocks = target._extract_module_blocks(content)

        assert "alpha" in blocks
        assert "beta" in blocks
        assert "Alpha content" in blocks["alpha"]
        assert "Beta content" in blocks["beta"]

    def test_get_module_markers(self):
        """_get_module_markers returns correct markers."""
        target = ClaudeCodeTarget()

        start, end = target._get_module_markers("test-module")

        assert start == "<!-- lola:module:test-module:start -->"
        assert end == "<!-- lola:module:test-module:end -->"

    def test_update_existing_module_instructions(self, tmp_path):
        """Updating existing module replaces its instructions."""
        target = ClaudeCodeTarget()
        dest = tmp_path / "CLAUDE.md"

        # Add initial instructions
        source1 = tmp_path / "v1" / "AGENTS.md"
        source1.parent.mkdir()
        source1.write_text("# Version 1")
        target.generate_instructions(source1, dest, "test-module")

        # Update with new instructions
        source2 = tmp_path / "v2" / "AGENTS.md"
        source2.parent.mkdir()
        source2.write_text("# Version 2")
        target.generate_instructions(source2, dest, "test-module")

        content = dest.read_text()
        assert "# Version 2" in content
        assert "# Version 1" not in content
        # Should only have one module section
        assert content.count("lola:module:test-module:start") == 1


# =============================================================================
# Regression Tests
# =============================================================================


class TestInstructionsRegressions:
    """Regression tests for instructions-related bugs."""

    def test_remove_last_module_cleans_up_markers(self, tmp_path):
        """
        Regression: When the last module is removed, the entire managed section
        should be removed, not just the module content.

        Previously, empty markers were left behind:
        <!-- lola:instructions:start --><!-- lola:instructions:end -->
        """
        target = ClaudeCodeTarget()
        dest = tmp_path / "CLAUDE.md"

        # Add some existing content before instructions
        dest.write_text("# My Project\n\nSome content here.\n\n")

        # Add instructions
        source = tmp_path / "source" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Module Instructions")
        target.generate_instructions(source, dest, "test-module")

        # Verify instructions were added
        content = dest.read_text()
        assert "<!-- lola:instructions:start -->" in content
        assert "test-module" in content

        # Remove the module
        target.remove_instructions(dest, "test-module")

        # The file should not have any lola markers at all
        content = dest.read_text()
        assert "<!-- lola:instructions:start -->" not in content
        assert "<!-- lola:instructions:end -->" not in content
        assert "lola:module" not in content
        # Original content should be preserved
        assert "# My Project" in content

    def test_update_removes_instructions_with_stale_registry(self, tmp_path):
        """
        Regression: When AGENTS.md is deleted and user reinstalls, the installation
        record has has_instructions=False. Update should still remove any existing
        instructions from the target file.

        Previously, instructions were only removed if has_instructions=True in the
        installation record, leaving orphaned instructions in CLAUDE.md.
        """
        from lola.cli.install import update_cmd

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create module WITHOUT instructions (AGENTS.md deleted)
        module_dir = modules_dir / "test-module"
        module_dir.mkdir()
        skills_dir = module_dir / "skills" / "skill1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")
        # Note: No AGENTS.md file

        # Create project dir
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create registry with stale installation (has_instructions=False due to reinstall)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="test-module",
            assistant="claude-code",
            scope="project",
            project_path=str(project_dir),
            skills=["skill1"],
            has_instructions=False,  # Stale: was reinstalled after AGENTS.md deleted
        )
        registry.add(inst)

        # Create paths
        skill_dest = project_dir / ".claude" / "skills"
        skill_dest.mkdir(parents=True)
        command_dest = project_dir / ".claude" / "commands"
        command_dest.mkdir()

        # Create CLAUDE.md with orphaned instructions (from before reinstall)
        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text(
            "# My Project\n\n"
            "<!-- lola:instructions:start -->\n"
            "<!-- lola:module:test-module:start -->\n"
            "# Old Instructions\n"
            "<!-- lola:module:test-module:end -->\n"
            "<!-- lola:instructions:end -->\n"
        )

        # Create local module copy (without AGENTS.md)
        local_modules = project_dir / ".lola" / "modules"
        local_modules.mkdir(parents=True)
        shutil.copytree(module_dir, local_modules / "test-module")

        # Create mock target that uses real remove_instructions
        real_target = ClaudeCodeTarget()
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.supports_agents = True
        mock_target.get_skill_path.return_value = skill_dest
        mock_target.get_command_path.return_value = command_dest
        mock_target.get_agent_path.return_value = None
        mock_target.get_mcp_path.return_value = None
        mock_target.get_instructions_path.return_value = claude_md
        mock_target.remove_skill.return_value = True
        mock_target.generate_skill.return_value = True
        # Use real remove_instructions to test the actual fix
        mock_target.remove_instructions = real_target.remove_instructions

        runner = CliRunner()
        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch(
                "lola.cli.install.get_local_modules_path", return_value=local_modules
            ),
            patch("lola.cli.install.get_target", return_value=mock_target),
        ):
            result = runner.invoke(update_cmd, ["test-module"])

        assert result.exit_code == 0

        # The orphaned instructions should be removed
        content = claude_md.read_text()
        assert "<!-- lola:instructions:start -->" not in content
        assert "test-module" not in content
        assert "Old Instructions" not in content
        # Original content should be preserved
        assert "# My Project" in content


# =============================================================================
# --append-context Tests
# =============================================================================


class TestAppendContext:
    """Tests for --append-context flag."""

    def test_append_context_creates_reference(self, tmp_path):
        """--append-context inserts a reference instead of verbatim content."""
        from lola.targets.install import _install_instructions

        target = ClaudeCodeTarget()
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()
        context_dir = module_dir / "module"
        context_dir.mkdir()
        (context_dir / "AGENTS.md").write_text("# Instructions\nRead context/foo.md")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        local_module = project_dir / ".lola" / "modules" / "test-module"
        local_module.mkdir(parents=True)
        shutil.copytree(module_dir, local_module, dirs_exist_ok=True)

        module = Module.from_path(module_dir)
        assert module is not None

        result = _install_instructions(
            target,
            module,
            local_module,
            str(project_dir),
            append_context=["module/AGENTS.md"],
        )

        assert result is True
        claude_md = project_dir / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "Read the module context from" in content
        assert ".lola/modules/test-module/module/AGENTS.md" in content
        assert "<!-- lola:module:test-module:start -->" in content

    def test_append_context_missing_file_returns_false(self, tmp_path):
        """--append-context returns False when the context file doesn't exist."""
        from lola.targets.install import _install_instructions

        target = ClaudeCodeTarget()
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()
        (module_dir / "AGENTS.md").write_text("# Instructions")

        module = Module.from_path(module_dir)
        assert module is not None

        result = _install_instructions(
            target,
            module,
            module_dir,
            str(tmp_path),
            append_context=["nonexistent/FILE.md"],
        )

        assert result is False

    def test_append_context_preserves_existing_claude_md(self, tmp_path):
        """--append-context preserves existing content in CLAUDE.md."""
        from lola.targets.install import _install_instructions

        target = ClaudeCodeTarget()
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()
        context_dir = module_dir / "module"
        context_dir.mkdir()
        (context_dir / "AGENTS.md").write_text("# Module context")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        local_module = project_dir / ".lola" / "modules" / "test-module"
        local_module.mkdir(parents=True)
        shutil.copytree(module_dir, local_module, dirs_exist_ok=True)

        claude_md = project_dir / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nExisting content.\n")

        module = Module.from_path(module_dir)
        assert module is not None

        result = _install_instructions(
            target,
            module,
            local_module,
            str(project_dir),
            append_context=["module/AGENTS.md"],
        )

        assert result is True
        content = claude_md.read_text()
        assert "# My Project" in content
        assert "Existing content." in content
        assert "Read the module context from" in content

    def test_default_behavior_unchanged_without_flag(self, tmp_path):
        """Without --append-context, verbatim copy still works."""
        from lola.targets.install import _install_instructions

        target = ClaudeCodeTarget()
        module_dir = tmp_path / "test-module"
        module_dir.mkdir()
        (module_dir / "AGENTS.md").write_text("# Verbatim Instructions")
        skills_dir = module_dir / "skills" / "s1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: T\n---\nC")

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        module = Module.from_path(module_dir)
        assert module is not None

        result = _install_instructions(
            target,
            module,
            module_dir,
            str(project_dir),
        )

        assert result is True
        claude_md = project_dir / "CLAUDE.md"
        content = claude_md.read_text()
        assert "# Verbatim Instructions" in content
        assert "Read the module context from" not in content


class TestListWithAppendContext:
    """Tests for lola list showing append_context."""

    def test_list_shows_append_context(self, tmp_path):
        """lola list displays append-context when set."""
        from lola.cli.install import list_installed_cmd

        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="test-module",
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                has_instructions=True,
                append_context=["module/AGENTS.md"],
            )
        )

        runner = CliRunner()
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = runner.invoke(list_installed_cmd)

        assert result.exit_code == 0
        assert "append-context" in result.output
        assert "module/AGENTS.md" in result.output

    def test_list_hides_append_context_when_not_set(self, tmp_path):
        """lola list omits append-context when not set."""
        from lola.cli.install import list_installed_cmd

        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="test-module",
                assistant="claude-code",
                scope="project",
                project_path=str(tmp_path),
                has_instructions=True,
            )
        )

        runner = CliRunner()
        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = runner.invoke(list_installed_cmd)

        assert result.exit_code == 0
        assert "append-context" not in result.output
