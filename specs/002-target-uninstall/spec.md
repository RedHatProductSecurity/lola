# Feature Specification: Target Uninstall Functions

**Feature Branch**: `002-target-uninstall`
**Created**: 2025-12-18
**Status**: Draft
**Input**: User description: "Ensure each target has an uninstall function that is called when needing to uninstall from a target."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent Uninstall Behavior Across Targets (Priority: P1)

A developer using lola wants to uninstall a module from their project. Currently, the `uninstall_cmd()` function manually handles removal of commands and agents inline rather than delegating to target-specific methods. This means target-specific cleanup logic cannot be added without modifying the CLI code.

**Why this priority**: This is the core problem - the uninstall logic is not properly encapsulated in targets. Each target should be responsible for its own cleanup, enabling target-specific uninstall behavior and making the codebase more maintainable.

**Independent Test**: Can be fully tested by uninstalling a module with skills, commands, agents, MCPs, and instructions, then verifying all generated files are removed correctly for each target.

**Acceptance Scenarios**:

1. **Given** a module with commands installed to Claude Code, **When** the user runs `lola uninstall my-module`, **Then** the target's `remove_command()` method is called for each command (not inline file deletion in CLI).

2. **Given** a module with agents installed to Claude Code, **When** the user runs `lola uninstall my-module`, **Then** the target's `remove_agent()` method is called for each agent (not inline file deletion in CLI).

3. **Given** any installed component type (skill, command, agent, MCP, instructions), **When** uninstalling, **Then** the corresponding target removal method is used consistently.

---

### User Story 2 - Target-Specific Cleanup (Priority: P2)

Different AI assistants may have different file formats or additional cleanup requirements during uninstall. For example, Gemini CLI uses a managed section in GEMINI.md, while Claude Code uses individual files. A target should be able to implement custom cleanup logic without changing the CLI.

**Why this priority**: Enables future extensibility for targets that need custom cleanup behavior. Without this, adding a new target or modifying uninstall behavior requires changes to the CLI code.

**Independent Test**: Can be tested by creating a target with custom cleanup logic and verifying it is called during uninstall.

**Acceptance Scenarios**:

1. **Given** a managed section target (Gemini CLI, OpenCode), **When** uninstalling commands, **Then** the target-specific `remove_command()` handles the appropriate file format (TOML for Gemini, MD for OpenCode).

2. **Given** a target that stores commands in a non-standard location, **When** uninstalling, **Then** the target's `remove_command()` method knows the correct paths without CLI hard-coding.

---

### User Story 3 - Unified Uninstall Orchestration (Priority: P3)

A developer extending lola wants to add a new target. They should be able to implement a single `uninstall()` method that handles all cleanup, or rely on the individual removal methods being called correctly.

**Why this priority**: Simplifies target implementation by providing a clear contract. Either implement `uninstall()` for full control, or implement individual `remove_*()` methods for component-level cleanup.

**Independent Test**: Can be tested by implementing a new target with either approach and verifying uninstall works correctly.

**Acceptance Scenarios**:

1. **Given** a target implementing individual `remove_*()` methods, **When** uninstalling, **Then** the orchestration layer calls each method appropriately.

2. **Given** a target that needs atomic uninstall (all-or-nothing), **When** implementing `uninstall()`, **Then** the target can override the orchestration and handle cleanup itself.

---

### Edge Cases

- What happens when a command file to be removed doesn't exist? The removal should succeed silently (idempotent).
- What happens when removing from a managed section target and the section marker is missing? The removal should succeed silently.
- What happens when the target's removal method fails? The CLI should log the failure but continue removing other components.
- What happens when uninstalling a module that was never installed? The CLI should report "no installations found" as it does today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add `remove_command(dest_dir: Path, cmd_name: str, module_name: str) -> bool` abstract method to `AssistantTarget` ABC.
- **FR-002**: System MUST add `remove_agent(dest_dir: Path, agent_name: str, module_name: str) -> bool` abstract method to `AssistantTarget` ABC.
- **FR-003**: System MUST implement `remove_command()` in `BaseAssistantTarget` with default behavior (delete file at expected path).
- **FR-004**: System MUST implement `remove_agent()` in `BaseAssistantTarget` with default behavior (delete file at expected path).
- **FR-005**: System MUST update `uninstall_cmd()` to delegate command removal to `target.remove_command()` instead of inline file deletion.
- **FR-006**: System MUST update `uninstall_cmd()` to delegate agent removal to `target.remove_agent()` instead of inline file deletion.
- **FR-007**: All removal methods MUST be idempotent (return True if file doesn't exist - nothing to remove is success).
- **FR-008**: System MUST update orphan removal functions (`_remove_orphaned_commands`, `_remove_orphaned_agents`) to use target methods.
- **FR-009**: System SHOULD add an `uninstall_from_assistant()` orchestration function in `targets/install.py` to mirror `install_to_assistant()`.

### Key Entities

- **AssistantTarget**: The abstract base class defining the interface for assistant targets. Adding removal methods ensures consistent uninstall behavior.
- **BaseAssistantTarget**: The default implementation providing common behavior. Default removal implementations delete files at expected paths.
- **ManagedSectionTarget**: Targets like Gemini CLI that write to managed sections. May need special handling for command/agent removal.
- **Installation**: The record of what was installed, used to determine what needs to be removed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five component types (skills, commands, agents, MCPs, instructions) have corresponding target removal methods.
- **SC-002**: The `uninstall_cmd()` function no longer contains inline file deletion logic for commands or agents.
- **SC-003**: Uninstalling a module with all component types succeeds for all supported targets (claude-code, cursor, gemini-cli, opencode).
- **SC-004**: Adding a new target only requires implementing the target class, not modifying CLI code for uninstall.
- **SC-005**: All existing tests continue to pass after refactoring.
- **SC-006**: New tests verify that target removal methods are called during uninstall.

## Assumptions

- The current `remove_skill()`, `remove_instructions()`, and `remove_mcps()` methods on targets are sufficient and don't need changes.
- The default file-based removal behavior is suitable for most targets (Claude Code, Cursor, OpenCode).
- Managed section targets (Gemini CLI, OpenCode for instructions) already handle their special cases in existing removal methods.
- Backward compatibility with existing installations is required - uninstalling modules installed before this change must work.
