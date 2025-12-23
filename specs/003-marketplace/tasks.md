# Tasks: Module Marketplace

**Input**: Design documents from `/specs/003-marketplace/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Tests will be created following existing Lola patterns (pytest)

**Organization**: Tasks grouped by user story with commits every ~150 LOC

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, etc.)
- Include exact file paths in descriptions

## Path Conventions

Single project structure: `src/lola/`, `tests/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and configuration

- [X] T001 Add MARKET_DIR and CACHE_DIR constants to src/lola/config.py
- [X] T002 [P] Create src/lola/market/ directory with __init__.py
- [X] T003 Commit: "feat(market): add marketplace directory structure and
      config"
- [X] T004 Run pytest, ruff check, ty check - all must pass before PR
- [X] T005 Create PR using gh pr create following .github/PULL_REQUEST_TEMPLATE

---

## Phase 2: Foundational - Part 1 (Marketplace Dataclass)

**Purpose**: Core data model that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create Marketplace dataclass in src/lola/models.py with fields
      (name, url, enabled, description, version, modules)
- [X] T007 [P] Add from_reference() classmethod to Marketplace in
      src/lola/models.py
- [X] T008 [P] Add from_cache() classmethod to Marketplace in
      src/lola/models.py
- [X] T009 [P] Add from_url() classmethod to Marketplace in src/lola/models.py
- [X] T010 Commit: "feat(models): add Marketplace dataclass with factory
      methods"
- [X] T011 Run pytest, ruff check, ty check - all must pass before PR
- [X] T012 Create PR using gh pr create following .github/PULL_REQUEST_TEMPLATE

---

## Phase 2: Foundational - Part 2 (Marketplace Methods)

- [X] T013 Add validate() method to Marketplace in src/lola/models.py
- [X] T014 [P] Add to_reference_dict() method to Marketplace in
      src/lola/models.py
- [X] T015 [P] Add to_cache_dict() method to Marketplace in src/lola/models.py
- [X] T016 Create unit tests for Marketplace dataclass in
      tests/test_marketplace_model.py
- [X] T017 Commit: "feat(models): add Marketplace validation and serialization
      methods"
- [X] T018 Run pytest, ruff check, ty check - all must pass before PR
- [X] T019 Create PR using gh pr create following .github/PULL_REQUEST_TEMPLATE

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Register Marketplace (Priority: P1) 🎯 MVP

**Goal**: Enable users to register marketplaces via
`lola market add <name> <url>`

**Independent Test**: Run `lola market add official https://example.com/mkt.yml`
and verify reference file at `$LOLA_HOME/market/official.yml` and cache at
`$LOLA_HOME/market/cache/official.yml` are created

### US1 - Part 1: MarketplaceRegistry Core

- [X] T020 [P] [US1] Create test file tests/test_market_manager.py with setup
- [X] T021 [P] [US1] Add test_registry_add() in tests/test_market_manager.py
      with HTTP mocking
- [X] T022 [P] [US1] Add test_registry_add_duplicate() in
      tests/test_market_manager.py
- [X] T023 [P] [US1] Add test_registry_add_invalid_yaml() in
      tests/test_market_manager.py
- [X] T024 [US1] Create MarketplaceRegistry class in
      src/lola/market/manager.py with __init__
- [X] T025 [US1] Implement add() method in MarketplaceRegistry in
      src/lola/market/manager.py
- [X] T026 [US1] Add YAML validation in add() method using
      Marketplace.validate()
- [X] T027 [US1] Add file save logic for reference and cache in add() method
- [X] T028 [US1] Add Rich console success/error messages in add() method
- [X] T029 [US1] Commit: "feat(market): implement MarketplaceRegistry.add()
      with tests"
- [X] T030 [US1] Run pytest, ruff check, ty check - all must pass before PR
- [X] T031 [US1] Create PR using gh pr create following
      .github/PULL_REQUEST_TEMPLATE

### US1 - Part 2: CLI Integration

- [X] T032 [US1] Create CLI command group in src/lola/cli/market.py with
      @click
- [X] T033 [US1] Implement market add command in src/lola/cli/market.py
- [X] T034 [US1] Register market command group in src/lola/main.py
- [X] T035 [P] [US1] Create CLI test file tests/test_cli_market.py with
      CliRunner
- [X] T036 [US1] Add test_market_add_command() in tests/test_cli_market.py
- [X] T037 [US1] Commit: "feat(cli): add lola market add command with tests"
- [X] T038 [US1] Run pytest, ruff check, ty check - all must pass before PR
- [X] T039 [US1] Create PR using gh pr create following
      .github/PULL_REQUEST_TEMPLATE

**Checkpoint**: User Story 1 complete - can add marketplaces via CLI

---

