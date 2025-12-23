"""
market.manager:
    Marketplace registry management for adding, updating, and managing
    marketplace catalogs
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
import yaml

from lola.models import Marketplace
from lola.market.search import search_market, display_market
from lola.exceptions import MarketplaceNameError


def parse_market_ref(module_name: str) -> tuple[str, str] | None:
    """
    Parse marketplace reference from module name.

    Args:
        module_name: Module name with marketplace prefix (@marketplace/module)

    Returns:
        Tuple of (marketplace_name, module_name) if valid, None otherwise
    """
    if module_name.startswith("@") and "/" in module_name:
        parts = module_name[1:].split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
    return None


def validate_marketplace_name(name: str) -> str:
    """Validate marketplace name to ensure it's a valid filesystem name.

    Raises:
        MarketplaceNameError: If the name is invalid.

    Returns:
        The validated name.
    """
    if not name:
        raise MarketplaceNameError(name, "name cannot be empty")
    if name in (".", ".."):
        raise MarketplaceNameError(name, "path traversal not allowed")
    if "/" in name or "\\" in name:
        raise MarketplaceNameError(name, "path separators not allowed")
    if name.startswith("."):
        raise MarketplaceNameError(name, "cannot start with dot")

    return name


class MarketplaceRegistry:
    """Manages marketplace references and caches."""

    def __init__(self, market_dir: Path, cache_dir: Path):
        """Initialize registry."""
        self.market_dir = market_dir
        self.cache_dir = cache_dir
        self.console = Console()

        self.market_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def add(self, name: str, url: str) -> None:
        """Add a new marketplace."""
        try:
            name = validate_marketplace_name(name)
        except MarketplaceNameError as e:
            self.console.print(f"[red]{e}[/red]")
            return

        ref_file = self.market_dir / f"{name}.yml"

        if ref_file.exists():
            self.console.print(f"[yellow]Marketplace '{name}' already exists[/yellow]")
            return

        try:
            marketplace = Marketplace.from_url(url, name)
            is_valid, errors = marketplace.validate()

            if not is_valid:
                self.console.print("[red]Validation failed:[/red]")
                for err in errors:
                    self.console.print(f"  - {err}")
                return

            # Save reference
            with open(ref_file, "w") as f:
                yaml.dump(marketplace.to_reference_dict(), f)

            # Save cache
            cache_file = self.cache_dir / f"{name}.yml"
            with open(cache_file, "w") as f:
                yaml.dump(marketplace.to_cache_dict(), f)

            module_count = len(marketplace.modules)
            self.console.print(
                f"[green]Added marketplace '{name}' with {module_count} modules[/green]"
            )
        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def search_module(self, module_name: str) -> tuple[dict, str] | None:
        """
        Search for a module by name across all enabled marketplaces.

        Args:
            module_name: Name of the module to search for

        Returns:
            Tuple of (module_dict, marketplace_name) if found, None otherwise
        """
        # Iterate through all marketplace reference files
        for ref_file in self.market_dir.glob("*.yml"):
            # Load reference to check if marketplace is enabled
            marketplace_ref = Marketplace.from_reference(ref_file)

            if not marketplace_ref.enabled:
                continue

            # Load cache to get modules
            cache_file = self.cache_dir / ref_file.name
            if not cache_file.exists():
                continue

            marketplace = Marketplace.from_cache(cache_file)

            # Search for module in this marketplace
            for module in marketplace.modules:
                if module.get("name") == module_name:
                    return module, marketplace_ref.name

        return None

    def search_module_all(self, module_name: str) -> list[tuple[dict, str]]:
        """
        Search for a module by name across all enabled marketplaces.

        Returns all matches, not just the first one.

        Args:
            module_name: Name of the module to search for

        Returns:
            List of tuples (module_dict, marketplace_name)
        """
        matches = []

        for ref_file in self.market_dir.glob("*.yml"):
            marketplace_ref = Marketplace.from_reference(ref_file)

            if not marketplace_ref.enabled:
                continue

            cache_file = self.cache_dir / ref_file.name
            if not cache_file.exists():
                continue

            marketplace = Marketplace.from_cache(cache_file)

            for module in marketplace.modules:
                if module.get("name") == module_name:
                    matches.append((module, marketplace_ref.name))

        return matches

    def select_marketplace(
        self,
        module_name: str,
        matches: list[tuple[dict, str]],
        show_version: bool = True,
    ) -> str | None:
        """
        Prompt user to select a marketplace when multiple matches exist.

        Args:
            module_name: Name of the module
            matches: List of (module_dict, marketplace_name) tuples
            show_version: Whether to display version in the options

        Returns:
            Selected marketplace name, or None if cancelled
        """
        import click

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0][1]

        self.console.print(
            f"[yellow]Module '{module_name}' found in multiple marketplaces:[/yellow]"
        )
        self.console.print()

        for idx, (module, marketplace_name) in enumerate(matches, 1):
            version = module.get("version", "")
            description = module.get("description", "")

            display = f"@{marketplace_name}/{module_name} - {description}"
            if show_version and version:
                display = f"@{marketplace_name}/{module_name}:{version} - {description}"

            self.console.print(f"  {idx}. {display}")

        self.console.print()

        choice = click.prompt(
            "Select marketplace",
            type=click.IntRange(1, len(matches)),
            default=1,
        )

        return matches[choice - 1][1]

    def search(self, query: str) -> None:
        """Search for modules across all enabled marketplaces."""
        ref_files = list(self.market_dir.glob("*.yml"))

        if not ref_files:
            self.console.print("[yellow]No marketplaces registered[/yellow]")
            self.console.print(
                "[dim]Use 'lola market add <name> <url>' to add a marketplace[/dim]"
            )
            return

        results = search_market(query, self.market_dir, self.cache_dir)
        display_market(results, query, self.console)

    def list(self) -> None:
        """List all registered marketplaces."""
        ref_files = list(self.market_dir.glob("*.yml"))

        if not ref_files:
            self.console.print("[yellow]No marketplaces registered[/yellow]")
            self.console.print(
                "[dim]Use 'lola market add <name> <url>' to add a marketplace[/dim]"
            )
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("Name")
        table.add_column("Modules", justify="right")
        table.add_column("Status")

        for ref_file in sorted(ref_files):
            marketplace_ref = Marketplace.from_reference(ref_file)

            cache_file = self.cache_dir / ref_file.name
            module_count = 0
            if cache_file.exists():
                marketplace = Marketplace.from_cache(cache_file)
                module_count = len(marketplace.modules)

            status = "[red]disabled[/red]"
            if marketplace_ref.enabled:
                status = "[green]enabled[/green]"

            table.add_row(marketplace_ref.name, str(module_count), status)

        self.console.print(table)

    def _set_enabled(self, name: str, enabled: bool) -> None:
        """Set marketplace enabled status."""
        ref_file = self.market_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(f"[red]Marketplace '{name}' not found[/red]")
            return

        marketplace_ref = Marketplace.from_reference(ref_file)
        marketplace_ref.enabled = enabled

        with open(ref_file, "w") as f:
            yaml.dump(marketplace_ref.to_reference_dict(), f)

        status = "enabled" if enabled else "disabled"
        self.console.print(f"[green]Marketplace '{name}' {status}[/green]")

    def enable(self, name: str) -> None:
        """Enable a marketplace."""
        self._set_enabled(name, True)

    def disable(self, name: str) -> None:
        """Disable a marketplace."""
        self._set_enabled(name, False)

    def remove(self, name: str) -> None:
        """Remove a marketplace."""
        ref_file = self.market_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(f"[red]Marketplace '{name}' not found[/red]")
            return

        cache_file = self.cache_dir / f"{name}.yml"

        ref_file.unlink()
        if cache_file.exists():
            cache_file.unlink()

        self.console.print(f"[green]Removed marketplace '{name}'[/green]")

    def update_one(self, name: str) -> bool:
        """Update cache for a single marketplace."""
        ref_file = self.market_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(f"[red]Marketplace '{name}' not found[/red]")
            return False

        marketplace_ref = Marketplace.from_reference(ref_file)

        try:
            marketplace = Marketplace.from_url(marketplace_ref.url, name)
            is_valid, errors = marketplace.validate()

            if not is_valid:
                self.console.print(f"[red]Validation failed for '{name}':[/red]")
                for err in errors:
                    self.console.print(f"  - {err}")
                return False

            cache_file = self.cache_dir / f"{name}.yml"
            with open(cache_file, "w") as f:
                yaml.dump(marketplace.to_cache_dict(), f)

            module_count = len(marketplace.modules)
            self.console.print(
                f"[green]Updated '{name}' with {module_count} modules[/green]"
            )
            return True
        except ValueError as e:
            self.console.print(f"[red]Failed to update '{name}': {e}[/red]")
            return False

    def update(self, name: str | None = None) -> None:
        """Update marketplace cache(s)."""
        if name:
            self.update_one(name)
            return

        ref_files = list(self.market_dir.glob("*.yml"))
        if not ref_files:
            self.console.print("[yellow]No marketplaces registered[/yellow]")
            return

        success_count = 0
        for ref_file in sorted(ref_files):
            marketplace_ref = Marketplace.from_reference(ref_file)
            if self.update_one(marketplace_ref.name):
                success_count += 1

        total = len(ref_files)
        self.console.print(
            f"[green]Updated {success_count}/{total} marketplaces[/green]"
        )
