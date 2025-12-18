# Research: Improved Module Init Template

**Date**: 2025-12-18
**Feature**: 001-mod-init-template

## Research Tasks

### 1. Current Module Structure Detection

**Question**: How does `Module.from_path()` currently detect module content?

**Findings** (from `src/lola/models.py:136-199`):
- `Module.from_path()` looks for content at the root of `module_path`:
  - `skills/` directory containing subdirectories with `SKILL.md`
  - `commands/` directory containing `.md` files
  - `agents/` directory containing `.md` files
  - `mcps.json` file with MCP server definitions
  - `AGENTS.md` file for module instructions
- A module is valid if it has at least one of: skills, commands, agents, mcps, or instructions
- No support for nested `module/` subdirectory currently exists

**Decision**: Modify `Module.from_path()` to check for a `module/` subdirectory first. If it exists, use that as the content root; otherwise, fall back to the current root-level detection for backward compatibility during migration period.

**Rationale**: This allows gradual migration while supporting both old and new structures.

**Alternatives Considered**:
- A: Force all modules to use `module/` structure immediately → Rejected: Would break all existing modules without migration path
- B: Use a marker file to indicate new structure → Rejected: Adds complexity; directory presence is sufficient

---

### 2. Component Naming Convention

**Question**: How are installed components currently named?

**Findings** (from `src/lola/targets/base.py:214-219`, `cli/install.py:136-139`):
- Commands: `{module_name}-{cmd_name}.md` (e.g., `my-module-my-command.md`)
- Agents: `{module_name}-{agent_name}.md` (e.g., `my-module-my-agent.md`)
- Skills: `{module_name}-{skill_name}` (e.g., `my-module-my-skill/`)
- MCPs: `{module_name}-{mcp_name}` prefix

**Decision**: Change to dot-separated naming: `{module_name}.{component_name}` per FR-016.
- Commands: `my-module.my-command.md`
- Agents: `my-module.my-agent.md`
- Skills: `my-module.my-skill/`
- MCPs: Keep hyphen prefix for now (JSON key naming conventions)

**Rationale**: Dot-separation is more readable and aligns with common namespace conventions.

**Alternatives Considered**:
- A: Use slash-like naming (e.g., `my-module/my-command.md`) → Rejected: Creates nested directories unnecessarily
- B: Use colon separation (`my-module:my-command`) → Rejected: Colons can cause issues on Windows

---

### 3. Interactive Prompts with Click

**Question**: How to implement interactive conflict resolution (FR-011)?

**Findings** (from existing code in `cli/mod.py:501-517`):
- Existing pattern uses `click.confirm()` for simple yes/no confirmations
- Click provides:
  - `click.confirm()`: Yes/No prompts
  - `click.prompt()`: Text input with validation
  - `click.Choice`: For multiple options

**Decision**: Use `click.prompt()` with `click.Choice` for each conflict:
```python
action = click.prompt(
    f"File '{filename}' already exists",
    type=click.Choice(['overwrite', 'skip', 'abort']),
    default='skip'
)
```

**Rationale**: Standard Click pattern, works well with `--force` flag to bypass prompts.

---

### 4. Template Content Strategy

**Question**: What should template files contain?

**Findings** (from existing `init_module()` in `cli/mod.py:312-436`):
- Current templates have basic frontmatter and placeholder descriptions
- Templates lack clear placeholder markers as specified in FR-007

**Decision**: Use `[REPLACE: ...]` markers for user-editable sections:
```markdown
---
name: [REPLACE: Your skill name]
description: [REPLACE: Description of what this skill does]
---

# [REPLACE: Skill Title]

[REPLACE: Describe the skill's purpose and capabilities]
```

**Rationale**: Clear markers are easier to find/replace and indicate intent to modify.

---

### 5. Legacy Module Detection

**Question**: How to detect legacy (non-`module/`) structures for error messaging?

**Findings**: Currently `Module.from_path()` detects content at root level.

**Decision**: In `lola install`, check for both structures:
1. If `module/` subdirectory exists and contains content → Use it
2. If root contains content but no `module/` → Error with migration instructions
3. If neither has content → Current "no skills/commands found" error

**Rationale**: Provides clear upgrade path for existing module authors.

---

### 6. MCP Template Format

**Question**: What should mcps.json template contain? (FR-013)

**Findings** (from current `cli/mod.py:389-400`):
- Current template has a working example MCP server
- FR-013 specifies commented placeholder instead

**Decision**: Use JSON with descriptive field values (JSON doesn't support comments):
```json
{
  "mcpServers": {
    "your-server-name": {
      "command": "[REPLACE: command, e.g., npx]",
      "args": ["[REPLACE: -y]", "[REPLACE: @package/server]"],
      "env": {
        "API_KEY": "${API_KEY_ENV_VAR}"
      }
    }
  }
}
```

**Rationale**: JSON limitation means we use descriptive placeholders instead of comments.

**Alternatives Considered**:
- A: Use JSONC (JSON with comments) → Rejected: Not standard JSON, may cause parsing issues
- B: Use YAML for MCP config → Rejected: Breaks compatibility with assistant expectations

---

### 7. Post-Init Summary Display

**Question**: What should the success summary show? (FR-008)

**Findings** (from current `init_module()` output):
- Shows structure tree (good)
- Shows numbered next steps (good)

**Decision**: Enhance with:
1. Created path summary
2. Tree view of structure
3. Numbered actionable next steps
4. Suggestion to run `lola mod add` when ready

**Rationale**: Matches existing pattern but adds clarity.

---

## Implementation Approach Summary

### Phase 1: Template Enhancement
1. Update `init_module()` to create `module/` subdirectory structure
2. Add `[REPLACE: ...]` placeholder markers to all templates
3. Update mcps.json to use placeholder format
4. Add README.md generation at repo root
5. Enhance summary output

### Phase 2: Installation Logic Updates
1. Modify `Module.from_path()` to prefer `module/` subdirectory
2. Add legacy structure detection with error and migration instructions
3. Update naming convention to dot-separated format in `BaseAssistantTarget`

### Phase 3: Interactive Conflict Resolution
1. Add `--force` flag to `mod init`
2. Implement per-file conflict prompts when not using `--force`
3. Handle partial directory merging

### Breaking Changes
- Existing modules without `module/` structure will need migration
- Component naming changes may affect existing references (minor)