## Phase 4: User Story 3 - Install Module from Marketplace (Priority: P1)

**Goal**: Enable direct module installation from marketplace via
`lola install <module> -a <assistant>`

**Independent Test**: Run `lola install git-tools -a claude-code` with module
in marketplace, verify module is added and installed

**Note**: Implemented before US2 (search) as it's P1 and core value prop

### US3 - Implementation

- [X] T040 [P] [US3] Add test_find_module() in tests/test_market_manager.py
- [X] T041 [P] [US3] Add test_find_module_not_found() in
      tests/test_market_manager.py
- [X] T042 [P] [US3] Add test_find_module_disabled_marketplace() in
      tests/test_market_manager.py
- [X] T043 [US3] Implement find_module() method in MarketplaceRegistry in
      src/lola/market/manager.py
- [X] T044 [US3] Commit: "feat(market): add find_module() with tests"
- [X] T045 [US3] Run pytest, ruff check, ty check - all must pass before PR
- [X] T046 [US3] Create PR using gh pr create following
      .github/PULL_REQUEST_TEMPLATE
- [X] T047 [P] [US3] Add test_install_from_marketplace() in
      tests/test_cli_install.py
- [X] T048 [US3] Add marketplace lookup logic to install command in
      src/lola/cli/install.py
- [X] T049 [US3] Add automatic `lola mod add` call in install command when
      module found in marketplace
- [X] T050 [US3] Add error handling for module not found in any marketplace
- [X] T051 [US3] Add user prompt for multiple marketplace matches in
      src/lola/cli/install.py
- [X] T052 [US3] Commit: "feat(install): add marketplace module resolution"
- [X] T053 [US3] Run pytest, ruff check, ty check - all must pass before PR
- [X] T054 [US3] Create PR using gh pr create following
      .github/PULL_REQUEST_TEMPLATE

**Checkpoint**: User Stories 1 AND 3 complete - can add marketplaces and
install directly

---

## Phase 5: User Story 2 - Search Marketplace Modules (Priority: P2)

**Goal**: Enable searching across enabled marketplaces via
`lola search <query>`

**Independent Test**: Run `lola search authentication` and verify matching
modules displayed with marketplace name, description, version

### US2 - Implementation

- [X] T048 [P] [US2] Add test_registry_search() in
      tests/test_market_manager.py
- [X] T049 [P] [US2] Add test_registry_search_no_results() in
      tests/test_market_manager.py
- [X] T050 [P] [US2] Add test_registry_search_disabled_marketplace() in
      tests/test_market_manager.py
- [X] T051 [US2] Implement search() method in MarketplaceRegistry in
      src/lola/market/manager.py
- [X] T052 [US2] Add query matching logic (name, description, tags) in search()
- [X] T053 [US2] Add Rich console formatted output (dnf search style) in
      search()
- [X] T054 [US2] Commit: "feat(market): implement search() with tests"
- [X] T055 [US2] Create PR using gh pr create for search functionality
- [X] T056 [P] [US2] Add test_search_command() in tests/test_cli_market.py
- [X] T057 [US2] Implement search command in src/lola/cli/market.py
- [X] T058 [US2] Add "no marketplaces registered" check in search command
- [X] T059 [US2] Commit: "feat(cli): add lola search command"
- [X] T060 [US2] Create PR using gh pr create for search CLI command

**Checkpoint**: User Stories 1, 2, AND 3 complete - full marketplace discovery
and install workflow

---

## Phase 6: User Story 4 - Update Marketplace Cache (Priority: P2)

**Goal**: Enable cache refresh via `lola market update <name>` or
`lola market update --all`

**Independent Test**: Run `lola market update official` and verify cache file
refreshed from source URL

### US4 - Implementation

- [X] T061 [P] [US4] Add test_registry_update_one() in
      tests/test_market_manager.py
- [X] T062 [P] [US4] Add test_registry_update_all() in
      tests/test_market_manager.py
- [X] T063 [P] [US4] Add test_registry_update_network_failure() in
      tests/test_market_manager.py
- [X] T064 [US4] Implement update() method in MarketplaceRegistry in
      src/lola/market/manager.py
- [X] T065 [US4] Implement _update_one() helper method in MarketplaceRegistry
- [X] T066 [US4] Add error handling for network failures (preserve cache)
- [X] T067 [US4] Add validation for updated marketplace schema
- [X] T068 [US4] Commit: "feat(market): implement update() with tests"
- [X] T069 [US4] Create PR using gh pr create for update functionality
- [X] T070 [P] [US4] Add test_update_command() in tests/test_cli_market.py
- [X] T071 [US4] Implement update command in src/lola/cli/market.py with
      --all flag
