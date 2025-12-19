# Tasks: Improved Module Init Template

**Input**: Design documents from `/specs/001-mod-init-template/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: Tests ARE required per constitution (II. Testing Standards) - included below.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/lola/` at repository root
- **Tests**: `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new exception type and prepare for feature work

- [ ] T001 Add LegacyModuleStructureError exception in src/lola/exceptions.py
- [ ] T002 [P] Add test fixtures for module/ subdirectory structure in tests/conftest.py

**Checkpoint**: Infrastructure ready for user story implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core changes to Module detection that ALL user stories depend on

**⚠️ CRITICAL**: User Story 2 (installation logic) cannot work without this

- [ ] T003 Modify Module.from_path() to check for module/ subdirectory first in src/lola/models.py
- [ ] T004 Add test for Module.from_path() with module/ subdirectory in tests/test_models.py
- [ ] T005 Update naming convention to dot-separated format in src/lola/targets/base.py (get_command_filename, get_agent_filename)
- [ ] T006 [P] Update naming in src/lola/targets/claude_code.py to use dot-separator
- [ ] T007 [P] Update naming in src/lola/targets/cursor.py to use dot-separator
- [ ] T008 [P] Update naming in src/lola/targets/opencode.py to use dot-separator
- [ ] T009 [P] Update naming in src/lola/targets/gemini.py to use dot-separator
- [ ] T010 Add tests for dot-separated naming convention in tests/test_install.py

**Checkpoint**: Foundation ready - module/ detection and dot-naming work, user stories can begin

---

## Phase 3: User Story 1 - Initialize Complete Module Template (Priority: P1) 🎯 MVP

**Goal**: Create complete, well-documented module template with module/ subdirectory and [REPLACE:] markers

**Independent Test**: Run `lola mod init my-module` and verify all expected files/directories are created with useful content under module/

### Tests for User Story 1

- [ ] T011 [P] [US1] Test init creates module/ subdirectory structure in tests/test_mod.py::test_init_creates_module_subdirectory
- [ ] T012 [P] [US1] Test init creates README.md at repo root in tests/test_mod.py::test_init_creates_readme
- [ ] T013 [P] [US1] Test template files contain [REPLACE:] markers in tests/test_mod.py::test_templates_have_replace_markers
- [ ] T014 [P] [US1] Test init in current directory uses directory name in tests/test_mod.py::test_init_current_directory

### Implementation for User Story 1

- [ ] T015 [US1] Refactor init_module() to create module/ subdirectory structure in src/lola/cli/mod.py
- [ ] T016 [US1] Add README.md template generation at repo root in src/lola/cli/mod.py
- [ ] T017 [US1] Update SKILL.md template with [REPLACE:] markers in src/lola/cli/mod.py
- [ ] T018 [US1] Update command template with [REPLACE:] markers in src/lola/cli/mod.py
- [ ] T019 [US1] Update agent template with [REPLACE:] markers in src/lola/cli/mod.py
- [ ] T020 [US1] Update mcps.json template to use placeholder format in src/lola/cli/mod.py
- [ ] T021 [US1] Update AGENTS.md template with [REPLACE:] markers in src/lola/cli/mod.py
- [ ] T022 [US1] Update _module_tree() to show module/ subdirectory structure in src/lola/cli/mod.py
- [ ] T023 [US1] Update next steps output to reference module/ paths in src/lola/cli/mod.py

**Checkpoint**: User Story 1 complete - `lola mod init` creates proper module/ structure with templates

---

## Phase 4: User Story 2 - Edit Module Without Affecting Running Agents (Priority: P2)

**Goal**: Update installation logic to read from module/ subdirectory and fail on legacy structure

**Independent Test**: Verify `lola install` reads from module/ subdirectory and fails with migration instructions for legacy modules

### Tests for User Story 2

- [ ] T024 [P] [US2] Test install reads from module/ subdirectory in tests/test_install.py::test_install_from_module_subdirectory
- [ ] T025 [P] [US2] Test install fails on legacy structure with migration message in tests/test_install.py::test_install_fails_legacy_structure
- [ ] T026 [P] [US2] Test installed files use dot-separated naming in tests/test_install.py::test_installed_files_dot_naming

### Implementation for User Story 2

- [ ] T027 [US2] Add legacy structure detection in Module.from_path() in src/lola/models.py
- [ ] T028 [US2] Update install_cmd() to check for module/ subdirectory in src/lola/cli/install.py
- [ ] T029 [US2] Add error message with migration instructions for legacy modules in src/lola/cli/install.py
- [ ] T030 [US2] Update copy_module_to_local() to handle module/ path in src/lola/targets/install.py
- [ ] T031 [US2] Update skill installation to use content from module/ in src/lola/targets/install.py

**Checkpoint**: User Story 2 complete - installation works with module/ structure, rejects legacy

---

## Phase 5: User Story 3 - Selective Component Initialization (Priority: P3)

**Goal**: Support --minimal flag and --force flag for conflict resolution

**Independent Test**: Run `lola mod init --minimal` and verify empty structure; run with --force on existing directory

### Tests for User Story 3

- [ ] T032 [P] [US3] Test --minimal creates empty directories without content in tests/test_mod.py::test_init_minimal_flag
- [ ] T033 [P] [US3] Test --force overwrites existing files in tests/test_mod.py::test_init_force_flag
- [ ] T034 [P] [US3] Test conflict prompts without --force in tests/test_mod.py::test_init_conflict_prompt

### Implementation for User Story 3

- [ ] T035 [US3] Add --minimal flag to init_module() in src/lola/cli/mod.py
- [ ] T036 [US3] Add --force flag to init_module() in src/lola/cli/mod.py
- [ ] T037 [US3] Implement conflict detection for existing files in src/lola/cli/mod.py
- [ ] T038 [US3] Implement interactive prompt for file conflicts using click.prompt() in src/lola/cli/mod.py
- [ ] T039 [US3] Handle skip/overwrite/abort actions for each conflict in src/lola/cli/mod.py

**Checkpoint**: User Story 3 complete - selective init and conflict resolution work

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [ ] T040 [P] Run ruff check src tests and fix any issues
- [ ] T041 [P] Run basedpyright src and fix any type errors
- [ ] T042 [P] Run pytest to ensure all tests pass
- [ ] T043 Update CLI help text for mod init command in src/lola/cli/mod.py
- [ ] T044 Validate quickstart.md scenarios manually
- [ ] T045 Test end-to-end: init → mod add → install → verify structure

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - can proceed after T010
- **User Story 2 (Phase 4)**: Depends on Foundational - can proceed after T010
- **User Story 3 (Phase 5)**: Depends on User Story 1 (template changes must exist first)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent after Foundational phase
- **User Story 2 (P2)**: Independent after Foundational phase - can run parallel with US1
- **User Story 3 (P3)**: Depends on US1 completion (builds on init_module changes)

### Within Each User Story

- Tests written FIRST, ensure they FAIL before implementation
- Implementation follows test structure
- Story complete before moving to next priority (unless parallel execution)

### Parallel Opportunities

**Phase 1:**
- T001, T002 can run in parallel

**Phase 2:**
- T006, T007, T008, T009 can run in parallel (different target files)

**Phase 3 (US1):**
- T011, T012, T013, T014 can run in parallel (different test cases)

**Phase 4 (US2):**
- T024, T025, T026 can run in parallel (different test cases)

**Phase 5 (US3):**
- T032, T033, T034 can run in parallel (different test cases)

**Phase 6:**
- T040, T041, T042 can run in parallel (different tools)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "Test init creates module/ subdirectory structure in tests/test_mod.py"
Task: "Test init creates README.md at repo root in tests/test_mod.py"
Task: "Test template files contain [REPLACE:] markers in tests/test_mod.py"
Task: "Test init in current directory uses directory name in tests/test_mod.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T010)
3. Complete Phase 3: User Story 1 (T011-T023)
4. **STOP and VALIDATE**: Test `lola mod init` creates proper structure
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → `lola mod init` works with module/ structure (MVP!)
3. Add User Story 2 → `lola install` works with module/ structure
4. Add User Story 3 → Selective init and conflict resolution
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (template enhancements)
   - Developer B: User Story 2 (installation logic)
3. After US1 completes:
   - Developer A: User Story 3 (selective init)
4. Stories integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution requires: ruff, basedpyright, pytest all pass before merge
