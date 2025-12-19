# Tasks: Target Uninstall Functions

**Input**: Design documents from `/specs/002-target-uninstall/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included as this is a refactoring that must maintain existing behavior (Constitution II).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/lola/`, `tests/` at repository root
- Paths follow existing lola project structure from plan.md

---

## Phase 1: Setup

**Purpose**: Test fixtures and helper preparation

- [X] T001 Add test fixtures for command/agent removal in tests/conftest.py
- [X] T002 [P] Verify existing uninstall tests pass as baseline in tests/test_cli_install.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: ABC interface changes that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add `remove_command()` abstract method to AssistantTarget ABC in src/lola/targets/base.py (FR-001)
- [X] T004 Add `remove_agent()` abstract method to AssistantTarget ABC in src/lola/targets/base.py (FR-002)
- [X] T005 Implement default `remove_command()` in BaseAssistantTarget in src/lola/targets/base.py (FR-003)
- [X] T006 Implement default `remove_agent()` in BaseAssistantTarget in src/lola/targets/base.py (FR-004)
- [X] T007 Ensure `remove_command()` is idempotent (return True if file doesn't exist) per FR-007
- [X] T008 Ensure `remove_agent()` is idempotent and handles supports_agents=False per FR-007

**Checkpoint**: ABC interface extended - user story implementation can now begin

---

## Phase 3: User Story 1 - Consistent Uninstall Behavior (Priority: P1) 🎯 MVP

**Goal**: Delegate command/agent removal from CLI to target methods

**Independent Test**: Run `lola uninstall my-module` and verify commands/agents are removed via target methods

### Tests for User Story 1

- [X] T009 [P] [US1] Add test for `remove_command()` deletes file correctly in tests/test_targets.py
- [X] T010 [P] [US1] Add test for `remove_command()` idempotent when file missing in tests/test_targets.py
- [X] T011 [P] [US1] Add test for `remove_agent()` deletes file correctly in tests/test_targets.py
- [X] T012 [P] [US1] Add test for `remove_agent()` idempotent when file missing in tests/test_targets.py
- [X] T013 [P] [US1] Add test for `remove_agent()` returns True for non-agent-supporting target in tests/test_targets.py

### Implementation for User Story 1

- [X] T014 [US1] Update `uninstall_cmd()` to use `target.remove_command()` instead of inline deletion in src/lola/cli/install.py (FR-005)
- [X] T015 [US1] Update `uninstall_cmd()` to use `target.remove_agent()` instead of inline deletion in src/lola/cli/install.py (FR-006)
- [X] T016 [US1] Update `_remove_orphaned_commands()` to use `target.remove_command()` in src/lola/cli/install.py (FR-008)
- [X] T017 [US1] Update `_remove_orphaned_agents()` to use `target.remove_agent()` in src/lola/cli/install.py (FR-008)
- [X] T018 [US1] Verify existing uninstall CLI tests still pass after refactoring in tests/test_cli_install.py

**Checkpoint**: User Story 1 complete - uninstall now delegates to target methods

---

## Phase 4: User Story 2 - Target-Specific Cleanup (Priority: P2)

**Goal**: Verify targets can override removal methods for custom behavior

**Independent Test**: Create mock target with custom remove_command(), verify it's called during uninstall

### Tests for User Story 2

- [X] T019 [P] [US2] Add test that ClaudeCodeTarget inherits default removal behavior in tests/test_targets.py
- [X] T020 [P] [US2] Add test that CursorTarget inherits default removal behavior in tests/test_targets.py
- [X] T021 [P] [US2] Add test that GeminiTarget uses correct TOML filename in removal in tests/test_targets.py
- [X] T022 [P] [US2] Add test that OpenCodeTarget inherits default removal behavior in tests/test_targets.py

### Implementation for User Story 2

- [X] T023 [US2] Verify ClaudeCodeTarget works with inherited defaults in src/lola/targets/claude_code.py
- [X] T024 [US2] Verify CursorTarget works with inherited defaults in src/lola/targets/cursor.py
- [X] T025 [US2] Verify GeminiTarget works with inherited defaults in src/lola/targets/gemini.py
- [X] T026 [US2] Verify OpenCodeTarget works with inherited defaults in src/lola/targets/opencode.py

**Checkpoint**: User Story 2 complete - all targets verified to work with new methods

---

## Phase 5: User Story 3 - Unified Uninstall Orchestration (Priority: P3)

**Goal**: Add `uninstall_from_assistant()` orchestration function to mirror install

**Independent Test**: Call `uninstall_from_assistant()` directly and verify all component types removed

### Tests for User Story 3

- [X] T027 [P] [US3] Add test for `uninstall_from_assistant()` calls all removal methods in tests/test_targets.py
- [X] T028 [P] [US3] Add test for `uninstall_from_assistant()` returns correct count in tests/test_targets.py
- [X] T029 [P] [US3] Add test for `uninstall_from_assistant()` handles empty installation in tests/test_targets.py

### Implementation for User Story 3

- [X] T030 [US3] Add `uninstall_from_assistant()` function signature in src/lola/targets/install.py (FR-009)
- [X] T031 [US3] Implement skill removal via `target.remove_skill()` in uninstall_from_assistant()
- [X] T032 [US3] Implement command removal via `target.remove_command()` in uninstall_from_assistant()
- [X] T033 [US3] Implement agent removal via `target.remove_agent()` in uninstall_from_assistant()
- [X] T034 [US3] Implement MCP removal via `target.remove_mcps()` in uninstall_from_assistant()
- [X] T035 [US3] Implement instructions removal via `target.remove_instructions()` in uninstall_from_assistant()
- [X] T036 [US3] Add verbose output support to uninstall_from_assistant()
- [X] T037 [US3] Export `uninstall_from_assistant` from src/lola/targets/__init__.py

**Checkpoint**: User Story 3 complete - orchestration function available

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and validation

- [X] T038 Run `ruff check src tests` and fix any issues
- [X] T039 Run `ruff format src tests` and fix any formatting issues
- [X] T040 Run `basedpyright src` and fix any type errors
- [X] T041 Run full test suite `pytest` and ensure all tests pass (SC-005)
- [X] T042 Verify SC-002: `uninstall_cmd()` no longer contains inline file deletion for commands/agents
- [X] T043 Run quickstart.md verification checklist

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (P1) → US2 (P2) → US3 (P3) in priority order
  - OR US1, US2, US3 in parallel if team capacity allows
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent of US1/US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation tasks in order listed
- Story complete before moving to next priority

### Parallel Opportunities

**Within Phase 2 (Foundational)**:
- T003, T004 (ABC methods) must be sequential (same file section)
- T005, T006 (defaults) can run after T003/T004

**Within Phase 3 (US1)**:
- T009-T013 (tests) can all run in parallel
- T014-T017 (implementation) should be sequential (same file)

**Within Phase 4 (US2)**:
- T019-T022 (tests) can all run in parallel
- T023-T026 (verification) can all run in parallel

**Within Phase 5 (US3)**:
- T027-T029 (tests) can all run in parallel
- T030-T037 (implementation) should be sequential (same file)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all US1 tests together:
Task: "Add test for remove_command() deletes file correctly in tests/test_targets.py"
Task: "Add test for remove_command() idempotent when file missing in tests/test_targets.py"
Task: "Add test for remove_agent() deletes file correctly in tests/test_targets.py"
Task: "Add test for remove_agent() idempotent when file missing in tests/test_targets.py"
Task: "Add test for remove_agent() returns True for non-agent-supporting target in tests/test_targets.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `lola uninstall` and verify delegation works
5. Run all tests - this is the MVP

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP complete
3. Add User Story 2 → Verify all targets work → Enhanced coverage
4. Add User Story 3 → Add orchestration → Full feature complete

### Single Developer Flow

Since this is a small refactoring:
1. T001-T008: Foundation (estimate: 30 min)
2. T009-T018: US1 MVP (estimate: 45 min)
3. T019-T026: US2 verification (estimate: 30 min)
4. T027-T037: US3 orchestration (estimate: 45 min)
5. T038-T043: Polish (estimate: 15 min)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing
- Commit after each phase completion
- This is a refactoring - existing behavior MUST be preserved
- Constitution requires: ruff check, basedpyright, pytest all passing
