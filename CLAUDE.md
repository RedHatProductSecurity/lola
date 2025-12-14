# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Lola

Lola is an AI Skills Package Manager that lets you write AI context/skills once and install them to multiple AI assistants (Claude Code, Cursor, Gemini CLI, OpenCode). Skills are portable modules with a SKILL.md file that get converted to each assistant's native format.

## Development Commands

```bash
# Install in development mode
uv pip install -e .

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

### Key Source Files

- `src/lola/main.py` - CLI entry point, registers all commands
- `src/lola/cli/mod.py` - Module management: add, rm, ls, info, init, update
- `src/lola/cli/install.py` - Install/uninstall/update commands
- `src/lola/models.py` - Data models: Module, Skill, Command, Agent, Installation, InstallationRegistry
- `src/lola/config.py` - Global paths (LOLA_HOME, MODULES_DIR, INSTALLED_FILE)
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

### Target Assistants

Defined in `targets.py` ASSISTANTS dict. Each assistant has different output formats:

| Assistant | Skills | Commands | Agents |
|-----------|--------|----------|--------|
| claude-code | `.claude/skills/<module>-<skill>/SKILL.md` | `.claude/commands/<module>-<cmd>.md` | `.claude/agents/<module>-<agent>.md` |
| cursor | `.cursor/rules/<module>-<skill>.mdc` | `.cursor/commands/<module>-<cmd>.md` | `.cursor/agents/<module>-<agent>.md` |
| gemini-cli | `GEMINI.md` (managed section) | `.gemini/commands/<module>-<cmd>.toml` | N/A |
| opencode | `.opencode/skills/<module>-<skill>.md` | `.opencode/commands/<module>-<cmd>.md` | `.opencode/agents/<module>-<agent>.md` |

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
