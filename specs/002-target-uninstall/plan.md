# Implementation Plan: Target Uninstall Functions

**Branch**: `002-target-uninstall` | **Date**: 2025-12-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-target-uninstall/spec.md`

## Summary

Add `remove_command()` and `remove_agent()` methods to the `AssistantTarget` ABC and refactor `uninstall_cmd()` to delegate removal logic to targets instead of inline file deletion. This encapsulates target-specific cleanup behavior and enables extensibility for new targets.

## Technical Context

**Language/Version**: Python 3.13 (project uses modern type hints like `list[str]`)
**Primary Dependencies**: click (CLI), rich (console output), pathlib (file operations)
**Storage**: Local filesystem (markdown files, JSON config files)
**Testing**: pytest with Click's CliRunner for CLI tests
**Target Platform**: Cross-platform CLI (macOS, Linux, Windows)
**Project Type**: Single Python package with CLI
**Performance Goals**: Module operations < 5 seconds (per constitution)
**Constraints**: Idempotent operations required; existing tests must pass
**Scale/Scope**: 4 assistant targets (claude-code, cursor, gemini-cli, opencode)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality First | ✅ PASS | Will run ruff check, basedpyright before merge |
| II. Testing Standards | ✅ PASS | New tests for remove_command/remove_agent; existing CLI tests updated |
| III. User Experience Consistency | ✅ PASS | Idempotent removal (FR-007); no user-facing behavior change |
| IV. Performance Requirements | ✅ PASS | Refactoring only; no performance impact expected |

**Quality Gates**:
- Pre-commit: `ruff check src tests`, `ruff format --check`, `basedpyright src`
- Pre-merge: All above + `pytest` with no failures

## Project Structure

### Documentation (this feature)

```text
specs/002-target-uninstall/
├── plan.md              # This file
├── research.md          # Design decisions and patterns
├── data-model.md        # Entity/method definitions
├── quickstart.md        # Usage examples
├── contracts/           # Interface definitions
│   └── target-interface.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/lola/
├── targets/
│   ├── __init__.py      # Target registry and exports
│   ├── base.py          # AssistantTarget ABC + BaseAssistantTarget (MODIFY)
│   ├── install.py       # Install orchestration (ADD uninstall_from_assistant)
│   ├── claude_code.py   # Claude Code target (inherits defaults)
│   ├── cursor.py        # Cursor target (inherits defaults)
│   ├── gemini.py        # Gemini CLI target (may override remove_command)
│   └── opencode.py      # OpenCode target (may override remove_command)
├── cli/
│   └── install.py       # CLI commands (MODIFY uninstall_cmd)
└── ...

tests/
├── test_targets.py      # Target method tests (ADD remove_command/remove_agent tests)
├── test_cli_install.py  # CLI tests (UPDATE uninstall tests)
└── conftest.py          # Shared fixtures
```

**Structure Decision**: Single project structure matches existing lola codebase. Changes are localized to `targets/` module and `cli/install.py`.

## Complexity Tracking

No constitution violations. This is a straightforward refactoring with:
- 2 new abstract methods in ABC
- 2 default implementations in base class
- CLI delegation change (remove inline file operations)
- Optional orchestration function (FR-009)
