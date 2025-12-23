# Data Model: Module Marketplace

**Feature**: 003-marketplace
**Date**: 2025-12-22
**Purpose**: Define data structures following existing Lola patterns

## Data Classes

Following the pattern from `src/lola/models.py`.

### Marketplace

Location: `src/lola/models.py` (extend existing file)

```python
@dataclass
class Marketplace:
    """Represents a marketplace catalog with modules"""
    name: str
    url: str
    enabled: bool = True
    description: str = ""
    version: str = ""
    modules: list[dict] = field(default_factory=list)

    @classmethod
    def from_reference(cls, ref_file: Path) -> "Marketplace":
        """Load marketplace from reference file"""
        with open(ref_file) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True)
        )

    @classmethod
    def from_cache(cls, cache_file: Path) -> "Marketplace":
        """Load marketplace from cache file"""
        with open(cache_file) as f:
            data = yaml.safe_load(f)
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            version=data.get("version", ""),
            modules=data.get("modules", [])
        )

    @classmethod
    def from_url(cls, url: str, name: str) -> "Marketplace":
        """Download and parse marketplace from URL"""
        from urllib.request import urlopen
        from urllib.error import URLError

        try:
            with urlopen(url, timeout=10) as response:
                data = yaml.safe_load(response.read())
        except URLError as e:
            raise ValueError(f"Failed to download marketplace: {e}")

        return cls(
            name=name,
            url=url,
            enabled=True,
            description=data.get("description", ""),
            version=data.get("version", ""),
            modules=data.get("modules", [])
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate marketplace structure"""
        errors = []

        if not self.name:
            errors.append("Missing required field: name")
        if not self.url:
            errors.append("Missing required field: url")

        if self.modules and not self.version:
            errors.append("Missing version for marketplace catalog")

        for i, mod in enumerate(self.modules):
            required = ["name", "description", "version", "repository"]
            for field in required:
                if field not in mod:
                    errors.append(f"Module {i}: missing '{field}'")

        return len(errors) == 0, errors

    def to_reference_dict(self) -> dict:
        """Convert to dict for reference file"""
        return {
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled
        }

    def to_cache_dict(self) -> dict:
        """Convert to dict for cache file"""
        return {
            "name": self.description or self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "enabled": self.enabled,
            "modules": self.modules
        }
```

---

### MarketplaceRegistry

Location: `src/lola/market/manager.py` (new file)

