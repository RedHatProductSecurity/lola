"""
UI utilities for consistent CLI output.

Provides icons, styling helpers, and output functions for a polished CLI experience.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

# Shared console instance
console = Console(soft_wrap=True, legacy_windows=False)

# Icons/symbols for consistent visual language
class Icons:
    """Unicode symbols for CLI output."""
    # Status
    SUCCESS = "✓"
    ERROR = "✗"
    WARNING = "!"
    INFO = "•"
    SKIP = "○"

    # Objects
    MODULE = "◆"
    SKILL = "→"
    COMMAND = "/"
    FOLDER = "📁"

    # Actions
    ADD = "+"
    REMOVE = "-"
    UPDATE = "↻"
    INSTALL = "↓"

    # Structure
    ARROW = "→"
    BULLET = "•"
    INDENT = "  "


def success(message: str, prefix: bool = True) -> None:
    """Print a success message."""
    icon = f"[green]{Icons.SUCCESS}[/green] " if prefix else ""
    console.print(f"{icon}[green]{message}[/green]")


def error(message: str, prefix: bool = True) -> None:
    """Print an error message."""
    icon = f"[red]{Icons.ERROR}[/red] " if prefix else ""
    console.print(f"{icon}[red]{message}[/red]")


def warning(message: str, prefix: bool = True) -> None:
    """Print a warning message."""
    icon = f"[yellow]{Icons.WARNING}[/yellow] " if prefix else ""
    console.print(f"{icon}[yellow]{message}[/yellow]")


def info(message: str, prefix: bool = True) -> None:
    """Print an info message."""
    icon = f"[blue]{Icons.INFO}[/blue] " if prefix else ""
    console.print(f"{icon}{message}")


def dim(message: str) -> None:
    """Print dimmed/secondary text."""
    console.print(f"[dim]{message}[/dim]")


def header(title: str) -> None:
    """Print a section header."""
    console.print(f"\n[bold]{title}[/bold]")


def subheader(title: str) -> None:
    """Print a subsection header."""
    console.print(f"[bold]{title}[/bold]")


def module_name(name: str, version: str = None) -> str:
    """Format a module name with optional version."""
    if version:
        return f"[cyan]{name}[/cyan] [dim]v{version}[/dim]"
    return f"[cyan]{name}[/cyan]"


def skill_name(name: str, ok: bool = True) -> str:
    """Format a skill name."""
    color = "green" if ok else "red"
    return f"[{color}]{name}[/{color}]"


def command_name(name: str, ok: bool = True) -> str:
    """Format a command name (with leading slash)."""
    color = "green" if ok else "red"
    return f"[{color}]/{name}[/{color}]"


def path(p: str) -> str:
    """Format a file path."""
    return f"[dim]{p}[/dim]"


def item(text: str, indent: int = 1) -> None:
    """Print a list item with bullet."""
    prefix = Icons.INDENT * indent
    console.print(f"{prefix}{Icons.BULLET} {text}")


def item_result(name: str, ok: bool, indent: int = 1, note: str = None) -> None:
    """Print an item with success/failure indicator."""
    prefix = Icons.INDENT * indent
    icon = f"[green]{Icons.SUCCESS}[/green]" if ok else f"[red]{Icons.ERROR}[/red]"
    color = "green" if ok else "red"
    msg = f"{prefix}{icon} [{color}]{name}[/{color}]"
    if note:
        msg += f" [dim]({note})[/dim]"
    console.print(msg)


def kv(key: str, value: str, indent: int = 1) -> None:
    """Print a key-value pair."""
    prefix = Icons.INDENT * indent
    console.print(f"{prefix}[dim]{key}:[/dim] {value}")


def blank() -> None:
    """Print a blank line."""
    console.print()


def hint(message: str) -> None:
    """Print a helpful hint."""
    console.print(f"[dim]{Icons.ARROW} {message}[/dim]")


def next_steps(steps: list[str]) -> None:
    """Print a list of suggested next steps."""
    console.print()
    console.print("[bold]Next steps:[/bold]")
    for i, step in enumerate(steps, 1):
        console.print(f"  {i}. {step}")


def assistant_header(name: str, target: str) -> None:
    """Print an assistant installation header."""
    console.print(f"  [bold]{name}[/bold] {Icons.ARROW} {path(str(target))}")


def assistant_summary(assistant: str, skills: list[str] = None, commands: list[str] = None, skill_dest: str = None, command_dest: str = None, skipped_reason: str = None) -> None:
    """Print a compact summary for an assistant installation."""
    if skipped_reason:
        console.print(f"  [bold]{assistant}[/bold] [yellow]skipped[/yellow] [dim]({skipped_reason})[/dim]")
        return

    parts = []
    if skills:
        parts.append(f"{len(skills)} skill{'s' if len(skills) != 1 else ''}")
    if commands:
        parts.append(f"{len(commands)} command{'s' if len(commands) != 1 else ''}")

    if parts:
        summary = ", ".join(parts)
        console.print(f"  [green]{Icons.SUCCESS}[/green] [bold]{assistant}[/bold] [dim]({summary})[/dim]")


def count_summary(items: str, count: int) -> str:
    """Format a count summary (e.g., '3 skills')."""
    return f"{count} {items}" if count != 1 else f"{count} {items.rstrip('s')}"


def module_tree(name: str, skills: list[str] = None, commands: list[str] = None) -> None:
    """Print a module structure as a tree."""
    tree = Tree(f"[cyan]{name}/[/cyan]")

    if skills:
        for skill in skills:
            skill_node = tree.add(f"[green]{skill}/[/green]")
            skill_node.add("[dim]SKILL.md[/dim]")

    if commands:
        cmd_node = tree.add("[dim]commands/[/dim]")
        for cmd in commands:
            cmd_node.add(f"[dim]{cmd}.md[/dim]")

    console.print(tree)
