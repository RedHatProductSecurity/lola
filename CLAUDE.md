# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Lola

Lola is an AI Skills Package Manager that lets you write AI context/skills once and install them to multiple AI assistants (Claude Code, Cursor, Gemini CLI). Skills are portable modules with a SKILL.md file that get converted to each assistant's native format.

## Development Commands

```bash
# Install in development mode
uv pip install -e .

# Run tests
pytest                     # All tests
pytest tests/test_cli_mod.py  # Single test file
pytest -k test_add         # Tests matching pattern
pytest --cov=src/lola      # With coverage

# Run the CLI
lola --help
lola mod ls
lola install <module> -a claude-code
```

## Architecture

### Core Data Flow

1. **Module Registration**: `lola mod add <source>` fetches modules (from git, zip, tar, or folder) to `~/.lola/modules/`
2. **Installation**: `lola install <module>` copies modules to project's `.lola/modules/` and generates assistant-specific files:
   - Claude Code: `.claude/skills/<module>-<skill>/SKILL.md` (native format, no conversion)
   - Cursor: `.cursor/rules/<module>-<skill>.mdc` (converted with frontmatter rewrite)
   - Gemini CLI: `GEMINI.md` (entries appended to managed section between markers)
3. **Updates**: `lola update` regenerates assistant files from source modules

### Key Source Files

- `src/lola/main.py` - CLI entry point, registers all commands
- `src/lola/cli/mod.py` - Module management: add, rm, ls, info, init, update
- `src/lola/cli/install.py` - Install/uninstall commands, generates assistant-specific files
- `src/lola/models.py` - Data models: Module, Skill, Installation, InstallationRegistry
- `src/lola/config.py` - Paths and assistant configurations (LOLA_HOME, MODULES_DIR, ASSISTANTS dict)
- `src/lola/converters.py` - Skill format conversion (skill_to_cursor_mdc, parse_skill_frontmatter)
- `src/lola/command_converters.py` - Command format conversion (command_to_gemini for TOML)
- `src/lola/sources.py` - Source fetching (git clone, zip/tar extraction, folder copy)
- `src/lola/frontmatter.py` - YAML frontmatter parsing shared by converters

### Module Structure

Modules live in `~/.lola/modules/<name>/` with:
```
.lola/module.yml    # manifest with type: lola/module, version, skills list
<skill-name>/
  SKILL.md          # skill definition with YAML frontmatter (name, description)
  scripts/          # optional supporting files
```

### SKILL.md Format

Skills require YAML frontmatter with `description` field:
```markdown
---
name: skill-name
description: When to use this skill
---

# Skill content...
```

### Slash Commands

Modules can include slash commands in `commands/` directory. Each command is a markdown file with frontmatter:
- `$ARGUMENTS` - placeholder for all arguments as a single string
- `$1`, `$2`, etc. - positional argument placeholders

Commands are converted to assistant-native formats:
- Claude/Cursor: Markdown pass-through to `.claude/commands/` or `.cursor/commands/`
- Gemini: TOML format with `{{args}}` substitution to `.gemini/commands/`

### Installation Registry

`~/.lola/installed.yml` tracks all installations with module name, assistant, scope, project path, and installed skills.

### Assistant Scope Limitations

- Claude Code: supports both user and project scope
- Cursor: project scope only for skills (commands work in both scopes)
- Gemini CLI: project scope only for skills (commands work in both scopes)

### Testing Patterns

Tests use Click's `CliRunner` for CLI testing. Key fixtures in `tests/conftest.py`:
- `mock_lola_home` - patches LOLA_HOME and MODULES_DIR to temp directory
- `sample_module` - creates a complete test module with skill and command
- `registered_module` - sample_module copied into mock_lola_home
