"""Tests for the mod CLI commands."""

import shutil
from unittest.mock import patch


from lola.cli.mod import mod, list_registered_modules


class TestModGroup:
    """Tests for the mod command group."""

    def test_mod_help(self, cli_runner):
        """Show mod help."""
        result = cli_runner.invoke(mod, ["--help"])
        assert result.exit_code == 0
        assert "Manage lola modules" in result.output

    def test_mod_no_args(self, cli_runner):
        """Show help when no subcommand."""
        result = cli_runner.invoke(mod, [])
        # Click groups with no args show usage/help
        assert "Manage lola modules" in result.output or "Usage" in result.output


class TestModAdd:
    """Tests for mod add command."""

    def test_add_help(self, cli_runner):
        """Show add help."""
        result = cli_runner.invoke(mod, ["add", "--help"])
        assert result.exit_code == 0
        assert "Add a module" in result.output
        assert "git repository" in result.output.lower()

    def test_add_local_folder(self, cli_runner, sample_module, tmp_path):
        """Add module from local folder."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["add", str(sample_module)])

        assert result.exit_code == 0
        assert "Added" in result.output
        assert (modules_dir / "sample-module").exists()

    def test_add_with_name_override(self, cli_runner, sample_module, tmp_path):
        """Add module with custom name."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(
                mod, ["add", str(sample_module), "-n", "custom-name"]
            )

        assert result.exit_code == 0
        assert "custom-name" in result.output
        assert (modules_dir / "custom-name").exists()

    def test_add_invalid_source(self, cli_runner, tmp_path):
        """Fail on invalid source."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Create a non-module file
        invalid_file = tmp_path / "notamodule.txt"
        invalid_file.write_text("not a module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["add", str(invalid_file)])

        assert result.exit_code == 1
        assert "Cannot determine source type" in result.output

    def test_add_invalid_name_override(self, cli_runner, sample_module, tmp_path):
        """Fail on invalid name override."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(
                mod, ["add", str(sample_module), "-n", "../traversal"]
            )

        assert result.exit_code == 1
        assert "path separators" in result.output.lower()


class TestModList:
    """Tests for mod ls command."""

    def test_ls_empty(self, cli_runner, tmp_path):
        """List when no modules."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["ls"])

        assert result.exit_code == 0
        assert "No modules" in result.output

    def test_ls_with_modules(self, cli_runner, sample_module, tmp_path):
        """List modules."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["ls"])

        assert result.exit_code == 0
        assert "sample-module" in result.output


class TestModRemove:
    """Tests for mod rm command."""

    def test_rm_help(self, cli_runner):
        """Show rm help."""
        result = cli_runner.invoke(mod, ["rm", "--help"])
        assert result.exit_code == 0
        assert "Remove a module" in result.output

    def test_rm_nonexistent(self, cli_runner, tmp_path):
        """Fail removing nonexistent module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["rm", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_rm_module(self, cli_runner, sample_module, tmp_path):
        """Remove a module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module to registry
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["rm", "sample-module", "-f"])

        assert result.exit_code == 0
        assert "removed" in result.output.lower()
        assert not dest.exists()


class TestModInfo:
    """Tests for mod info command."""

    def test_info_help(self, cli_runner):
        """Show info help."""
        result = cli_runner.invoke(mod, ["info", "--help"])
        assert result.exit_code == 0

    def test_info_nonexistent(self, cli_runner, tmp_path):
        """Fail on nonexistent module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["info", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_info_module(self, cli_runner, sample_module, tmp_path):
        """Show module info."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["info", "sample-module"])

        assert result.exit_code == 0
        assert "sample-module" in result.output


