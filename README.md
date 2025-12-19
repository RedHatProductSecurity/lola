# Lola - AI Skills Package Manager

**Write your AI context once, use it everywhere.**

Every AI tool wants its own prompt format. Claude Code uses `SKILL.md`. Cursor uses `.mdc` rules. Gemini CLI uses `GEMINI.md`. Slash commands? Different syntax for each. You end up maintaining the same instructions in three different places—or worse, giving up and only using one tool.

Lola fixes this. Write your skills and commands once as portable modules, then install them everywhere with a single command.

[![asciicast](https://asciinema.org/a/UsbI8adasbdAhAFQuiXj70eVp.svg)](https://asciinema.org/a/UsbI8adasbdAhAFQuiXj70eVp)

## Supported AI Assistants

| Assistant | Skills | Commands |
|-----------|--------|----------|
| Claude Code | `.claude/skills/<module>-<skill>/SKILL.md` | `.claude/commands/<module>-<cmd>.md` |
| Cursor | `.cursor/rules/<module>-<skill>.mdc` | `.cursor/commands/<module>-<cmd>.md` |
| Gemini CLI | `GEMINI.md` | `.gemini/commands/<module>-<cmd>.toml` |
| OpenCode | `AGENTS.md` | `.opencode/commands/<module>-<cmd>.md` |

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
# Install to all assistants in the current directory
lola install my-skills

# Install to a specific assistant in the current directory
lola install my-skills -a claude-code

# Install to a specific project directory
lola install my-skills ./my-project
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
| `lola install <module> <path>` | Install to a specific project directory |
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
  skills/
    example-skill/
      SKILL.md         # Initial skill (unless --no-skill)
  commands/            # Created by default
    example-command.md # (unless --no-command)
  agents/              # Created by default
    example-agent.md   # (unless --no-agent)
```

### 2. Edit the skill

Edit `skills/example-skill/SKILL.md`:

```markdown
---
name: my-skills
description: Description shown in skill listings
---

# My Skill

Instructions for the AI assistant...
```

### 3. Add supporting files to skills

You can add additional files to any skill directory (scripts, templates, examples, etc.). Reference them using relative paths in your `SKILL.md`:

```markdown
# My Skill

Use the helper script: `./scripts/helper.sh`

Load the template from: `./templates/example.md`
```

**Path handling:** Use relative paths like `./file` or `./scripts/helper.sh` to reference files in the same skill directory. Each assistant handles these differently:

| Assistant | Skill Location | Supporting Files | Path Behavior |
|-----------|---------------|------------------|---------------|
| Claude Code | `.claude/skills/<skill>/SKILL.md` | Copied with skill | Paths work as-is |
| Cursor | `.cursor/rules/<skill>.mdc` | Stay in `.lola/modules/` | Paths rewritten automatically |
| Gemini | `GEMINI.md` (references only) | Stay in `.lola/modules/` | Paths work (SKILL.md read from source) |
| OpenCode | `AGENTS.md` (references only) | Stay in `.lola/modules/` | Paths work (SKILL.md read from source) |

- **Claude Code** copies the entire skill directory, so relative paths like `./scripts/helper.sh` work because the files are alongside `SKILL.md`
- **Cursor** only copies the skill content to an `.mdc` file, so Lola rewrites `./` paths to point back to `.lola/modules/<module>/skills/<skill>/`
- **Gemini/OpenCode** don't copy skills—they add entries to `GEMINI.md`/`AGENTS.md` that tell the AI to read the original `SKILL.md` from `.lola/modules/`, so relative paths work from that location

Example skill structure:

```
my-skills/
  skills/
    example-skill/
      SKILL.md
      scripts/
        helper.sh
      templates/
        example.md
```

### 4. Add more skills

Create additional skill directories under `skills/`, each with a `SKILL.md`:

```
my-skills/
  skills/
    example-skill/
      SKILL.md
    git-workflow/
      SKILL.md
    code-review/
      SKILL.md
```

### 4. Add slash commands

Create a `commands/` directory with markdown files:

```
my-skills/
  skills/
    example-skill/
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

> **Note:** Modules use auto-discovery. Skills, commands, and agents are automatically detected from the directory structure. No manifest file is required.

### 5. Add to registry and install

```bash
lola mod add ./my-skills
lola install my-skills
```

## Module Structure

```
my-module/
  skills/            # Skills directory
    skill-name/
      SKILL.md       # Required: skill definition
      scripts/       # Optional: supporting files
      templates/     # Optional: templates
  commands/          # Optional: slash commands
    review-pr.md
    quick-commit.md
  agents/            # Optional: subagents
    my-agent.md
```

> **Note:** Modules use auto-discovery. Skills are discovered from `skills/<name>/SKILL.md`, commands from `commands/*.md`, and agents from `agents/*.md`. No manifest file is required.

### SKILL.md

```markdown
---
name: skill-name
description: When to use this skill
---

# Skill Title

Your instructions, workflows, and guidance for the AI assistant.

Reference supporting files using relative paths:
- `./scripts/helper.sh` - files in the same skill directory
- `./templates/example.md` - subdirectories are supported
```

**Supporting files:** You can include scripts, templates, examples, or any other files in your skill directory. Use relative paths like `./file` or `./scripts/helper.sh` in your `SKILL.md` to reference them. These paths are automatically rewritten for different assistant types during installation.

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

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)
for guidelines on how to contribute to Lola.

## License

[GPL-2.0-or-later](https://spdx.org/licenses/GPL-2.0-or-later.html)

## Authors

- Igor Brandao
- Katie Mulliken
