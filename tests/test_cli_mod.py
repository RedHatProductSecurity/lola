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
        assert "Cannot handle source" in result.output

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
            # Default skill, command, and agent should be created in module/
            assert (
                tmp_path / "module" / "skills" / "example-skill" / "SKILL.md"
            ).exists()
            assert (tmp_path / "module" / "commands" / "example-command.md").exists()
            assert (tmp_path / "module" / "agents" / "example-agent.md").exists()
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
            # Default skill, command, and agent should be created in module/
            assert (
                tmp_path
                / "my-new-module"
                / "module"
                / "skills"
                / "example-skill"
                / "SKILL.md"
            ).exists()
            assert (
                tmp_path
                / "my-new-module"
                / "module"
                / "commands"
                / "example-command.md"
            ).exists()
            assert (
                tmp_path / "my-new-module" / "module" / "agents" / "example-agent.md"
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
            assert (tmp_path / "mymod" / "module" / "skills").exists()
            assert not (
                tmp_path / "mymod" / "module" / "skills" / "example-skill"
            ).exists()
            # But command and agent should still be created
            assert (
                tmp_path / "mymod" / "module" / "commands" / "example-command.md"
            ).exists()
            assert (
                tmp_path / "mymod" / "module" / "agents" / "example-agent.md"
            ).exists()
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
            assert (
                tmp_path / "mymod" / "module" / "skills" / "custom-skill" / "SKILL.md"
            ).exists()
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
            assert (tmp_path / "mymod" / "module" / "commands" / "my-cmd.md").exists()
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
        """Warn and skip when default skill directory already exists."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            # Create the default skill directory under module/skills/
            (tmp_path / "module").mkdir()
            (tmp_path / "module" / "skills").mkdir()
            (tmp_path / "module" / "skills" / "example-skill").mkdir()
            result = cli_runner.invoke(mod, ["init"])

            # Command should succeed but warn about skipping existing skill
            assert result.exit_code == 0
            assert "already exists" in result.output
        finally:
            os.chdir(original_dir)

    def test_init_creates_mcps_json(self, cli_runner, tmp_path):
        """Initialize module creates mcps.json by default."""
        import os

        from lola.config import MCPS_FILE

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod"])

            assert result.exit_code == 0
            mcps_file = tmp_path / "mymod" / "module" / MCPS_FILE
            assert mcps_file.exists()

            # Verify content has [REPLACE:] placeholders (new template format)
            content = mcps_file.read_text()
            assert "mcpServers" in content
            assert "[REPLACE:" in content
        finally:
            os.chdir(original_dir)

    def test_init_creates_agents_md(self, cli_runner, tmp_path):
        """Initialize module creates AGENTS.md by default."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod"])

            assert result.exit_code == 0
            agents_file = tmp_path / "mymod" / "module" / "AGENTS.md"
            assert agents_file.exists()

            # Verify content
            content = agents_file.read_text()
            assert "# Mymod" in content
            assert "## When to Use" in content
        finally:
            os.chdir(original_dir)

    def test_init_no_mcps_flag(self, cli_runner, tmp_path):
        """Initialize module with --no-mcps skips mcps.json."""
        import os

        from lola.config import MCPS_FILE

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod", "--no-mcps"])

            assert result.exit_code == 0
            mcps_file = tmp_path / "mymod" / "module" / MCPS_FILE
            assert not mcps_file.exists()
        finally:
            os.chdir(original_dir)

    def test_init_no_instructions_flag(self, cli_runner, tmp_path):
        """Initialize module with --no-instructions skips AGENTS.md."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "mymod", "--no-instructions"])

            assert result.exit_code == 0
            agents_file = tmp_path / "mymod" / "module" / "AGENTS.md"
            assert not agents_file.exists()
        finally:
            os.chdir(original_dir)

    def test_init_both_no_flags(self, cli_runner, tmp_path):
        """Initialize module with both --no-mcps and --no-instructions."""
        import os

        from lola.config import MCPS_FILE

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod, ["init", "mymod", "--no-mcps", "--no-instructions"]
            )

            assert result.exit_code == 0
            assert not (tmp_path / "mymod" / "module" / MCPS_FILE).exists()
            assert not (tmp_path / "mymod" / "module" / "AGENTS.md").exists()
            # But other files should still be created
            assert (
                tmp_path / "mymod" / "module" / "skills" / "example-skill" / "SKILL.md"
            ).exists()
        finally:
            os.chdir(original_dir)

    def test_init_mcps_with_no_skill_command_agent(self, cli_runner, tmp_path):
        """mcps.json and AGENTS.md created even when --no-skill --no-command --no-agent."""
        import os

        from lola.config import MCPS_FILE

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod,
                [
                    "init",
                    "mymod",
                    "--no-skill",
                    "--no-command",
                    "--no-agent",
                ],
            )

            assert result.exit_code == 0
            # mcps.json should be created in module/
            mcps_file = tmp_path / "mymod" / "module" / MCPS_FILE
            assert mcps_file.exists()
            content = mcps_file.read_text()
            assert "mcpServers" in content

            # AGENTS.md should be created in module/
            agents_file = tmp_path / "mymod" / "module" / "AGENTS.md"
            assert agents_file.exists()
            agents_content = agents_file.read_text()
            assert "# Mymod" in agents_content
        finally:
            os.chdir(original_dir)

    def test_init_agents_md_adapts_to_content(self, cli_runner, tmp_path):
        """AGENTS.md adapts based on what skills/commands/agents were created."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod,
                ["init", "mymod", "-s", "my-skill", "-c", "my-cmd", "-g", "my-agent"],
            )

            assert result.exit_code == 0
            agents_file = tmp_path / "mymod" / "module" / "AGENTS.md"
            content = agents_file.read_text()

            # Should mention the skill
            assert "my-skill" in content.lower() or "My Skill" in content
            # Should mention the command (now uses dot notation)
            assert "my-cmd" in content.lower() or "My Cmd" in content
            assert "mymod.my-cmd" in content
            # Should mention the agent (now uses dot notation)
            assert "my-agent" in content.lower() or "My Agent" in content
            assert "mymod.my-agent" in content
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