class TestListRegisteredModules:
    """Tests for list_registered_modules helper function."""

    def test_empty_registry(self, tmp_path):
        """Return empty list when no modules."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = list_registered_modules()

        assert result == []

    def test_with_modules(self, sample_module, tmp_path):
        """Return list of modules."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = list_registered_modules()

        assert len(result) == 1
        assert result[0].name == "sample-module"

    def test_ignores_empty_directories(self, tmp_path):
        """Ignore directories without skills or commands."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Create empty module (no skills or commands)
        empty_dir = modules_dir / "empty"
        empty_dir.mkdir()

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = list_registered_modules()

        assert result == []


class TestModInit:
    """Tests for mod init command."""

    def test_init_help(self, cli_runner):
        """Show init help."""
        result = cli_runner.invoke(mod, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize a new lola module" in result.output

    def test_init_current_dir(self, cli_runner, tmp_path):
        """Initialize module in current directory."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init"])

            assert result.exit_code == 0
            assert "Initialized module" in result.output
            # Default skill, command, and agent should be created
            assert (tmp_path / "skills" / "example-skill" / "SKILL.md").exists()
            assert (tmp_path / "commands" / "example-command.md").exists()
            assert (tmp_path / "agents" / "example-agent.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_with_name(self, cli_runner, tmp_path):
        """Initialize module with name creates subdirectory."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-new-module"])

            assert result.exit_code == 0
            assert "my-new-module" in result.output
            # Default skill, command, and agent should be created
            assert (tmp_path / "my-new-module" / "skills" / "example-skill" / "SKILL.md").exists()
            assert (
                tmp_path / "my-new-module" / "commands" / "example-command.md"
            ).exists()
            assert (
                tmp_path / "my-new-module" / "agents" / "example-agent.md"
            ).exists()
        finally:
            os.chdir(original_dir)

    def test_init_no_skill(self, cli_runner, tmp_path):
        """Initialize module without skill."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod", "--no-skill"])

            assert result.exit_code == 0
            # Module directory should exist
            assert (tmp_path / "mymod").exists()
            # Skills directory should exist but be empty (no example-skill)
            assert (tmp_path / "mymod" / "skills").exists()
            assert not (tmp_path / "mymod" / "skills" / "example-skill").exists()
            # But command and agent should still be created
            assert (tmp_path / "mymod" / "commands" / "example-command.md").exists()
            assert (tmp_path / "mymod" / "agents" / "example-agent.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_with_custom_skill(self, cli_runner, tmp_path):
        """Initialize module with custom skill name."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod", "-s", "custom-skill"])

            assert result.exit_code == 0
            assert (tmp_path / "mymod" / "skills" / "custom-skill" / "SKILL.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_with_command(self, cli_runner, tmp_path):
        """Initialize module with command."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod", "-c", "my-cmd"])

            assert result.exit_code == 0
            assert (tmp_path / "mymod" / "commands" / "my-cmd.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_already_exists(self, cli_runner, tmp_path):
        """Fail when directory already exists."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            (tmp_path / "existing").mkdir()
            result = cli_runner.invoke(mod, ["init", "existing"])

            assert result.exit_code == 1
            assert "already exists" in result.output
        finally:
            os.chdir(original_dir)

    def test_init_skill_already_exists(self, cli_runner, tmp_path):
        """Fail when default skill directory already exists."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            # Create the default skill directory under skills/
            (tmp_path / "skills").mkdir()
            (tmp_path / "skills" / "example-skill").mkdir()
            result = cli_runner.invoke(mod, ["init"])

            assert result.exit_code == 1
            assert "already exists" in result.output
        finally:
            os.chdir(original_dir)


class TestModListVerbose:
    """Tests for mod ls with verbose flag."""

    def test_ls_verbose(self, cli_runner, sample_module, tmp_path):
        """List modules with verbose output."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module to registry
        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["ls", "-v"])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert "skill1" in result.output
        assert "cmd1" in result.output


class TestModInfoAdvanced:
    """Advanced tests for mod info command."""

    def test_info_with_source_info(self, cli_runner, sample_module, tmp_path):
        """Show source info in module details."""
        from lola.parsers import save_source_info

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module and add source info
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)
        save_source_info(dest, "https://github.com/user/repo.git", "git")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["info", "sample-module"])

        assert result.exit_code == 0
        assert "Source" in result.output
        assert "git" in result.output

    def test_info_empty_module(self, cli_runner, tmp_path):
        """Show warning for empty module (no skills or commands)."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Create empty module (no skills or commands)
        empty = modules_dir / "empty"
        empty.mkdir()

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["info", "empty"])

        assert result.exit_code == 0
        assert "No skills or commands found" in result.output


class TestModUpdate:
    """Tests for mod update command."""

    def test_update_help(self, cli_runner):
        """Show update help."""
        result = cli_runner.invoke(mod, ["update", "--help"])
        assert result.exit_code == 0
        assert "Update module" in result.output

    def test_update_nonexistent(self, cli_runner, tmp_path):
        """Fail updating nonexistent module."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["update", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_update_no_modules(self, cli_runner, tmp_path):
        """Update all when no modules registered."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["update"])

        assert result.exit_code == 0
        assert "No modules to update" in result.output

    def test_update_specific_module(self, cli_runner, sample_module, tmp_path):
        """Update a specific module from folder source."""
        from lola.parsers import save_source_info

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module and save source info pointing to original
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)
        save_source_info(dest, str(sample_module), "folder")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["update", "sample-module"])

        assert result.exit_code == 0
        assert "Updated" in result.output

    def test_update_all_modules(self, cli_runner, sample_module, tmp_path):
        """Update all registered modules."""
        from lola.parsers import save_source_info

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        # Copy sample module and save source info
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)
        save_source_info(dest, str(sample_module), "folder")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["update"])

        assert result.exit_code == 0
        assert "Updating 1 module" in result.output


class TestModRemoveAdvanced:
    """Advanced tests for mod rm command."""

    def test_rm_with_installations(self, cli_runner, sample_module, tmp_path):
        """Remove module that has installations."""
        from unittest.mock import MagicMock
        from lola.models import Installation, InstallationRegistry

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)

        # Create installation record
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="sample-module",
                assistant="claude-code",
                scope="user",
                skills=["sample-module-skill1"],
            )
        )

        # Create mock skill directory
        skill_dest = tmp_path / "skills" / "sample-module-skill1"
        skill_dest.mkdir(parents=True)
        (skill_dest / "SKILL.md").write_text("content")

        # Create mock target
        mock_target = MagicMock()
        mock_target.get_skill_path.return_value = tmp_path / "skills"
        mock_target.get_command_path.return_value = tmp_path / "commands"
        mock_target.get_command_filename.side_effect = lambda m, c: f"{m}-{c}.md"
        mock_target.remove_skill.return_value = True

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.get_target", return_value=mock_target),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["rm", "sample-module", "-f"])

        assert result.exit_code == 0
        assert "removed" in result.output.lower()
        assert not dest.exists()

    def test_rm_cancelled(self, cli_runner, sample_module, tmp_path):
        """Cancel removal without force flag."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Copy sample module
        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            # Input 'n' to cancel
            result = cli_runner.invoke(mod, ["rm", "sample-module"], input="n\n")

        assert "Cancelled" in result.output
        assert dest.exists()  # Module should still exist
