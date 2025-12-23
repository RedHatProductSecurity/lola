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
