# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## What is Lola

Lola is an AI Skills Package Manager that lets you write AI context/skills once and install them to multiple AI assistants (Claude Code, Cursor, Gemini CLI, OpenCode, etc.). Skills are portable modules with a SKILL.md file that get converted to each assistant's native format.

## Development Commands

Remember to source the virtual environment before running commands:
```bash
source .venv/bin/activate
```

```bash
# Install in development mode with dev dependencies
uv sync --group dev

# Run tests
pytest                        # All tests
pytest tests/test_cli_mod.py  # Single test file
pytest -k test_add            # Tests matching pattern
pytest --cov=src/lola         # With coverage

# Run linting and type checking
ruff check src tests
basedpyright src

# Run the CLI
lola --help
lola mod ls
lola install <module> -a claude-code
```

## Architecture

### Core Data Flow

1. **Module Registration**: `lola mod add <source>` fetches modules (from git, zip, tar, or folder) to `~/.lola/modules/`
2. **Installation**: `lola install <module>` copies modules to project's `.lola/modules/` and generates assistant-specific files
3. **Updates**: `lola update` regenerates assistant files from source modules
4. **Marketplace Registration**: `lola market add <name> <url>` fetches marketplace catalogs to `~/.lola/market/` (reference) and `~/.lola/market/cache/` (full catalog)
5. **Module Discovery**: `lola mod search <query>` searches across enabled marketplace caches; `lola install <module>` auto-adds from marketplace if not in registry

### Key Source Files

- `src/lola/main.py` - CLI entry point, registers all commands
- `src/lola/cli/mod.py` - Module management: add, rm, ls, info, init, update, search
- `src/lola/cli/install.py` - Install/uninstall/update commands (with marketplace integration)
- `src/lola/cli/market.py` - Marketplace management: add, ls, update, set (enable/disable), rm
- `src/lola/models.py` - Data models: Module, Skill, Command, Agent, Installation, InstallationRegistry, Marketplace
- `src/lola/market/manager.py` - MarketplaceRegistry class for marketplace operations
- `src/lola/market/search.py` - Search functionality across marketplace caches
- `src/lola/config.py` - Global paths (LOLA_HOME, MODULES_DIR, INSTALLED_FILE, MARKET_DIR, CACHE_DIR)
- `src/lola/targets.py` - Assistant definitions and file generators (ASSISTANTS dict, generate_* functions)
- `src/lola/parsers.py` - Source fetching (SourceHandler classes) and skill/command parsing
- `src/lola/frontmatter.py` - YAML frontmatter parsing

### Module Structure

Modules use auto-discovery. Skills, commands, and agents are discovered from directory structure:

```
my-module/
  skills/              # Skills directory (required for skills)
    skill-name/
      SKILL.md         # Required: skill definition with frontmatter
      scripts/         # Optional: supporting files
  commands/            # Slash commands (*.md files)
  agents/              # Subagents (*.md files)
```

### Marketplace Structure

Marketplaces are YAML files with module catalogs:

```yaml
name: Marketplace Name
description: Description of the marketplace
version: 1.0.0
modules:
  - name: module-name
    description: Module description
    version: 1.0.0
    repository: https://github.com/user/repo.git
    tags: [tag1, tag2]
```

**Storage locations:**
- **Reference files**: `~/.lola/market/<name>.yml` - Contains source URL and enabled status
- **Cache files**: `~/.lola/market/cache/<name>.yml` - Full marketplace catalog

**Key operations:**
- `MarketplaceRegistry.add(name, url)` - Downloads and validates marketplace, saves reference and cache
- `MarketplaceRegistry.search_module_all(name)` - Finds module across all enabled marketplaces
- `MarketplaceRegistry.select_marketplace(name, matches)` - Prompts user when module exists in multiple marketplaces
- `MarketplaceRegistry.update(name)` - Re-fetches marketplace from source URL
- Cache recovery: Automatically re-downloads from source URL if cache is missing

### Target Assistants

Defined in `targets.py` TARGETS dict. Each assistant has different output formats:

| Assistant | Skills | Commands | Agents |
|-----------|--------|----------|--------|
| claude-code | `.claude/skills/<module>-<skill>/SKILL.md` | `.claude/commands/<module>-<cmd>.md` | `.claude/agents/<module>-<agent>.md` |
| cursor | `.cursor/rules/<module>-<skill>.mdc` | `.cursor/commands/<module>-<cmd>.md` | N/A |
| gemini-cli | `GEMINI.md` (managed section) | `.gemini/commands/<module>-<cmd>.toml` | N/A |
| opencode | `AGENTS.md` (managed section) | `.opencode/commands/<module>-<cmd>.md` | `.opencode/agent/<module>-<agent>.md` |

Agent frontmatter is modified during generation:
- Claude Code: `model: inherit` is added
- OpenCode: `mode: subagent` is added

### Source Handlers

`parsers.py` uses strategy pattern for fetching modules:
- `GitSourceHandler` - git clone with depth 1
- `ZipSourceHandler` / `ZipUrlSourceHandler` - local/remote zip files
- `TarSourceHandler` / `TarUrlSourceHandler` - local/remote tar archives
- `FolderSourceHandler` - local directory copy

### Testing Patterns

Tests use Click's `CliRunner` for CLI testing. Key fixtures in `tests/conftest.py`:
- `mock_lola_home` - patches LOLA_HOME, MODULES_DIR, INSTALLED_FILE to temp directory
- `sample_module` - creates test module with skill, command, and agent
- `registered_module` - sample_module copied into mock_lola_home
- `mock_assistant_paths` - creates mock assistant output directories
- `marketplace_with_modules` - creates marketplace with test modules
- `marketplace_disabled` - creates disabled marketplace for testing

**Marketplace testing patterns:**
- HTTP requests are mocked using `unittest.mock.patch` with `urllib.request.urlopen`
- Marketplace YAML validation uses actual `Marketplace` model validation
- Tests verify both reference and cache files are created correctly
- Cache recovery is tested with missing cache files
- Multi-marketplace conflicts tested with multiple marketplace fixtures
