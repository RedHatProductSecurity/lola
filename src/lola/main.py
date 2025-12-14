"""
main:
    Main CLI entry point for lola package manager
"""

import click
from rich.console import Console

from lola import __version__
from lola.cli.install import install_cmd, list_installed_cmd, uninstall_cmd, update_cmd
from lola.cli.mod import mod

console = Console()


def ver():
    """Show version."""
    console.print(f"lola {__version__}")


@click.group(invoke_without_command=True, no_args_is_help=True)
@click.option("-v", "--version", is_flag=True, help="Show version")
@click.pass_context
def main(ctx, version):
    """
    lola - AI Skills Package Manager

    Manage and install AI skills across different AI assistants
    like Claude Code, Cursor, and Gemini CLI.

    \b
    Quick start:
        lola mod add [git-url|folder|zip|tar]    Add a module
        lola mod ls                               List modules
        lola install [module] -a [assistant]     Install skills

    \b
    For more help on any command:
        lola [command] --help
    """
    ctx.ensure_object(dict)
    if version:
        ver()


# Register command groups
main.add_command(mod)

# Register top-level commands
main.add_command(install_cmd)
main.add_command(uninstall_cmd)
main.add_command(update_cmd)
main.add_command(list_installed_cmd)


if __name__ == "__main__":
    main()
