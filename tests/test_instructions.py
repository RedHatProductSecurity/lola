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


# =============================================================================
# Claude Code Target Tests
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
        """remove_instructions removes module from managed section."""
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
