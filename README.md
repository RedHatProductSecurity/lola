# Lola - AI Skills Package Manager

Lola manages and installs AI skills across different AI assistants. Package your prompts, workflows, and instructions into reusable modules that work with Claude Code, Cursor, and Gemini CLI.

## Supported AI Assistants

| Assistant | Skill Format | Location | Scope |
|-----------|--------------|----------|-------|
| Claude Code | `SKILL.md` directories | `.claude/skills/<skill>/` | user, project |
| Cursor | `.mdc` files | `.cursor/rules/<skill>.mdc` | user, project |
| Gemini CLI | Entries in `GEMINI.md` | `GEMINI.md` | project only |

> **Note:** Gemini CLI can only read files within the project workspace, so it only supports project-scope installs.

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

## Commands

### Module Management (`lola mod`)

| Command | Description |
|---------|-------------|
| `lola mod add <source>` | Add a module from git, folder, zip, or tar |
| `lola mod ls` | List registered modules |
| `lola mod info <name>` | Show module details |
| `lola mod init [name]` | Initialize a new module |
| `lola mod update [name]` | Update module(s) from source |
| `lola mod rm <name>` | Remove a module |

### Installation

| Command | Description |
|---------|-------------|
| `lola install <module>` | Install skills to all assistants |
| `lola install <module> -a <assistant>` | Install to specific assistant |
| `lola install <module> -s project <path>` | Install to a project |
| `lola uninstall <module>` | Uninstall skills |
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

Update `.lola/module.yml`:

```yaml
type: lola/module
version: 0.1.0
description: My skills collection

skills:
  - git-workflow
  - code-review
```

### 4. Add to registry and install

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
```

### module.yml

```yaml
type: lola/module
version: 0.1.0
description: What this module provides

skills:
  - skill-one
  - skill-two
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

## How It Works

1. **Registry**: Modules are stored in `~/.lola/modules/`
2. **Installation**: Skills are converted and copied to assistant-specific locations
3. **Project scope**: Uses symlinks to the global module for space efficiency
4. **Updates**: `lola mod update` re-fetches from original source; `lola update` regenerates files

## License

[GPL-2.0-or-later](https://spdx.org/licenses/GPL-2.0-or-later.html)

## Authors

- Igor Brandao
- Katie Mulliken
