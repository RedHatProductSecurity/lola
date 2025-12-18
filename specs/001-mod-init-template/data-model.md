# Data Model: Improved Module Init Template

**Date**: 2025-12-18
**Feature**: 001-mod-init-template

## Entity Relationships

```
ModuleRepository (1) ──contains──> (1) ModuleContent
ModuleContent (1) ──contains──> (0..*) Skill
ModuleContent (1) ──contains──> (0..*) Command
ModuleContent (1) ──contains──> (0..*) Agent
ModuleContent (1) ──contains──> (0..1) MCPConfig
ModuleContent (1) ──contains──> (0..1) Instructions
```

## Entities

### ModuleRepository

The top-level directory structure for a lola module repository.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Module name (derived from directory name) |
| path | Path | Yes | Absolute path to the repository root |
| readme_path | Path | No | Path to README.md at repo root |
| module_dir | Path | Yes | Path to `module/` subdirectory containing lola content |

**Validation Rules**:
- `name` must match pattern `^[a-z0-9-]+$`
- `module_dir` must exist and be a directory
- `readme_path` is at `path / "README.md"`

**State Transitions**: N/A (static structure)

---

### ModuleContent

All lola-importable content within the `module/` subdirectory.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| path | Path | Yes | Path to the module content root (`module/`) |
| skills | list[str] | No | List of skill names |
| commands | list[str] | No | List of command names |
| agents | list[str] | No | List of agent names |
| mcps | list[str] | No | List of MCP server names |
| has_instructions | bool | Yes | Whether AGENTS.md exists |

**Validation Rules**:
- At least one of: skills, commands, agents, mcps, or instructions must exist
- All referenced skill directories must contain SKILL.md
- All referenced command files must have valid frontmatter
- All referenced agent files must have valid frontmatter

---

### Skill

A skill folder containing instructions and supporting files.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Skill name (directory name) |
| path | Path | Yes | Path to skill directory |
| description | string | No | From SKILL.md frontmatter |

**File Structure**:
```
module/skills/{name}/
├── SKILL.md          # Required: frontmatter + instructions
└── scripts/          # Optional: supporting files
```

**SKILL.md Frontmatter**:
```yaml
---
name: string          # Required
description: string   # Required
---
```

---

### Command

A slash command definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Command name (file stem) |
| path | Path | Yes | Path to command .md file |
| description | string | No | From frontmatter |
| argument_hint | string | No | From frontmatter |

**File Structure**:
```
module/commands/{name}.md
```

**Frontmatter**:
```yaml
---
description: string      # Required
argument-hint: string    # Optional
---
```

---

### Agent

A subagent definition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Agent name (file stem) |
| path | Path | Yes | Path to agent .md file |
| description | string | No | From frontmatter |
| model | string | No | From frontmatter |

**File Structure**:
```
module/agents/{name}.md
```

**Frontmatter**:
```yaml
---
description: string   # Required
model: string         # Optional (defaults to inherit)
---
```

---

### MCPConfig

MCP server configuration.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| path | Path | Yes | Path to mcps.json |
| servers | dict[str, MCPServer] | Yes | Server name → config mapping |

**File Structure**:
```
module/mcps.json
```

**Schema**:
```json
{
  "mcpServers": {
    "{server-name}": {
      "command": "string",
      "args": ["string", ...],
      "env": { "KEY": "value" }
    }
  }
}
```

---

### Instructions

Module-level guidance for AI assistants.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| path | Path | Yes | Path to AGENTS.md |
| content | string | Yes | Markdown content |

**File Structure**:
```
module/AGENTS.md
```

**No frontmatter** - plain markdown.

---

## New Directory Structure

### Template Output (after `lola mod init my-module`)

```
my-module/
├── README.md                    # Repo-level documentation (not imported)
└── module/                      # All lola-importable content
    ├── skills/
    │   └── example-skill/
    │       └── SKILL.md
    ├── commands/
    │   └── example-command.md
    ├── agents/
    │   └── example-agent.md
    ├── mcps.json
    └── AGENTS.md
```

### Installed Component Naming

| Component Type | Old Format | New Format (FR-016) |
|---------------|------------|---------------------|
| Skill | `module-skill/` | `module.skill/` |
| Command | `module-command.md` | `module.command.md` |
| Agent | `module-agent.md` | `module.agent.md` |
| MCP | `module-server` | `module-server` (unchanged) |

---

## Conflict Resolution States

When `lola mod init` encounters existing files:

| Current State | Action Options | Result |
|--------------|----------------|--------|
| File exists | `overwrite` | Replace with template |
| File exists | `skip` | Keep existing, continue |
| File exists | `abort` | Stop init, rollback |
| `--force` flag | N/A | Always overwrite |
| `--minimal` flag | N/A | Skip example content |

---

## Error States

### LegacyModuleStructureError (new)

Raised when `lola install` encounters a module without `module/` subdirectory.

| Field | Type | Description |
|-------|------|-------------|
| module_name | string | Name of the module |
| message | string | Error description with migration instructions |

**Migration Instructions Template**:
```
Module '{name}' uses legacy structure without module/ subdirectory.

To migrate:
1. Create a module/ directory
2. Move skills/, commands/, agents/, AGENTS.md, and mcps.json into module/
3. Re-run 'lola install {name}'
```
