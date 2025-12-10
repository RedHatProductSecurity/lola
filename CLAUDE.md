# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Lola

Lola is an AI Skills Package Manager that lets you write AI context/skills once and install them to multiple AI assistants (Claude Code, Cursor, Gemini CLI). Skills are portable modules with a SKILL.md file that get converted to each assistant's native format.

## Development Commands

```bash
# Install in development mode
uv pip install -e .

# Run the CLI
lola --help
lola mod ls
lola install <module> -a claude-code
```

## Architecture

### Core Data Flow

1. **Module Registration**: `lola mod add <source>` fetches modules (from git, zip, tar, or folder) to `~/.lola/modules/`
2. **Installation**: `lola install <module>` copies modules to project's `.lola/modules/` and generates assistant-specific files:
   - Claude Code: `.claude/skills/<skill>/SKILL.md` (native format, no conversion)
   - Cursor: `.cursor/rules/<skill>.mdc` (converted with frontmatter rewrite)
   - Gemini CLI: `GEMINI.md` (entries appended to managed section between markers)
3. **Updates**: `lola update` regenerates assistant files from source modules

### Key Source Files

- `src/lola/main.py` - CLI entry point, registers all commands
- `src/lola/mod.py` - Module management: add, rm, ls, info, init, update
- `src/lola/install.py` - Install/uninstall commands, generates assistant-specific files
- `src/lola/models.py` - Data models: Module, Skill, Installation, InstallationRegistry
- `src/lola/config.py` - Paths and assistant configurations (LOLA_HOME, MODULES_DIR, ASSISTANTS dict)
- `src/lola/converters.py` - Format conversion (skill_to_cursor_mdc, parse_skill_frontmatter)
- `src/lola/sources.py` - Source fetching (git clone, zip/tar extraction, folder copy)

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

### Installation Registry

`~/.lola/installed.yml` tracks all installations with module name, assistant, scope, project path, and installed skills.

### Assistant Scope Limitations

- Claude Code: supports both user and project scope
- Cursor: project scope only (user rules not supported)
- Gemini CLI: project scope only (can only read files within workspace)
