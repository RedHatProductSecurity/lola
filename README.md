# Lola - AI Skills Package Manager

**Write your AI context once, use it everywhere.**

Every AI tool wants its own prompt format. Claude Code uses `SKILL.md`. Cursor uses `.mdc` rules. Gemini CLI uses `GEMINI.md`. Slash commands? Different syntax for each. You end up maintaining the same instructions in three different places—or worse, giving up and only using one tool.

Lola fixes this. Write your skills and commands once as portable modules, then install them everywhere with a single command.

[![asciicast](https://asciinema.org/a/UsbI8adasbdAhAFQuiXj70eVp.svg)](https://asciinema.org/a/UsbI8adasbdAhAFQuiXj70eVp)

## Supported AI Assistants

| Assistant | Skills | Commands | Scope |
|-----------|--------|----------|-------|
| Claude Code | `.claude/skills/<module>-<skill>/SKILL.md` | `.claude/commands/<module>-<cmd>.md` | user, project |
| Cursor | `.cursor/rules/<module>-<skill>.mdc` | `.cursor/commands/<module>-<cmd>.md` | skills: project only, commands: user, project |
| Gemini CLI | `GEMINI.md` | `.gemini/commands/<module>-<cmd>.toml` | skills: project only, commands: user, project |

> **Note:** Cursor and Gemini CLI skills require project-scope installs. Commands work in both scopes for all assistants.

## Installation

```bash
# With uv (recommended)
uv tool install git+https://github.com/seckatie/lola

# Or clone and install locally
git clone https://github.com/seckatie/lola
cd lola
uv tool install .
```

## Quick Start

### 1. Add a module

```bash
# From a git repository
lola mod add https://github.com/user/my-skills.git

# From a local folder
lola mod add ./my-local-skills

# From a zip or tar file
lola mod add ~/Downloads/skills.zip
```

### 2. Install skills to your AI assistants

```bash
# Install to all assistants (user scope)
lola install my-skills

# Install to a specific assistant
lola install my-skills -a claude-code

# Install to a specific project
lola install my-skills -s project ./my-project
```

### 3. List and manage

```bash
# List modules in registry
lola mod ls

# List installed modules
lola installed

# Update module from source
lola mod update my-skills

# Regenerate assistant files after changes
lola update
```

## CLI Reference

### Module Management (`lola mod`)

| Command | Description |
|---------|-------------|
| `lola mod add <source>` | Add a module from git, folder, zip, or tar |
| `lola mod ls` | List registered modules |
| `lola mod info <name>` | Show module details |
| `lola mod init [name]` | Initialize a new module |
| `lola mod init [name] -c` | Initialize with a command template |
| `lola mod update [name]` | Update module(s) from source |
| `lola mod rm <name>` | Remove a module |

### Installation

| Command | Description |
|---------|-------------|
| `lola install <module>` | Install skills and commands to all assistants |
| `lola install <module> -a <assistant>` | Install to specific assistant |
| `lola install <module> -s project <path>` | Install to a project |
| `lola uninstall <module>` | Uninstall skills and commands |
| `lola installed` | List all installations |
| `lola update` | Regenerate assistant files |

## Creating a Module

### 1. Initialize

```bash
lola mod init my-skills
cd my-skills
```

This creates:

```
my-skills/
  .lola/
    module.yml       # Module manifest
  my-skills/
    SKILL.md         # Initial skill
```

### 2. Edit the skill

Edit `my-skills/SKILL.md`:

```markdown
---
name: my-skills
description: Description shown in skill listings
---

# My Skill

Instructions for the AI assistant...
```

### 3. Add more skills

Create additional skill directories, each with a `SKILL.md`:

```
my-skills/
  .lola/
    module.yml
  git-workflow/
    SKILL.md
  code-review/
    SKILL.md
```

### 4. Add slash commands

Create a `commands/` directory with markdown files:

```
my-skills/
  .lola/
    module.yml
  git-workflow/
    SKILL.md
  commands/
    review-pr.md
    quick-commit.md
```

Command files use YAML frontmatter:

```markdown
---
description: Review a pull request
argument-hint: <pr-number>
---

Review PR #$ARGUMENTS and provide feedback.
```

Update `.lola/module.yml`:

```yaml
type: lola/module
version: 0.1.0
description: My skills collection

skills:
  - git-workflow
  - code-review

commands:
  - review-pr
  - quick-commit
```

### 5. Add to registry and install

```bash
lola mod add ./my-skills
lola install my-skills
```

## Module Structure

```
my-module/
  .lola/
    module.yml       # Required: module manifest
    source.yml       # Auto-generated: tracks source for updates
  skill-name/
    SKILL.md         # Required: skill definition
    scripts/         # Optional: supporting files
    templates/       # Optional: templates
  commands/          # Optional: slash commands
    review-pr.md
    quick-commit.md
```

### module.yml

```yaml
type: lola/module
version: 0.1.0
description: What this module provides

skills:
  - skill-one
  - skill-two

commands:
  - review-pr
  - quick-commit
```

### SKILL.md

```markdown
---
name: skill-name
description: When to use this skill
---

# Skill Title

Your instructions, workflows, and guidance for the AI assistant.
```

### Command Files

```markdown
---
description: What this command does
argument-hint: <required> [optional]
---

Your prompt template here. Use $ARGUMENTS for all args or $1, $2 for positional.
```

**Argument variables:**
- `$ARGUMENTS` - All arguments as a single string
- `$1`, `$2`, `$3`... - Positional arguments

Commands are automatically converted to each assistant's format:
- Claude/Cursor: Markdown with frontmatter (pass-through)
- Gemini: TOML with `{{args}}` substitution

## How It Works

1. **Registry**: Modules are stored in `~/.lola/modules/`
2. **Installation**: Skills and commands are converted to each assistant's native format
3. **Prefixing**: Skills and commands are prefixed with module name to avoid conflicts (e.g., `mymodule-skill`)
4. **Project scope**: Copies modules to `.lola/modules/` within the project
5. **Updates**: `lola mod update` re-fetches from original source; `lola update` regenerates files

## License

[GPL-2.0-or-later](https://spdx.org/licenses/GPL-2.0-or-later.html)

## Authors

- Igor Brandao
- Katie Mulliken
