# Quickstart: Improved Module Init Template

**Date**: 2025-12-18
**Feature**: 001-mod-init-template

## Overview

This feature enhances `lola mod init` to create a complete, well-documented module template with all lola content isolated under a `module/` subdirectory.

## Getting Started

### Create a New Module

```bash
# Create a new module with all components
lola mod init my-awesome-module

# Navigate to the module
cd my-awesome-module
```

### Customize the Template

1. **Edit the skill** (`module/skills/example-skill/SKILL.md`):
   - Replace `[REPLACE: ...]` markers with your content
   - Add detailed instructions for the AI assistant

2. **Edit the command** (`module/commands/example-command.md`):
   - Define the command's purpose and workflow
   - Use `$ARGUMENTS` to access user-provided arguments

3. **Edit the agent** (`module/agents/example-agent.md`):
   - Describe the agent's specialized role
   - Define guidelines and workflows

4. **Configure MCPs** (`module/mcps.json`):
   - Replace placeholder values with real MCP server configs
   - Or delete if not using MCPs

5. **Edit instructions** (`module/AGENTS.md`):
   - Describe when to use each component
   - Add module-level guidance

### Register and Install

```bash
# Add to lola registry
lola mod add ./my-awesome-module

# Install to current project
lola install my-awesome-module

# Or install to a specific project
lola install my-awesome-module /path/to/project
```

## Common Workflows

### Minimal Module (Skills Only)

```bash
lola mod init my-skills --no-command --no-agent --no-mcps
```

### Command-Only Module

```bash
lola mod init my-commands --no-skill --no-agent --no-mcps
```

### Empty Structure for Manual Setup

```bash
lola mod init my-module --minimal
```

### Initialize in Current Directory

```bash
cd my-existing-repo
lola mod init  # Uses directory name as module name
```

### Force Overwrite Existing Files

```bash
lola mod init my-module --force
```

## Directory Structure

After running `lola mod init my-module`:

```
my-module/
├── README.md                    # Repo documentation (not imported by lola)
└── module/                      # All lola-importable content
    ├── skills/
    │   └── example-skill/
    │       └── SKILL.md         # Skill definition with frontmatter
    ├── commands/
    │   └── example-command.md   # Slash command definition
    ├── agents/
    │   └── example-agent.md     # Subagent definition
    ├── mcps.json                # MCP server configuration
    └── AGENTS.md                # Module-level instructions
```

## Key Changes from Previous Versions

### New `module/` Subdirectory

All lola content is now under `module/` instead of at the repository root:

| Before | After |
|--------|-------|
| `skills/` | `module/skills/` |
| `commands/` | `module/commands/` |
| `agents/` | `module/agents/` |
| `AGENTS.md` | `module/AGENTS.md` |
| `mcps.json` | `module/mcps.json` |

**Why?** This allows you to:
- Edit module content without affecting running AI coding agents
- Keep repo-level files (tests, CI, docs) separate from lola content

### Dot-Separated Naming

Installed components now use dots instead of hyphens:

| Before | After |
|--------|-------|
| `my-module-my-skill/` | `my-module.my-skill/` |
| `/my-module-my-command` | `/my-module.my-command` |
| `@my-module-my-agent` | `@my-module.my-agent` |

### Migration Required

Existing modules without `module/` subdirectory will need migration:

```bash
# In your existing module directory:
mkdir module
mv skills commands agents AGENTS.md mcps.json module/
```

## Template Placeholders

All generated templates use `[REPLACE: ...]` markers:

```markdown
---
name: example-skill
description: [REPLACE: Brief description of what this skill does]
---
```

Find all placeholders:
```bash
grep -r "\[REPLACE:" module/
```

## Troubleshooting

### "Module uses legacy structure" Error

```
Error: Module 'my-module' uses legacy structure without module/ subdirectory.
```

**Solution**: Migrate your module by moving content into a `module/` subdirectory.

### File Conflict During Init

```
File 'module/skills/example-skill/SKILL.md' already exists.
[o]verwrite, [s]kip, [a]bort?
```

**Options**:
- `o`: Replace the existing file with the template
- `s`: Keep the existing file, continue with other files
- `a`: Cancel the entire init operation

Use `--force` to automatically overwrite all conflicts.
