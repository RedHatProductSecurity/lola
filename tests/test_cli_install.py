"""Tests for the install CLI commands."""

import shutil
from unittest.mock import patch


from lola.cli.install import install_cmd, uninstall_cmd, update_cmd, list_installed_cmd
from lola.models import Installation, InstallationRegistry


class TestInstallCmd:
    """Tests for install command."""

    def test_install_help(self, cli_runner):
        """Show install help."""
        result = cli_runner.invoke(install_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Install a module" in result.output

    def test_install_missing_module(self, cli_runner, tmp_path):
        """Fail when module not found."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(install_cmd, ["nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_install_project_scope_defaults_to_cwd(self, cli_runner, tmp_path):
        """Project scope uses current directory when no path provided."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(install_cmd, ["mymodule", "-s", "project"])

        # Should fail because module doesn't exist (not because of missing path)
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_install_project_path_not_exists(self, cli_runner, tmp_path):
        """Fail when project path doesn't exist."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(
                install_cmd, ["mymodule", "-s", "project", "/nonexistent/path"]
            )

        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_install_module(self, cli_runner, sample_module, tmp_path):
        """Install a module successfully."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        # Create mock assistant paths
        skill_dest = tmp_path / "skills"
        command_dest = tmp_path / "commands"
        skill_dest.mkdir()
        command_dest.mkdir()

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch(
                "lola.cli.install.install_to_assistant", return_value=1
            ) as mock_install,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(
                install_cmd, ["sample-module", "-a", "claude-code"]
            )

        assert result.exit_code == 0
        assert "Installing" in result.output
        mock_install.assert_called_once()


class TestUninstallCmd:
    """Tests for uninstall command."""

    def test_uninstall_help(self, cli_runner):
        """Show uninstall help."""
        result = cli_runner.invoke(uninstall_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Uninstall a module" in result.output

    def test_uninstall_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations found."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(uninstall_cmd, ["nonexistent"])

        assert result.exit_code == 0
        assert "No installations found" in result.output

    def test_uninstall_with_force(self, cli_runner, tmp_path):
        """Uninstall with force flag."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule-skill1"],
            commands=["cmd1"],
        )
        registry.add(inst)

        # Create mock skill/command paths
        skill_dest = tmp_path / "skills"
        skill_dir = skill_dest / "mymodule-skill1"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("content")

        command_dest = tmp_path / "commands"
        command_dest.mkdir()
        (command_dest / "mymodule-cmd1.md").write_text("content")

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_assistant_skill_path", return_value=skill_dest),
            patch(
                "lola.cli.install.get_assistant_command_path", return_value=command_dest
            ),
        ):
            result = cli_runner.invoke(uninstall_cmd, ["mymodule", "-f"])

        assert result.exit_code == 0
        assert "Uninstalled" in result.output


class TestUpdateCmd:
    """Tests for update command."""

    def test_update_help(self, cli_runner):
        """Show update help."""
        result = cli_runner.invoke(update_cmd, ["--help"])
        assert result.exit_code == 0
        assert "Regenerate assistant files" in result.output

    def test_update_no_installations(self, cli_runner, tmp_path):
        """Warn when no installations to update."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(update_cmd, [])

        assert result.exit_code == 0
        assert "No installations to update" in result.output

    def test_update_specific_module(self, cli_runner, sample_module, tmp_path):
        """Update a specific module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        # Create registry with installation
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="sample-module",
            assistant="claude-code",
            scope="user",
            skills=["sample-module-skill1"],
            commands=["cmd1"],
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_assistant_skill_path", return_value=skill_dest),
            patch(
                "lola.cli.install.get_assistant_command_path", return_value=command_dest
            ),
        ):
            result = cli_runner.invoke(update_cmd, ["sample-module"])

        assert result.exit_code == 0
        assert "Update complete" in result.output

    def test_update_removes_orphaned_commands(self, cli_runner, tmp_path):
        """Update removes orphaned command files when command removed from module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with only one command (cmd1 removed)
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skill (auto-discovered via SKILL.md)
        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create command (auto-discovered from commands/*.md)
        commands_dir = module_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "cmd2.md").write_text("---\ndescription: Cmd 2\n---\nContent")

        # Create registry with old installation (had cmd1 and cmd2)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule-skill1"],
            commands=["cmd1", "cmd2"],  # cmd1 is orphaned
        )
        registry.add(inst)

        # Create mock paths with orphaned file
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create orphaned command file
        orphan_cmd = command_dest / "mymodule-cmd1.md"
        orphan_cmd.write_text("orphaned content")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_assistant_skill_path", return_value=skill_dest),
            patch(
                "lola.cli.install.get_assistant_command_path", return_value=command_dest
            ),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0
        assert "orphaned" in result.output.lower()
        assert not orphan_cmd.exists(), "Orphaned command file should be removed"

    def test_update_removes_orphaned_skills(self, cli_runner, tmp_path):
        """Update removes orphaned skill files when skill removed from module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with only skill1 (skill2 removed)
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skill (auto-discovered via SKILL.md) - skill2 was removed
        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create registry with old installation (had skill1 and skill2)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule-skill1", "mymodule-skill2"],  # skill2 is orphaned
            commands=[],
        )
        registry.add(inst)

        # Create mock paths with orphaned file
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        # Create orphaned skill directory
        orphan_skill = skill_dest / "mymodule-skill2"
        orphan_skill.mkdir()
        (orphan_skill / "SKILL.md").write_text("orphaned content")

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_assistant_skill_path", return_value=skill_dest),
            patch(
                "lola.cli.install.get_assistant_command_path", return_value=command_dest
            ),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0
        assert "orphaned" in result.output.lower()
        assert not orphan_skill.exists(), "Orphaned skill directory should be removed"

    def test_update_updates_registry_after_cleanup(self, cli_runner, tmp_path):
        """Update updates registry to reflect current module state."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a module with fewer items than registry
        module_dir = modules_dir / "mymodule"
        module_dir.mkdir()

        # Create skill (auto-discovered via SKILL.md)
        skill_dir = module_dir / "skill1"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: Skill 1\n---\nContent")

        # Create command (auto-discovered from commands/*.md)
        commands_dir = module_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "cmd1.md").write_text("---\ndescription: Cmd 1\n---\nContent")

        # Create registry with old installation (had more items)
        registry = InstallationRegistry(installed_file)
        inst = Installation(
            module_name="mymodule",
            assistant="claude-code",
            scope="user",
            skills=["mymodule-skill1", "mymodule-skill2", "mymodule-skill3"],
            commands=["cmd1", "cmd2"],
        )
        registry.add(inst)

        # Create mock paths
        skill_dest = tmp_path / "skills"
        skill_dest.mkdir()
        command_dest = tmp_path / "commands"
        command_dest.mkdir()

        with (
            patch("lola.cli.install.MODULES_DIR", modules_dir),
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
            patch("lola.cli.install.get_local_modules_path", return_value=modules_dir),
            patch("lola.cli.install.get_assistant_skill_path", return_value=skill_dest),
            patch(
                "lola.cli.install.get_assistant_command_path", return_value=command_dest
            ),
        ):
            result = cli_runner.invoke(update_cmd, ["mymodule"])

        assert result.exit_code == 0

        # Registry should now reflect current module state
        updated_inst = registry.find("mymodule")[0]
        assert set(updated_inst.skills) == {"mymodule-skill1"}
        assert set(updated_inst.commands) == {"cmd1"}


class TestListInstalledCmd:
    """Tests for installed (list) command."""

    def test_list_help(self, cli_runner):
        """Show list help."""
        result = cli_runner.invoke(list_installed_cmd, ["--help"])
        assert result.exit_code == 0
        assert "List all installed modules" in result.output

    def test_list_empty(self, cli_runner, tmp_path):
        """List when no modules installed."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry") as mock_registry,
        ):
            mock_registry.return_value = InstallationRegistry(installed_file)
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "No modules installed" in result.output

    def test_list_with_installations(self, cli_runner, tmp_path):
        """List installed modules."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="module1",
                assistant="claude-code",
                scope="user",
                skills=["module1-skill1"],
            )
        )
        registry.add(
            Installation(
                module_name="module2",
                assistant="cursor",
                scope="user",
                commands=["cmd1"],
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, [])

        assert result.exit_code == 0
        assert "module1" in result.output
        assert "module2" in result.output
        assert "Installed (2 modules)" in result.output

    def test_list_filter_by_assistant(self, cli_runner, tmp_path):
        """Filter list by assistant."""
        installed_file = tmp_path / ".lola" / "installed.yml"
        installed_file.parent.mkdir(parents=True)

        # Create registry with installations
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="module1",
                assistant="claude-code",
                scope="user",
            )
        )
        registry.add(
            Installation(
                module_name="module2",
                assistant="cursor",
                scope="user",
            )
        )

        with (
            patch("lola.cli.install.ensure_lola_dirs"),
            patch("lola.cli.install.get_registry", return_value=registry),
        ):
            result = cli_runner.invoke(list_installed_cmd, ["-a", "claude-code"])

        assert result.exit_code == 0
        assert "module1" in result.output
        assert "module2" not in result.output
        assert "Installed (1 module" in result.output
