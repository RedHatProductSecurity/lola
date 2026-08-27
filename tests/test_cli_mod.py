"""Tests for the mod CLI commands."""

import json
import shutil
from unittest.mock import patch


from lola.agent_plugins import PLUGIN_SCHEMA
from lola.cli.mod import mod, list_registered_modules


def _plugin_source(tmp_path, dirname, name):
    """Create an Agent Plugins source folder with one skill."""
    source = tmp_path / dirname
    skill = source / "skills" / "review"
    skill.mkdir(parents=True)
    (source / "plugin.json").write_text(
        json.dumps({"$schema": PLUGIN_SCHEMA, "name": name})
    )
    (skill / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\n"
    )
    return source


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


class TestAgentPluginInit:
    """Tests for Agent Plugins scaffolding."""

    def test_init_defaults_to_agent_plugins(self, cli_runner, tmp_path, monkeypatch):
        """Bare init creates the portable core and Lola extension namespace."""
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(mod, ["init", "my-plugin"])

        assert result.exit_code == 0
        root = tmp_path / "my-plugin"
        manifest = json.loads((root / "plugin.json").read_text())
        mcps = json.loads((root / "mcp.json").read_text())
        assert manifest["name"] == "my-plugin"
        assert "dev.getlola" in manifest["extensions"]
        assert mcps["$schema"].endswith("/1.0.0/mcp.schema.json")
        assert (root / "skills" / "example-skill" / "SKILL.md").exists()
        assert (root / "dev.getlola" / "commands" / "example-command.md").exists()
        assert (root / "dev.getlola" / "agents" / "example-agent.md").exists()
        assert (root / "dev.getlola" / "AGENTS.md").exists()
        assert not (root / "module").exists()

    def test_init_agent_plugin_existing_dir_needs_force(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """An existing directory errors unless --force is given."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "my-plugin").mkdir()

        result = cli_runner.invoke(
            mod, ["init", "my-plugin", "--format", "agent-plugins"]
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

        result = cli_runner.invoke(
            mod,
            ["init", "my-plugin", "--format", "agent-plugins", "--force"],
        )
        assert result.exit_code == 0
        assert (tmp_path / "my-plugin" / "plugin.json").exists()

    def test_init_agent_plugin_rerun_in_cwd(self, cli_runner, tmp_path, monkeypatch):
        """Re-running init inside the package directory succeeds."""
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        monkeypatch.chdir(plugin_dir)

        first = cli_runner.invoke(mod, ["init", "--format", "agent-plugins"])
        second = cli_runner.invoke(mod, ["init", "--format", "agent-plugins"])

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert (plugin_dir / "plugin.json").exists()

    def test_init_agent_plugin_rejects_invalid_name(
        self, cli_runner, tmp_path, monkeypatch
    ):
        """Plugin scaffolds enforce the v1 manifest name constraints."""
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(
            mod,
            ["init", "Bad_Name", "--format", "agent-plugins"],
        )

        assert result.exit_code == 1
        assert "invalid Agent Plugins name" in result.output


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

    def test_add_agent_plugin_uses_manifest_name(self, cli_runner, tmp_path):
        """Register Agent Plugins by plugin.json.name, not source dirname."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["add", str(source)])

        assert result.exit_code == 0
        assert "Added manifest-name" in result.output
        assert (modules_dir / "manifest-name").exists()
        assert not (modules_dir / "repository-name").exists()

    def test_add_agent_plugin_rejects_name_override(self, cli_runner, tmp_path):
        """Do not override the identity declared by plugin.json.name."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(
                mod,
                ["add", str(source), "--name", "override"],
            )

        assert result.exit_code == 1
        assert "plugin.json.name" in result.output

    def test_add_agent_plugin_conflict_declined(self, cli_runner, tmp_path):
        """Declining the manifest-name conflict keeps the existing module."""
        modules_dir = tmp_path / ".lola" / "modules"
        existing = modules_dir / "manifest-name"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("original")
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
        ):
            result = cli_runner.invoke(mod, ["add", str(source)], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        assert (existing / "keep.txt").exists()
        assert not (modules_dir / "repository-name").exists()

    def test_add_agent_plugin_conflict_overwrites(self, cli_runner, tmp_path):
        """Accepting the manifest-name conflict replaces the module."""
        modules_dir = tmp_path / ".lola" / "modules"
        existing = modules_dir / "manifest-name"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("original")
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
        ):
            result = cli_runner.invoke(mod, ["add", str(source)], input="y\n")

        assert result.exit_code == 0
        assert "Added manifest-name" in result.output
        assert (modules_dir / "manifest-name" / "plugin.json").exists()
        assert not (existing / "keep.txt").exists()

    def test_add_agent_plugin_invalid_manifest_errors(self, cli_runner, tmp_path):
        """A broken plugin.json fails cleanly instead of crashing."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")
        (source / "plugin.json").write_text(json.dumps({"name": "manifest-name"}))

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["add", str(source)])

        assert result.exit_code == 1
        assert "$schema" in result.output
        assert not (modules_dir / "repository-name").exists()

    def test_add_agent_plugin_conflict_non_interactive(self, cli_runner, tmp_path):
        """The overwrite prompt is not reachable without a TTY."""
        modules_dir = tmp_path / ".lola" / "modules"
        existing = modules_dir / "manifest-name"
        existing.mkdir(parents=True)
        (existing / "keep.txt").write_text("original")
        source = _plugin_source(tmp_path, "repository-name", "manifest-name")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=False),
        ):
            result = cli_runner.invoke(mod, ["add", str(source)])

        assert result.exit_code == 1
        assert "non-interactive" in result.output
        assert (existing / "keep.txt").exists()
        assert not (modules_dir / "repository-name").exists()

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

    def test_add_next_steps_hint(self, cli_runner, sample_module, tmp_path):
        """The post-add hint references install's -a and -s flags."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["add", str(sample_module)])

        assert result.exit_code == 0
        assert "Next steps:" in result.output
        assert "-a <assistant>" in result.output
        assert "-s <scope>" in result.output

    def test_add_ref_passed_to_fetch_and_save(
        self, cli_runner, sample_module, tmp_path
    ):
        """--ref flag is forwarded to fetch_module and save_source_info."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch(
                "lola.cli.mod.fetch_module", return_value=modules_dir / "sample-module"
            ) as mock_fetch,
            patch("lola.cli.mod.save_source_info") as mock_save,
        ):
            (modules_dir / "sample-module").mkdir()
            result = cli_runner.invoke(
                mod, ["add", "https://github.com/user/repo.git", "--ref", "v1.0.0"]
            )

        assert result.exit_code == 0
        # ref must be passed as 4th positional arg to fetch_module
        assert mock_fetch.call_args[0][3] == "v1.0.0"
        # ref must be passed as 5th positional arg to save_source_info
        assert mock_save.call_args[0][4] == "v1.0.0"

    def test_add_without_ref_passes_none(self, cli_runner, sample_module, tmp_path):
        """Without --ref, git_ref=None is passed (backward compat)."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch(
                "lola.cli.mod.fetch_module", return_value=modules_dir / "sample-module"
            ) as mock_fetch,
            patch("lola.cli.mod.save_source_info"),
        ):
            (modules_dir / "sample-module").mkdir()
            result = cli_runner.invoke(mod, ["add", "https://github.com/user/repo.git"])

        assert result.exit_code == 0
        assert mock_fetch.call_args[0][3] is None

    def test_add_ref_starting_with_dash_is_rejected(
        self, cli_runner, sample_module, tmp_path
    ):
        """--ref value starting with '-' is rejected to prevent option injection."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(
                mod,
                [
                    "add",
                    "https://github.com/user/repo.git",
                    "--ref",
                    "-upload-pack=evil",
                ],
            )

        assert result.exit_code == 1
        assert "refs cannot start with '-'" in result.output


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

    def test_ls_skips_broken_plugin(self, cli_runner, sample_module, tmp_path):
        """A registered module with a broken manifest is skipped, not fatal."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        shutil.copytree(sample_module, modules_dir / "sample-module")
        broken = modules_dir / "broken-plugin"
        broken.mkdir()
        (broken / "plugin.json").write_text("{not json")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["ls"])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert "broken-plugin" not in result.output


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
        assert "Initialize a new module" in result.output

    def test_init_current_dir(self, cli_runner, tmp_path):
        """Initialize module in current directory."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "--format", "lola"])

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

    def test_init_rejects_traversal_name(self, cli_runner, tmp_path):
        """A name is a directory component, never a path to delete."""
        import os

        victim = tmp_path / "victim"
        victim.mkdir()
        (victim / "keep.txt").write_text("original")
        workdir = tmp_path / "work"
        workdir.mkdir()
        original_dir = os.getcwd()

        try:
            os.chdir(workdir)
            result = cli_runner.invoke(mod, ["init", "../victim", "--force"])
        finally:
            os.chdir(original_dir)

        assert result.exit_code == 1
        assert (victim / "keep.txt").read_text() == "original"

    def test_init_plugin_preserves_existing_files(self, cli_runner, tmp_path):
        """Re-running init never overwrites an edited package."""
        import os

        (tmp_path / "plugin.json").write_text('{"name": "edited"}')
        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init"])
        finally:
            os.chdir(original_dir)

        assert result.exit_code == 0
        assert "already exists, skipping" in result.output
        assert (tmp_path / "plugin.json").read_text() == '{"name": "edited"}'
        assert (tmp_path / "README.md").exists()

    def test_init_unslugifiable_directory_name(self, cli_runner, tmp_path):
        """An underivable plugin name asks for an explicit one."""
        import os

        workdir = tmp_path / "___"
        workdir.mkdir()
        original_dir = os.getcwd()

        try:
            os.chdir(workdir)
            result = cli_runner.invoke(mod, ["init"])
        finally:
            os.chdir(original_dir)

        assert result.exit_code == 1
        assert "pass a name" in result.output

    def test_init_with_name(self, cli_runner, tmp_path):
        """Initialize module with name creates subdirectory."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod, ["init", "my-new-module", "--format", "lola"]
            )

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
            result = cli_runner.invoke(
                mod, ["init", "mymod", "--no-skill", "--format", "lola"]
            )

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
            result = cli_runner.invoke(
                mod, ["init", "mymod", "-s", "custom-skill", "--format", "lola"]
            )

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
            result = cli_runner.invoke(
                mod, ["init", "mymod", "-c", "my-cmd", "--format", "lola"]
            )

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
            result = cli_runner.invoke(mod, ["init", "existing", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "mymod", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "mymod", "--format", "lola"])

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
            result = cli_runner.invoke(
                mod, ["init", "mymod", "--no-mcps", "--format", "lola"]
            )

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
            result = cli_runner.invoke(
                mod, ["init", "mymod", "--no-instructions", "--format", "lola"]
            )

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
                mod,
                ["init", "mymod", "--no-mcps", "--no-instructions", "--format", "lola"],
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
                    "--format",
                    "lola",
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
                [
                    "init",
                    "mymod",
                    "-s",
                    "my-skill",
                    "-c",
                    "my-cmd",
                    "-g",
                    "my-agent",
                    "--format",
                    "lola",
                ],
            )

            assert result.exit_code == 0
            agents_file = tmp_path / "mymod" / "module" / "AGENTS.md"
            content = agents_file.read_text()

            # Should mention the skill
            assert "my-skill" in content.lower() or "My Skill" in content
            # Should mention the command (unprefixed)
            assert "my-cmd" in content.lower() or "My Cmd" in content
            assert "/my-cmd" in content
            # Should mention the agent (unprefixed)
            assert "my-agent" in content.lower() or "My Agent" in content
            assert "@my-agent" in content
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

    def test_info_from_path_dot(self, cli_runner, sample_module, tmp_path, monkeypatch):
        """Show module info using '.' for current directory."""
        # Change to the sample module directory
        monkeypatch.chdir(sample_module)

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", "."])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert "Skills" in result.output

    def test_info_from_relative_path(
        self, cli_runner, sample_module, tmp_path, monkeypatch
    ):
        """Show module info using a relative path."""
        # Change to parent of sample module
        monkeypatch.chdir(sample_module.parent)

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", "./sample-module"])

        assert result.exit_code == 0
        assert "sample-module" in result.output

    def test_info_from_absolute_path(self, cli_runner, sample_module, tmp_path):
        """Show module info using an absolute path."""
        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(sample_module)])

        assert result.exit_code == 0
        assert "sample-module" in result.output

    def test_info_path_not_found(self, cli_runner, tmp_path):
        """Fail on non-existent path."""
        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", "./nonexistent-path"])

        assert result.exit_code == 1
        assert "Path not found" in result.output

    def test_info_module_subdir_shows_descriptions(self, cli_runner, tmp_path):
        """Show descriptions for commands/agents in module/ subdirectory structure."""
        # Create module with module/ subdirectory structure
        module_dir = tmp_path / "test-mod"
        module_dir.mkdir()
        content_dir = module_dir / "module"
        content_dir.mkdir()

        # Create command with description
        commands_dir = content_dir / "commands"
        commands_dir.mkdir()
        (commands_dir / "my-cmd.md").write_text(
            "---\ndescription: My command description\n---\n\nCommand content"
        )

        # Create agent with description
        agents_dir = content_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "my-agent.md").write_text(
            "---\ndescription: My agent description\n---\n\nAgent content"
        )

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(module_dir)])

        assert result.exit_code == 0
        assert "/my-cmd" in result.output
        assert "My command description" in result.output
        assert "@my-agent" in result.output
        assert "My agent description" in result.output
        assert "(not found)" not in result.output

    def test_info_shows_hooks(self, cli_runner, tmp_path):
        """Show hooks section when lola.yaml defines pre/post-install hooks."""
        module_dir = tmp_path / "hooked-module"
        module_dir.mkdir()
        content_dir = module_dir / "module"
        content_dir.mkdir()

        # Minimal skill so the module is valid
        skills_dir = content_dir / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\n\nContent"
        )

        # Create the actual hook scripts on disk
        scripts_dir = content_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "setup.sh").write_text("#!/bin/sh\necho setup")
        (scripts_dir / "verify.sh").write_text("#!/bin/sh\necho verify")

        # lola.yaml with both hooks
        (content_dir / "lola.yaml").write_text(
            "hooks:\n  pre-install: scripts/setup.sh\n  post-install: scripts/verify.sh\n"
        )

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(module_dir)])

        assert result.exit_code == 0
        assert "Hooks" in result.output
        assert "pre-install" in result.output
        assert "scripts/setup.sh" in result.output
        assert "post-install" in result.output
        assert "scripts/verify.sh" in result.output
        assert "(not found)" not in result.output

    def test_info_shows_partial_hooks(self, cli_runner, tmp_path):
        """Show only defined hooks when only one hook is configured."""
        module_dir = tmp_path / "partial-hooks-module"
        module_dir.mkdir()
        content_dir = module_dir / "module"
        content_dir.mkdir()

        skills_dir = content_dir / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\n\nContent"
        )

        # Create the hook script on disk
        scripts_dir = content_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "setup.sh").write_text("#!/bin/sh\necho setup")

        # lola.yaml with only pre-install hook
        (content_dir / "lola.yaml").write_text(
            "hooks:\n  pre-install: scripts/setup.sh\n"
        )

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(module_dir)])

        assert result.exit_code == 0
        assert "Hooks" in result.output
        assert "pre-install" in result.output
        assert "scripts/setup.sh" in result.output
        assert "post-install" not in result.output

    def test_info_hooks_not_found_marker(self, cli_runner, tmp_path):
        """Show (not found) marker when hook script is missing from disk."""
        module_dir = tmp_path / "missing-hooks-module"
        module_dir.mkdir()
        content_dir = module_dir / "module"
        content_dir.mkdir()

        skills_dir = content_dir / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\n\nContent"
        )

        # lola.yaml references scripts that don't exist on disk
        (content_dir / "lola.yaml").write_text(
            "hooks:\n  pre-install: scripts/missing.sh\n"
        )

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(module_dir)])

        assert result.exit_code == 0
        assert "Hooks" in result.output
        assert "scripts/missing.sh" in result.output
        assert "(not found)" in result.output

    def test_info_no_hooks_section_when_absent(self, cli_runner, tmp_path):
        """Omit Hooks section entirely when no hooks are configured."""
        module_dir = tmp_path / "no-hooks-module"
        module_dir.mkdir()
        content_dir = module_dir / "module"
        content_dir.mkdir()

        skills_dir = content_dir / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: A skill\n---\n\nContent"
        )

        with patch("lola.cli.mod.ensure_lola_dirs"):
            result = cli_runner.invoke(mod, ["info", str(module_dir)])

        assert result.exit_code == 0
        assert "Hooks" not in result.output


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

    def test_update_replays_pinned_ref(self, cli_runner, tmp_path):
        """'lola mod update' replays the stored ref when fetching a git module."""
        from unittest.mock import MagicMock

        from lola.parsers import save_source_info

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        mod_path = modules_dir / "pinned-mod"
        mod_path.mkdir()
        save_source_info(mod_path, "https://example.com/repo.git", "git", ref="v1.0.0")

        fake_fetched = tmp_path / "fetched" / "pinned-mod"
        fake_fetched.mkdir(parents=True)
        save_source_info(
            fake_fetched, "https://example.com/repo.git", "git", ref="v1.0.0"
        )

        mock_handler = MagicMock()
        mock_handler.__class__.__name__ = "GitSourceHandler"
        mock_handler.can_handle.return_value = True
        mock_handler.fetch.return_value = fake_fetched

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.parsers.SOURCE_HANDLERS", [mock_handler]),
        ):
            result = cli_runner.invoke(mod, ["update", "pinned-mod"])

        assert result.exit_code == 0
        mock_handler.fetch.assert_called_once()
        assert "v1.0.0" in str(mock_handler.fetch.call_args)

    def test_update_without_ref_still_works(self, cli_runner, tmp_path):
        """'lola mod update' works for a git module without a pinned ref."""
        from unittest.mock import MagicMock

        from lola.parsers import save_source_info

        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        mod_path = modules_dir / "unpinned-mod"
        mod_path.mkdir()
        save_source_info(mod_path, "https://example.com/repo.git", "git")

        fake_fetched = tmp_path / "fetched" / "unpinned-mod"
        fake_fetched.mkdir(parents=True)
        save_source_info(fake_fetched, "https://example.com/repo.git", "git")

        mock_handler = MagicMock()
        mock_handler.__class__.__name__ = "GitSourceHandler"
        mock_handler.can_handle.return_value = True
        mock_handler.fetch.return_value = fake_fetched

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.parsers.SOURCE_HANDLERS", [mock_handler]),
        ):
            result = cli_runner.invoke(mod, ["update", "unpinned-mod"])

        assert result.exit_code == 0
        mock_handler.fetch.assert_called_once()
        call_args = mock_handler.fetch.call_args
        ref_arg = call_args.kwargs.get("ref") if call_args.kwargs else None
        assert ref_arg is None


class TestModInitModuleSubdir:
    """Tests for mod init with module/ subdirectory structure."""

    def test_init_creates_module_subdirectory(self, cli_runner, tmp_path):
        """Init creates module/ subdirectory with skills, commands, agents."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(mod, ["init", "my-module", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "my-module", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "my-module", "--format", "lola"])

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
            result = cli_runner.invoke(mod, ["init", "--format", "lola"])

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
                [
                    "init",
                    "my-mod",
                    "-s",
                    "my-skill",
                    "-c",
                    "my-cmd",
                    "-g",
                    "my-agent",
                    "--format",
                    "lola",
                ],
            )

            assert result.exit_code == 0
            agents_md = (tmp_path / "my-mod" / "module" / "AGENTS.md").read_text()
            # Should use dot-separated notation
            assert "/my-cmd" in agents_md
            assert "@my-agent" in agents_md
        finally:
            os.chdir(original_dir)

    def test_init_minimal_flag_creates_empty_structure(self, cli_runner, tmp_path):
        """Init with --minimal creates only empty directories."""
        import os

        original_dir = os.getcwd()

        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                mod, ["init", "my-module", "--minimal", "--format", "lola"]
            )

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

            result = cli_runner.invoke(
                mod, ["init", "my-module", "--force", "--format", "lola"]
            )

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

            result = cli_runner.invoke(mod, ["init", "existing", "--format", "lola"])

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

    def test_rm_passes_scope_to_get_skill_path(self, cli_runner, tmp_path):
        """Test that mod rm passes the installation scope to get_skill_path."""
        from unittest.mock import MagicMock
        from lola.models import Installation, InstallationRegistry

        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        # Create a fake module
        module_dir = modules_dir / "test-module"
        module_dir.mkdir()
        skills_dir = module_dir / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: Test\n---\nContent")

        # Create installation record with USER scope
        registry = InstallationRegistry(installed_file)
        registry.add(
            Installation(
                module_name="test-module",
                assistant="opencode",
                scope="user",  # User scope - critical for this test
                project_path="/some/project",
                skills=["test-skill"],
            )
        )

        # Create mock target
        mock_target = MagicMock()
        mock_target.uses_managed_section = False
        mock_target.remove_skill.return_value = True

        # Run the command
        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.get_target", return_value=mock_target),
            patch("lola.cli.mod.ensure_lola_dirs"),
        ):
            result = cli_runner.invoke(mod, ["rm", "test-module", "-f"])

        # Assert the command succeeded
        assert result.exit_code == 0

        # CRITICAL: Verify get_skill_path was called with the correct scope
        mock_target.get_skill_path.assert_called_once_with("/some/project", "user")


