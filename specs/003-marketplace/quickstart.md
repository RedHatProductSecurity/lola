# Quickstart: Marketplace Feature

**Feature**: 003-marketplace
**For**: Developers implementing the marketplace feature
**Purpose**: Quick reference for understanding and implementing the marketplace
system

## Overview

The marketplace feature enables users to register, search, and install modules
from curated YAML-based marketplaces, similar to dnf/yum package repositories.

## Core Concepts

1. **Marketplace Reference**: Lightweight file at `$LOLA_HOME/market/<name>.yml`
   containing URL and enabled status
2. **Marketplace Cache**: Full catalog at
   `$LOLA_HOME/market/cache/<name>.yml` with module list
3. **Modules**: Entries in marketplace cache with name, description, version,
   and repository URL

## File Structure

```
$LOLA_HOME/market/
├── official.yml              # Reference: url + enabled status
├── community.yml             # Reference: url + enabled status
└── cache/
    ├── official.yml          # Cached catalog with modules
    └── community.yml         # Cached catalog with modules
```

## Implementation Files

### New Files to Create

```
src/lola/
├── market/
│   ├── __init__.py
│   └── manager.py            # MarketplaceRegistry class
├── cli/
│   └── market.py             # CLI commands
└── models.py                 # ADD: Marketplace dataclass

tests/
├── test_cli_market.py        # CLI command tests
└── test_market_manager.py    # MarketplaceRegistry tests
```

### Files to Modify

```
src/lola/
├── config.py                 # ADD: MARKET_DIR, CACHE_DIR
├── main.py                   # ADD: market command group
└── cli/install.py            # ADD: marketplace integration
```

## Key Classes

### Marketplace (dataclass)

```python
@dataclass
class Marketplace:
    name: str
    url: str
    enabled: bool = True
    description: str = ""
    version: str = ""
    modules: list[dict] = field(default_factory=list)

    @classmethod
    def from_reference(cls, ref_file: Path) -> "Marketplace"

    @classmethod
    def from_cache(cls, cache_file: Path) -> "Marketplace"

    @classmethod
    def from_url(cls, url: str, name: str) -> "Marketplace"

    def validate(self) -> tuple[bool, list[str]]
```

### MarketplaceRegistry

```python
class MarketplaceRegistry:
    def __init__(self, market_dir: Path, cache_dir: Path)
    def add(self, name: str, url: str) -> None
    def remove(self, name: str) -> None
    def update(self, name: str = None) -> None
    def enable(self, name: str) -> None
    def disable(self, name: str) -> None
    def list(self) -> None
    def search(self, query: str) -> list[dict]
    def find_module(self, module_name: str) -> dict | None
```

## CLI Commands

```bash
# Add marketplace
lola market add official https://lola.dev/marketplace.yaml

# List marketplaces
lola market ls

# Search for modules
lola search authentication

# Update marketplace cache
lola market update official
lola market update --all

# Enable/disable marketplace
lola market enable official
lola market disable community

# Remove marketplace
lola market rm testing

# Install module from marketplace
lola install git-tools -a claude-code
```

## Development Workflow

### Phase 1: Core Infrastructure (Commit 1)

**Files**: `src/lola/config.py`, `src/lola/models.py`

1. Add to `config.py`:
   ```python
   MARKET_DIR = LOLA_HOME / "market"
   CACHE_DIR = MARKET_DIR / "cache"
   ```

2. Add `Marketplace` dataclass to `models.py`

**Test**: Create `tests/test_marketplace_model.py`
- Test `from_reference()`, `from_cache()`, `from_url()`
- Test `validate()` with various YAML structures

### Phase 2: Registry Class (Commit 2)

**Files**: `src/lola/market/manager.py`

1. Create `MarketplaceRegistry` class
2. Implement `add()` and `remove()` methods
3. Implement file I/O for reference and cache

**Test**: `tests/test_market_manager.py`
- Test add/remove with mocked HTTP downloads
- Test file creation and deletion

### Phase 3: List & Search (Commit 3)

**Files**: `src/lola/market/manager.py`

1. Implement `list()` with Rich table
2. Implement `search()` with query matching
3. Implement `find_module()` for lookups

**Test**: Update `tests/test_market_manager.py`
- Test list with multiple marketplaces
- Test search with various queries
- Test enabled/disabled filtering

### Phase 4: Update & Enable/Disable (Commit 4)

**Files**: `src/lola/market/manager.py`

1. Implement `update()` for cache refresh
2. Implement `enable()` and `disable()`

**Test**: Update `tests/test_market_manager.py`
- Test update with network mocking
- Test enable/disable toggling

### Phase 5: CLI Commands (Commit 5)

**Files**: `src/lola/cli/market.py`, `src/lola/main.py`

1. Create CLI command group with click
2. Wire up all commands to registry methods
3. Register in `main.py`

**Test**: `tests/test_cli_market.py`
- Use CliRunner for each command
- Test error scenarios

### Phase 6: Install Integration (Commit 6)

**Files**: `src/lola/cli/install.py`

1. Check marketplace if module not found locally
2. Auto-add module using repository URL
3. Continue with normal install flow

**Test**: Update `tests/test_cli_install.py`
- Test marketplace module resolution
- Test fallback to marketplace search

## Testing Strategy

### Unit Tests

```python
# tests/test_marketplace_model.py
def test_marketplace_from_reference()
def test_marketplace_from_cache()
def test_marketplace_from_url()
def test_marketplace_validate()

# tests/test_market_manager.py
def test_registry_add()
def test_registry_remove()
def test_registry_list()
def test_registry_search()
def test_registry_update()
def test_registry_enable_disable()
```

### Integration Tests

```python
# tests/test_cli_market.py
def test_market_add_command()
def test_market_ls_command()
def test_market_search_command()
def test_market_update_command()
def test_market_enable_disable_command()
def test_market_rm_command()
```

## Marketplace YAML Example

```yaml
name: Official Lola Marketplace
description: Curated modules from the Lola team
version: 1.0.0
modules:
  - name: git-tools
    description: Git workflow automation tools
    version: 1.2.0
    repository: https://github.com/example/git-tools.git
    tags: [git, automation, workflow]

  - name: code-review
    description: Code review assistance
    version: 2.0.1
    repository: https://github.com/example/code-review.git
    tags: [review, quality]
```

## Common Patterns

### Loading Marketplaces

```python
# Load reference
marketplace = Marketplace.from_reference(ref_file)

# Load cache
marketplace = Marketplace.from_cache(cache_file)

# Download new
marketplace = Marketplace.from_url(url, name)
```

### Rich Console Output

```python
from rich.console import Console
from rich.table import Table

console = Console()
table = Table(title="Marketplaces")
table.add_column("Name", style="cyan")
table.add_row("official", "[green]enabled[/green]")
console.print(table)
```

### Error Handling

```python
try:
    marketplace = Marketplace.from_url(url, name)
    is_valid, errors = marketplace.validate()
    if not is_valid:
        console.print("[red]Validation failed:[/red]")
        for err in errors:
            console.print(f"  - {err}")
except ValueError as e:
    console.print(f"[red]Error: {e}[/red]")
```

## Performance Considerations

- Search loads all enabled marketplace caches into memory
- Expected: 5-10 marketplaces × 50-100 modules each = 250-1000 modules
- YAML parsing: ~1-5ms per file
- Total search time: < 100ms (well under 2s requirement)

## Dependencies

- **urllib**: HTTP downloads (stdlib, no new dependency)
- **pyyaml**: YAML parsing (already in pyproject.toml)
- **rich**: Console output (already in pyproject.toml)
- **click**: CLI framework (already in pyproject.toml)
