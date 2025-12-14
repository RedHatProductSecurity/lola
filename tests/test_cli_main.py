"""Tests for the main CLI entry point."""

from lola.main import main
from lola import __version__


class TestMainCli:
    """Tests for the main CLI group."""

    def test_help(self, cli_runner):
        """Show help text."""
        result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "lola - AI Skills Package Manager" in result.output
        assert "Quick start" in result.output

    def test_no_args_shows_help(self, cli_runner):
        """Show help when no arguments provided."""
        result = cli_runner.invoke(main, [])
        # no_args_is_help=True causes exit code 0 with help output
        assert "lola - AI Skills Package Manager" in result.output

    def test_version_flag(self, cli_runner):
        """Show version with -v flag."""
        result = cli_runner.invoke(main, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_long_flag(self, cli_runner):
        """Show version with --version flag."""
        result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestMainSubcommands:
    """Tests for main CLI subcommands."""

    def test_mod_subcommand_help(self, cli_runner):
        """Show mod subcommand help."""
        result = cli_runner.invoke(main, ["mod", "--help"])
        assert result.exit_code == 0
        assert "Manage lola modules" in result.output

    def test_install_subcommand_help(self, cli_runner):
        """Show install subcommand help."""
        result = cli_runner.invoke(main, ["install", "--help"])
        assert result.exit_code == 0
        assert "Install a module" in result.output

    def test_uninstall_subcommand_help(self, cli_runner):
        """Show uninstall subcommand help."""
        result = cli_runner.invoke(main, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Uninstall a module" in result.output

    def test_update_subcommand_help(self, cli_runner):
        """Show update subcommand help."""
        result = cli_runner.invoke(main, ["update", "--help"])
        assert result.exit_code == 0
        assert "Regenerate assistant files" in result.output

    def test_list_subcommand_help(self, cli_runner):
        """Show list subcommand help."""
        result = cli_runner.invoke(main, ["list", "--help"])
        assert result.exit_code == 0
        assert "List all installed modules" in result.output

    def test_invalid_subcommand(self, cli_runner):
        """Show error for invalid subcommand."""
        result = cli_runner.invoke(main, ["nonexistent"])
        assert result.exit_code != 0
        assert "No such command" in result.output