class TestModRmInteractive:
    """Tests for mod rm interactive picker (no argument)."""

    def test_rm_no_arg_non_interactive(self, cli_runner, tmp_path):
        """Fail with error message in non-interactive mode."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=False),
        ):
            result = cli_runner.invoke(mod, ["rm"])

        assert result.exit_code == 1
        assert "non-interactive" in result.output

    def test_rm_no_arg_interactive_no_modules(self, cli_runner, tmp_path):
        """Print message and exit 0 when no modules registered."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
        ):
            result = cli_runner.invoke(mod, ["rm"])

        assert result.exit_code == 0
        assert "No modules" in result.output

    def test_rm_no_arg_interactive_picker_selects(
        self, cli_runner, sample_module, tmp_path
    ):
        """Picker selection leads to module removal."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
            patch("lola.cli.mod.select_module", return_value="sample-module"),
        ):
            result = cli_runner.invoke(mod, ["rm", "-f"])

        assert result.exit_code == 0
        assert "sample-module" in result.output
        assert not dest.exists()

    def test_rm_no_arg_interactive_picker_cancelled(
        self, cli_runner, sample_module, tmp_path
    ):
        """Cancelling the picker exits with code 130."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)
        installed_file = tmp_path / ".lola" / "installed.yml"

        dest = modules_dir / "sample-module"
        shutil.copytree(sample_module, dest)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.INSTALLED_FILE", installed_file),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
            patch("lola.cli.mod.select_module", return_value=None),
        ):
            result = cli_runner.invoke(mod, ["rm"])

        assert result.exit_code == 130
        assert "Cancelled" in result.output
        assert dest.exists()


