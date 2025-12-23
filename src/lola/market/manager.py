"""
market.manager:
    Marketplace registry management for adding, updating, and managing
    marketplace catalogs
"""

from pathlib import Path
from rich.console import Console
import yaml

from lola.models import Marketplace


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
