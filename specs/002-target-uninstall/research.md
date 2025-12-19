# Research: Target Uninstall Functions

**Feature**: 002-target-uninstall
**Date**: 2025-12-18

## Design Decisions

### 1. Method Signature for remove_command() and remove_agent()

**Decision**: Use `remove_command(dest_dir: Path, cmd_name: str, module_name: str) -> bool`

**Rationale**:
- Matches existing `generate_command()` signature pattern for consistency
- `dest_dir` is the commands directory (e.g., `.claude/commands/`)
- `cmd_name` is the unprefixed command name (e.g., `review-pr`)
- `module_name` needed to construct the full filename using `get_command_filename()`
- Returns `bool` for success/failure like other target methods

**Alternatives Considered**:
- `remove_command(file_path: Path) -> bool` - Rejected: Would require CLI to know filename format
- `remove_command(module_name: str, cmd_name: str, project_path: str) -> bool` - Rejected: Too high-level, doesn't match other method patterns

### 2. Idempotent Removal Behavior

**Decision**: Return `True` when file doesn't exist (nothing to remove is success)

**Rationale**:
- Follows Unix philosophy: removing something that doesn't exist isn't an error
- Matches existing `remove_skill()` behavior in `BaseAssistantTarget`
- Enables safe re-runs of uninstall without spurious errors
- Constitution requires idempotent operations (Principle III)

**Alternatives Considered**:
- Return `False` when file doesn't exist - Rejected: Would complicate error handling in CLI
- Raise exception when file doesn't exist - Rejected: Too strict, breaks idempotency

### 3. Default Implementation Location

**Decision**: Implement defaults in `BaseAssistantTarget`, not individual targets

**Rationale**:
- Most targets use the same file-based pattern (delete file at expected path)
- Only Gemini CLI has different command format (TOML) but same deletion logic
- Reduces code duplication across 4 targets
- Targets can still override if needed (e.g., managed sections)

**Alternatives Considered**:
- Abstract methods with no default - Rejected: Would require identical code in 4 targets
- Mixin class - Rejected: Over-engineering for simple file deletion

### 4. Orchestration Function (FR-009)

**Decision**: Add `uninstall_from_assistant()` in `targets/install.py` to mirror `install_to_assistant()`

**Rationale**:
- Creates symmetry between install and uninstall operations
- Centralizes uninstall logic that's currently inline in CLI
- Makes it easier to add pre/post uninstall hooks in future
- Simplifies CLI code by delegating to orchestration layer

**Alternatives Considered**:
- Keep logic in CLI - Rejected: Already identified as the problem in the spec
- Add `uninstall()` method to AssistantTarget - Rejected: Would duplicate orchestration logic per target

### 5. Handling Managed Section Targets

**Decision**: Gemini CLI and OpenCode commands use standard file deletion (not managed sections)

**Rationale**:
- Reviewed existing code: commands are individual files, not managed sections
- Gemini: `.gemini/commands/{module}.{cmd}.toml`
- OpenCode: `.opencode/commands/{module}.{cmd}.md`
- Only skills use managed sections in GEMINI.md/AGENTS.md
- Default `remove_command()` works for all targets

**Alternatives Considered**:
- Override remove_command() for Gemini to handle TOML - Not needed: same deletion logic
- Create ManagedSectionCommandTarget mixin - Not needed: no targets use managed sections for commands

## Existing Patterns

### Current Removal Methods in AssistantTarget ABC

| Method | Location | Behavior |
|--------|----------|----------|
| `remove_skill()` | `base.py:106` | Abstract, implemented in `BaseAssistantTarget` |
| `remove_instructions()` | `base.py:111` | Abstract, implemented in `ManagedInstructionsTarget` mixin |
| `remove_mcps()` | `base.py:152` | Abstract, implemented in `MCPSupportMixin` |

### Missing Removal Methods (to be added)

| Method | Why Missing | Current Behavior |
|--------|-------------|------------------|
| `remove_command()` | Not abstracted | Inline in `uninstall_cmd()` at line 751-761 |
| `remove_agent()` | Not abstracted | Inline in `uninstall_cmd()` at line 763-775 |

### Current Inline Removal in CLI

```python
# install.py:751-761 - Command removal
for cmd_name in inst.commands:
    filename = target.get_command_filename(module_name, cmd_name)
    cmd_file = command_dest / filename
    if cmd_file.exists():
        cmd_file.unlink()

# install.py:763-775 - Agent removal
for agent_name in inst.agents:
    filename = target.get_agent_filename(module_name, agent_name)
    agent_file = agent_dest / filename
    if agent_file.exists():
        agent_file.unlink()
```

## Migration Strategy

1. Add abstract methods to `AssistantTarget` ABC
2. Implement defaults in `BaseAssistantTarget`
3. Update `uninstall_cmd()` to call target methods
4. Update `_remove_orphaned_commands()` and `_remove_orphaned_agents()`
5. Add `uninstall_from_assistant()` orchestration function
6. Add tests for new methods
7. Verify existing tests still pass

No data migration needed - this is a code refactoring with no changes to stored data or file formats.