- [X] T072 [US4] Add success/error messages with module count
- [X] T073 [US4] Commit: "feat(cli): add lola market update command"
- [X] T074 [US4] Create PR using gh pr create for update CLI command

**Checkpoint**: User Stories 1-4 complete - full marketplace lifecycle

---

## Phase 7: User Story 5 - Manage Marketplaces (Priority: P3)

**Goal**: Enable listing, enabling, disabling, and removing marketplaces

**Independent Test**: Run `lola market ls`, enable/disable, and rm commands,
verify state changes

### US5 - Part 1: List and Enable/Disable

- [X] T075 [P] [US5] Add test_registry_list() in tests/test_market_manager.py
- [X] T076 [P] [US5] Add test_registry_enable() in
      tests/test_market_manager.py
- [X] T077 [P] [US5] Add test_registry_disable() in
      tests/test_market_manager.py
- [X] T078 [US5] Implement list() method in MarketplaceRegistry in
      src/lola/market/manager.py
- [X] T079 [US5] Add Rich Table with marketplace name, status (green/red),
      module count in list()
- [X] T080 [US5] Implement enable() method in MarketplaceRegistry
- [X] T081 [US5] Implement disable() method in MarketplaceRegistry
- [X] T082 [US5] Implement _set_enabled() helper method in MarketplaceRegistry
- [X] T083 [US5] Commit: "feat(market): implement list/enable/disable with
      tests"
- [X] T084 [US5] Create PR using gh pr create for list/enable/disable

### US5 - Part 2: Remove and CLI Commands

- [X] T085 [P] [US5] Add test_registry_remove() in
      tests/test_market_manager.py
- [X] T086 [US5] Implement remove() method in MarketplaceRegistry
- [X] T087 [US5] Add file deletion for both reference and cache in remove()
- [X] T088 [US5] Commit: "feat(market): implement remove() with tests"
- [X] T089 [US5] Create PR using gh pr create for remove functionality
- [X] T090 [P] [US5] Add test_list_command() in tests/test_cli_market.py
- [X] T091 [P] [US5] Add test_enable_disable_commands() in
      tests/test_cli_market.py
- [X] T092 [P] [US5] Add test_rm_command() in tests/test_cli_market.py
- [X] T093 [US5] Implement ls command in src/lola/cli/market.py
- [X] T094 [US5] Implement enable command in src/lola/cli/market.py
- [X] T095 [US5] Implement disable command in src/lola/cli/market.py
- [X] T096 [US5] Implement rm command in src/lola/cli/market.py
- [X] T097 [US5] Commit: "feat(cli): add lola market ls/enable/disable/rm
      commands"
- [X] T098 [US5] Create PR using gh pr create for management CLI commands

**Checkpoint**: All user stories complete - full marketplace feature

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [X] T099 [P] Run ruff format on all new files to ensure PEP8 compliance
- [X] T100 [P] Run ty check on src/lola/market/ and src/lola/models.py
- [X] T101 [P] Verify all lines in new files are <= 80 characters
- [X] T102 [P] Add docstrings to all public methods following existing patterns
- [X] T103 Test all CLI commands manually following quickstart.md scenarios
- [X] T104 [P] Update CLAUDE.md if new patterns or conventions added
- [X] T105 Create example marketplace YAML file in
      specs/003-marketplace/examples/
- [X] T106 Commit: "docs(market): add documentation and examples"
- [X] T107 Create PR using gh pr create for documentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - No other dependencies
- **User Story 3 (Phase 4)**: Depends on Foundational and US1 (needs
  marketplace data)
- **User Story 2 (Phase 5)**: Depends on Foundational and US1 (needs
  marketplace data)
- **User Story 4 (Phase 6)**: Depends on Foundational and US1 (needs existing
  marketplaces)
- **User Story 5 (Phase 7)**: Depends on Foundational and US1 (needs existing
  marketplaces)
- **Polish (Phase 8)**: Depends on all desired user stories

### PR Dependencies

Each PR must be merged before starting the next logical phase:
- Setup PR (T004) → Foundational PRs can start
- Foundational PRs (T010, T016) → US1 PRs can start
- US1 PRs (T027, T034) → US2, US3, US4, US5 PRs can start
- All feature PRs merged → Polish PR can start

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services (Registry uses Marketplace dataclass)
- Core methods before CLI commands
- Error handling after happy path
- Commit and PR after each logical chunk (~150 LOC)

### Parallel Opportunities

- Phase 1: Both tasks can run in parallel
- Phase 2: All Marketplace dataclass methods marked [P] can run in parallel
  after basic dataclass created
- All test creation tasks within a story marked [P] can run in parallel
- After US1 complete: US2, US3, US4, US5 can run in parallel (different
  methods/files)

---

## Parallel Example: Foundational Phase Part 1

