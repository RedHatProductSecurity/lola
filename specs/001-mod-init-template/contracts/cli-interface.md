# CLI Interface Contracts

**Date**: 2025-12-18
**Feature**: 001-mod-init-template

## Command: `lola mod init`

### Synopsis

```
lola mod init [NAME] [OPTIONS]
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| NAME | No | Current directory name | Name of the module to create |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--skill` | `-s` | string | `example-skill` | Name for the initial skill |
| `--no-skill` | | flag | false | Skip creating initial skill |
| `--command` | `-c` | string | `example-command` | Name for the initial command |
| `--no-command` | | flag | false | Skip creating initial command |
| `--agent` | `-g` | string | `example-agent` | Name for the initial agent |
| `--no-agent` | | flag | false | Skip creating initial agent |
| `--no-mcps` | | flag | false | Skip creating mcps.json |
| `--no-instructions` | | flag | false | Skip creating AGENTS.md |
| `--minimal` | | flag | false | Create empty directories without examples |
| `--force` | `-f` | flag | false | Overwrite existing files without prompting |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (e.g., permission denied, invalid name) |
| 2 | Warning (e.g., target already exists) |

### Behavior

#### Case 1: New Module (NAME provided)

**Precondition**: Directory `NAME` does not exist in current directory.

**Action**:
1. Create `NAME/` directory
2. Create `NAME/README.md` with module documentation template
3. Create `NAME/module/` subdirectory with:
   - `skills/example-skill/SKILL.md` (unless `--no-skill`)
   - `commands/example-command.md` (unless `--no-command`)
   - `agents/example-agent.md` (unless `--no-agent`)
   - `mcps.json` (unless `--no-mcps`)
   - `AGENTS.md` (unless `--no-instructions`)

**Output**:
```
Initialized module my-module
  Path: /path/to/my-module

Structure
my-module/
├── README.md
└── module/
    ├── skills/
    │   └── example-skill/
    │       └── SKILL.md
    ├── commands/
    │   └── example-command.md
    ├── agents/
    │   └── example-agent.md
    ├── mcps.json
    └── AGENTS.md

Next steps:
  1. Edit module/skills/example-skill/SKILL.md with your skill content
  2. Edit module/commands/example-command.md with your command prompt
  3. Edit module/agents/example-agent.md with your agent instructions
  4. Edit module/mcps.json to configure MCP servers
  5. Edit module/AGENTS.md with module instructions
  6. lola mod add /path/to/my-module
```

#### Case 2: Initialize Current Directory (no NAME)

**Precondition**: Current directory name is valid module name.

**Action**: Same as Case 1 but creates content in current directory.

#### Case 3: Conflict - Directory Exists

**Precondition**: `NAME/` or `NAME/module/` already exists with files.

**Interactive Mode** (no `--force`):
```
File 'module/skills/example-skill/SKILL.md' already exists.
[o]verwrite, [s]kip, [a]bort?
```

**Force Mode** (`--force`):
```
Overwriting module/skills/example-skill/SKILL.md
```

#### Case 4: Minimal Mode

**Precondition**: `--minimal` flag is set.

**Action**: Create directory structure without example content files.

---

## Command: `lola install`

### Updated Behavior for Module Structure

#### Case: Module Uses New Structure

**Precondition**: Module has `module/` subdirectory with content.

**Action**: Install from `module/` subdirectory (existing behavior applied to new path).

#### Case: Legacy Module Structure (NEW)

**Precondition**: Module has content at root but no `module/` subdirectory.

**Action**: Fail with exit code 1.

**Output**:
```
Error: Module 'my-module' uses legacy structure without module/ subdirectory.

To migrate:
  1. Create a module/ directory in your module repository
  2. Move skills/, commands/, agents/, AGENTS.md, and mcps.json into module/
  3. Re-run 'lola install my-module'

See https://lola.dev/migration for more details.
```

---

## Component Naming Contract

### Installed File Names

| Component | Pattern | Example |
|-----------|---------|---------|
| Skill directory | `{module}.{skill}/` | `my-module.code-review/` |
| Command file | `{module}.{command}.md` | `my-module.review-pr.md` |
| Agent file | `{module}.{agent}.md` | `my-module.reviewer.md` |
| MCP server key | `{module}-{server}` | `my-module-example-server` |

### Slash Command Registration

Installed commands are accessible as:
```
/{module}.{command}
```

Example: `/my-module.review-pr`

### Agent Registration

Installed agents are accessible as:
```
@{module}.{agent}
```

Example: `@my-module.reviewer`