```python
from pathlib import Path
from rich.console import Console
from rich.table import Table
import yaml
from lola.models import Marketplace


class MarketplaceRegistry:
    """Manages marketplace references and caches"""

    def __init__(self, market_dir: Path, cache_dir: Path):
        """Initialize registry"""
        self.market_dir = market_dir
        self.cache_dir = cache_dir
        self.console = Console()

        self.market_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def add(self, name: str, url: str) -> None:
        """Add a new marketplace"""
        ref_file = self.market_dir / f"{name}.yml"

        if ref_file.exists():
            self.console.print(
                f"[yellow]Marketplace '{name}' already exists[/yellow]"
            )
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
                f"[green]Added marketplace '{name}' "
                f"with {module_count} modules[/green]"
            )
        except ValueError as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def remove(self, name: str) -> None:
        """Remove a marketplace"""
        ref_file = self.market_dir / f"{name}.yml"
        cache_file = self.cache_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(
                f"[yellow]Marketplace '{name}' not found[/yellow]"
            )
            return

        ref_file.unlink()
        if cache_file.exists():
            cache_file.unlink()

        self.console.print(f"[green]Removed marketplace '{name}'[/green]")

    def update(self, name: str = None) -> None:
        """Update marketplace cache(s)"""
        if name:
            self._update_one(name)
            return

        for ref_file in self.market_dir.glob("*.yml"):
            self._update_one(ref_file.stem)

    def _update_one(self, name: str) -> None:
        """Update a single marketplace cache"""
        ref_file = self.market_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(
                f"[yellow]Marketplace '{name}' not found[/yellow]"
            )
            return

        try:
            ref = Marketplace.from_reference(ref_file)
            marketplace = Marketplace.from_url(ref.url, name)
            marketplace.enabled = ref.enabled

            cache_file = self.cache_dir / f"{name}.yml"
            with open(cache_file, "w") as f:
                yaml.dump(marketplace.to_cache_dict(), f)

            module_count = len(marketplace.modules)
            self.console.print(
                f"[green]Updated '{name}' ({module_count} modules)[/green]"
            )
        except ValueError as e:
            self.console.print(f"[red]Failed to update '{name}': {e}[/red]")

    def enable(self, name: str) -> None:
        """Enable a marketplace"""
        self._set_enabled(name, True)

    def disable(self, name: str) -> None:
        """Disable a marketplace"""
        self._set_enabled(name, False)

    def _set_enabled(self, name: str, enabled: bool) -> None:
        """Set enabled status for marketplace"""
        ref_file = self.market_dir / f"{name}.yml"

        if not ref_file.exists():
            self.console.print(
                f"[yellow]Marketplace '{name}' not found[/yellow]"
            )
            return

        marketplace = Marketplace.from_reference(ref_file)
        marketplace.enabled = enabled

        with open(ref_file, "w") as f:
            yaml.dump(marketplace.to_reference_dict(), f)

        status = "enabled" if enabled else "disabled"
        self.console.print(f"[green]Marketplace '{name}' {status}[/green]")

    def list(self) -> None:
        """List all marketplaces (like dnf repolist)"""
        table = Table(title="Marketplaces")
        table.add_column("Marketplace", style="cyan")
        table.add_column("Status")
        table.add_column("Modules", justify="right")

        for ref_file in sorted(self.market_dir.glob("*.yml")):
            marketplace = Marketplace.from_reference(ref_file)
            name = ref_file.stem

            if marketplace.enabled:
                status = "[green]enabled[/green]"
            else:
                status = "[red]disabled[/red]"

            cache_file = self.cache_dir / f"{name}.yml"
            module_count = 0
            if cache_file.exists():
                cached = Marketplace.from_cache(cache_file)
                module_count = len(cached.modules)

            table.add_row(name, status, str(module_count))

        self.console.print(table)

    def search(self, query: str) -> list[dict]:
        """Search modules across enabled marketplaces"""
        results = []
        query_lower = query.lower()

        for ref_file in self.market_dir.glob("*.yml"):
            marketplace = Marketplace.from_reference(ref_file)
            if not marketplace.enabled:
                continue

            cache_file = self.cache_dir / f"{ref_file.stem}.yml"
            if not cache_file.exists():
                continue

            cached = Marketplace.from_cache(cache_file)
            market_name = ref_file.stem

            for mod in cached.modules:
                matches = (
                    query_lower in mod["name"].lower() or
                    query_lower in mod["description"].lower() or
                    any(query_lower in tag.lower()
                        for tag in mod.get("tags", []))
                )

                if matches:
                    results.append({
                        "name": mod["name"],
                        "description": mod["description"],
                        "version": mod["version"],
                        "marketplace": market_name,
                        "repository": mod["repository"]
                    })

        if results:
            self.console.print(f"\nResults for \"{query}\":\n")
            for r in results:
                self.console.print(
                    f"{r['name']} - {r['description']} - "
                    f"{r['marketplace']} - v{r['version']}"
                )
        else:
            self.console.print(
                f"[yellow]No results for \"{query}\"[/yellow]"
            )

        return results

    def find_module(self, module_name: str) -> dict | None:
        """Find a module by name in enabled marketplaces"""
        for ref_file in self.market_dir.glob("*.yml"):
            marketplace = Marketplace.from_reference(ref_file)
            if not marketplace.enabled:
                continue

            cache_file = self.cache_dir / f"{ref_file.stem}.yml"
            if not cache_file.exists():
                continue

            cached = Marketplace.from_cache(cache_file)
            for mod in cached.modules:
                if mod["name"] == module_name:
                    return {**mod, "marketplace": ref_file.stem}

        return None
```

---

## File Structure

### Reference File

`$LOLA_HOME/market/<name>.yml`:
```yaml
name: official
url: https://lola.dev/marketplace.yaml
enabled: true
```

### Cache File

`$LOLA_HOME/market/cache/<name>.yml`:
```yaml
name: Official Lola Marketplace
description: Curated modules from the Lola team
version: 1.0.0
url: https://lola.dev/marketplace.yaml
enabled: true
modules:
  - name: git-tools
    description: Git workflow automation tools
    version: 1.2.0
    repository: https://github.com/example/git-tools.git
    tags: [git, automation]
```

---

## Summary

**Follows models.py Pattern**:
- `@dataclass` decorator
- `@classmethod` constructors (`from_reference`, `from_cache`, `from_url`)
- `validate()` returns `tuple[bool, list[str]]`
- `to_*_dict()` methods for serialization
- Registry class for CRUD operations

**Clean & Readable**:
- Methods are focused but not overly fragmented
- Early returns to avoid deep nesting
- Rich console for dnf/yum-style output
- Clear method names and purposes