```bash
# After T005 creates the dataclass, these can run in parallel:
T006: "Add from_reference() classmethod"
T007: "Add from_cache() classmethod"
T008: "Add from_url() classmethod"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 3 Only)

1. Complete Phase 1: Setup → Create PR (T001-T004)
2. Complete Phase 2: Foundational → Create 2 PRs (T005-T010, T011-T016)
3. Complete Phase 3: User Story 1 → Create 2 PRs (T017-T027, T028-T034)
4. **STOP and VALIDATE**: Test marketplace registration independently
5. Complete Phase 4: User Story 3 → Create 2 PRs (T035-T040, T041-T047)
6. **STOP and VALIDATE**: Test end-to-end marketplace install flow
7. Deploy/demo MVP (add + install workflow)

**Total MVP PRs**: 7 PRs (each ~100-150 LOC)

### Incremental Delivery with PRs

1. Foundation (3 PRs) → Dataclass ready
2. Add US1 (2 PRs) → Test independently → Basic marketplace registration works
3. Add US3 (2 PRs) → Test independently → End-to-end install works (MVP!)
4. Add US2 (2 PRs) → Test independently → Discovery via search works
5. Add US4 (2 PRs) → Test independently → Cache updates work
6. Add US5 (4 PRs) → Test independently → Full management suite
7. Polish (1 PR) → Documentation and cleanup

**Total Feature PRs**: 16 PRs

---

## Commit Message Format

All commits follow conventional commits format:

- `feat(module): description` - New features
- `test(module): description` - Test additions
- `docs(module): description` - Documentation changes
- `fix(module): description` - Bug fixes

Examples from this plan:
- `feat(market): add marketplace directory structure and config`
- `feat(models): add Marketplace dataclass with factory methods`
- `feat(cli): add lola market add command with tests`

---

## PR Creation Strategy

Each PR MUST follow `.github/PULL_REQUEST_TEMPLATE.md` requirements:

**Before creating PR**:
1. Run `pytest` - all tests must pass
2. Run `ruff check src tests` - linting must pass
3. Run `ty check` - type checking must pass

**PR Creation with gh**:
```bash
gh pr create --title "feat: <story> - <feature>" --body "## Summary
- <bullet point 1>
- <bullet point 2>

## Related Issues
Relates to specs/003-marketplace

## Test Plan
- <how to verify>

## Checklist
- [x] Tests pass (\`pytest\`)
- [x] Linting passes (\`ruff check src tests\`)
- [x] Type checking passes (\`ty check\`)

## AI Disclosure
AI-assisted with Claude Code"
```

PR title format: `feat: <user story> - <specific feature>`

Examples:
- `feat: US1 - Add marketplace registry core functionality`
- `feat: US1 - Add lola market add CLI command`
- `feat: US3 - Add marketplace module resolution to install`

---

## Notes

- **Commit frequently**: After each ~150 LOC chunk
- **Create PRs immediately**: After each commit
- **Small, focused PRs**: Easier to review and merge
- Use early returns to avoid else statements
- All Rich console output must match dnf/yum style
- Green for enabled, red for disabled in status displays
- Tests use CliRunner for CLI commands, mock HTTP calls for downloads
- Follow existing Lola patterns from models.py and cli/mod.py

---

## Task Count Summary

- **Total Tasks**: 123 (includes quality check tasks before each PR)
- **Setup (Phase 1)**: 5 tasks (2 impl + 1 commit + 1 QA + 1 PR)
- **Foundational (Phase 2)**: 14 tasks (9 impl + 2 commits + 2 QA + 2 PRs)
- **User Story 1 (P1)**: 20 tasks (14 impl + 2 commits + 2 QA + 2 PRs)
- **User Story 3 (P1)**: 15 tasks (9 impl + 2 commits + 2 QA + 2 PRs)
- **User Story 2 (P2)**: 15 tasks (9 impl + 2 commits + 2 QA + 2 PRs)
- **User Story 4 (P2)**: 16 tasks (10 impl + 2 commits + 2 QA + 2 PRs)
- **User Story 5 (P3)**: 28 tasks (18 impl + 4 commits + 4 QA + 4 PRs)
- **Polish (Phase 8)**: 10 tasks (7 impl + 1 commit + 1 QA + 1 PR)
- **Parallel Tasks**: 43 tasks marked [P]
- **Total PRs**: 16 PRs (each with mandatory QA before creation)

**QA Requirements** (per .github/PULL_REQUEST_TEMPLATE.md):
- All PRs require: pytest ✓ ruff check ✓ ty check ✓

**MVP Scope**: Phases 1-4 (54 tasks, 7 PRs) - Estimated 3-4 hours
**Full Feature**: All 123 tasks, 16 PRs - Estimated 10-12 hours