class TestModInitModuleSubdir:
    """Tests for mod init with module/ subdirectory structure."""

    def test_init_creates_module_subdirectory(self, cli_runner, tmp_path):
        """Init creates module/ subdirectory with skills, commands, agents."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-module"])

            assert result.exit_code == 0
            assert "Initialized module" in result.output
            # Module/ subdirectory should contain skills, commands, agents
            assert (
                tmp_path
                / "my-module"
                / "module"
                / "skills"
                / "example-skill"
                / "SKILL.md"
            ).exists()
            assert (
                tmp_path / "my-module" / "module" / "commands" / "example-command.md"
            ).exists()
            assert (
                tmp_path / "my-module" / "module" / "agents" / "example-agent.md"
            ).exists()
            # mcps.json and AGENTS.md should be in module/
            assert (tmp_path / "my-module" / "module" / "mcps.json").exists()
            assert (tmp_path / "my-module" / "module" / "AGENTS.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_creates_readme_at_root(self, cli_runner, tmp_path):
        """Init creates README.md at repo root, not in module/."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-module"])

            assert result.exit_code == 0
            # README.md at repo root
            readme = tmp_path / "my-module" / "README.md"
            assert readme.exists()
            content = readme.read_text()
            assert "# My Module" in content
            assert "module/" in content  # Should mention module/ structure
            # No README inside module/
            assert not (tmp_path / "my-module" / "module" / "README.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_templates_have_replace_markers(self, cli_runner, tmp_path):
        """Template files contain [REPLACE:] markers."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-module"])

            assert result.exit_code == 0
            # Check README.md has markers
            readme = (tmp_path / "my-module" / "README.md").read_text()
            assert "[REPLACE:" in readme

            # Check SKILL.md has markers
            skill_md = (
                tmp_path
                / "my-module"
                / "module"
                / "skills"
                / "example-skill"
                / "SKILL.md"
            ).read_text()
            assert "[REPLACE:" in skill_md

            # Check command has markers
            cmd_md = (
                tmp_path / "my-module" / "module" / "commands" / "example-command.md"
            ).read_text()
            assert "[REPLACE:" in cmd_md

            # Check agent has markers
            agent_md = (
                tmp_path / "my-module" / "module" / "agents" / "example-agent.md"
            ).read_text()
            assert "[REPLACE:" in agent_md

            # Check mcps.json has markers
            mcps_json = (tmp_path / "my-module" / "module" / "mcps.json").read_text()
            assert "[REPLACE:" in mcps_json

            # Check AGENTS.md has markers
            agents_md = (tmp_path / "my-module" / "module" / "AGENTS.md").read_text()
            assert "[REPLACE:" in agents_md
        finally:
            os.chdir(original_dir)

    def test_init_current_dir_creates_module_subdir(self, cli_runner, tmp_path):
        """Init in current directory uses directory name and creates module/."""
        import os

        original_dir = os.getcwd()
        # Create and switch to a named directory
        named_dir = tmp_path / "my-project"
        named_dir.mkdir()

        try:
            os.chdir(named_dir)
            result = cli_runner.invoke(mod, ["init"])

            assert result.exit_code == 0
            assert "my-project" in result.output
            # Module/ subdirectory should be created
            assert (
                named_dir / "module" / "skills" / "example-skill" / "SKILL.md"
            ).exists()
            assert (named_dir / "module" / "commands" / "example-command.md").exists()
            # README.md at root
            assert (named_dir / "README.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_agents_md_uses_dot_notation(self, cli_runner, tmp_path):
        """AGENTS.md uses dot-separated naming convention."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod,
                ["init", "my-mod", "-s", "my-skill", "-c", "my-cmd", "-g", "my-agent"],
            )

            assert result.exit_code == 0
            agents_md = (tmp_path / "my-mod" / "module" / "AGENTS.md").read_text()
            # Should use dot-separated notation
            assert "/my-mod.my-cmd" in agents_md
            assert "@my-mod.my-agent" in agents_md
        finally:
            os.chdir(original_dir)

    def test_init_minimal_flag_creates_empty_structure(self, cli_runner, tmp_path):
        """Init with --minimal creates only empty directories."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-module", "--minimal"])

            assert result.exit_code == 0
            # Empty directories exist
            assert (tmp_path / "my-module" / "module" / "skills").exists()
            assert (tmp_path / "my-module" / "module" / "commands").exists()
            assert (tmp_path / "my-module" / "module" / "agents").exists()
            # No example content
            assert not (
                tmp_path / "my-module" / "module" / "skills" / "example-skill"
            ).exists()
            assert not (
                tmp_path / "my-module" / "module" / "commands" / "example-command.md"
            ).exists()
            assert not (
                tmp_path / "my-module" / "module" / "agents" / "example-agent.md"
            ).exists()
            # No mcps.json or AGENTS.md
            assert not (tmp_path / "my-module" / "module" / "mcps.json").exists()
            assert not (tmp_path / "my-module" / "module" / "AGENTS.md").exists()
            # README.md still created at root
            assert (tmp_path / "my-module" / "README.md").exists()
        finally:
            os.chdir(original_dir)

    def test_init_force_overwrites_existing(self, cli_runner, tmp_path):
        """Init with --force overwrites existing directory."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            # Create existing directory with some content
            existing = tmp_path / "my-module"
            existing.mkdir()
            (existing / "old-file.txt").write_text("old content")

            result = cli_runner.invoke(mod, ["init", "my-module", "--force"])

            assert result.exit_code == 0
            # New structure created
            assert (existing / "module" / "skills").exists()
            assert (existing / "README.md").exists()
            # Old file should be gone
            assert not (existing / "old-file.txt").exists()
        finally:
            os.chdir(original_dir)

    def test_init_no_force_fails_on_existing(self, cli_runner, tmp_path):
        """Init without --force fails when directory exists."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            # Create existing directory
            (tmp_path / "existing").mkdir()

            result = cli_runner.invoke(mod, ["init", "existing"])

            assert result.exit_code == 1
            assert "already exists" in result.output
        finally:
            os.chdir(original_dir)


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