class TestModInfoInteractive:
    """Tests for mod info interactive picker (no argument)."""

    def test_info_no_arg_non_interactive(self, cli_runner, tmp_path):
        """Fail with error message in non-interactive mode."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=False),
        ):
            result = cli_runner.invoke(mod, ["info"])

        assert result.exit_code == 1
        assert "non-interactive" in result.output

    def test_info_no_arg_interactive_no_modules(self, cli_runner, tmp_path):
        """Print message and exit 0 when no modules registered."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
        ):
            result = cli_runner.invoke(mod, ["info"])

        assert result.exit_code == 0
        assert "No modules" in result.output

    def test_info_no_arg_interactive_picker_selects(
        self, cli_runner, sample_module, tmp_path
    ):
        """Picker selection shows module info."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        shutil.copytree(sample_module, modules_dir / "sample-module")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
            patch("lola.cli.mod.select_module", return_value="sample-module"),
        ):
            result = cli_runner.invoke(mod, ["info"])

        assert result.exit_code == 0
        assert "sample-module" in result.output

    def test_info_no_arg_interactive_picker_cancelled(self, cli_runner, tmp_path):
        """Cancelling the picker exits with code 130."""
        modules_dir = tmp_path / ".lola" / "modules"
        modules_dir.mkdir(parents=True)

        shutil.copytree(
            tmp_path / "sample-module" if False else modules_dir,
            modules_dir,
            dirs_exist_ok=True,
        )

        # Put one module in the registry so the picker is shown
        fake_mod = modules_dir / "fake-mod"
        fake_mod.mkdir()
        skills_dir = fake_mod / "skills" / "s1"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("---\ndescription: d\n---\n")

        with (
            patch("lola.cli.mod.MODULES_DIR", modules_dir),
            patch("lola.cli.mod.ensure_lola_dirs"),
            patch("lola.cli.mod.is_interactive", return_value=True),
            patch("lola.cli.mod.select_module", return_value=None),
        ):
            result = cli_runner.invoke(mod, ["info"])

        assert result.exit_code == 130
        assert "Cancelled" in result.output
