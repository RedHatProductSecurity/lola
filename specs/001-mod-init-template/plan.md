# Implementation Plan: Improved Module Init Template

**Branch**: `001-mod-init-template` | **Date**: 2025-12-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-mod-init-template/spec.md`

## Summary

Enhance `lola mod init` to create a complete, well-documented module template with all lola content isolated under a `module/` subdirectory. This allows module authors to edit module content (AGENTS.md, skills/, commands/, agents/, mcps.json) without affecting running coding agents, while keeping repo-level files (README.md, tests, CI config) at the root. The feature also updates `lola install` to read from the new `module/` subdirectory structure and use dot-separated naming for installed components.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: click, rich, pyyaml, python-frontmatter
**Storage**: Local filesystem (YAML frontmatter in .md files, JSON for mcps.json)
**Testing**: pytest with Click's CliRunner
**Target Platform**: macOS, Linux, Windows (CLI tool)
**Project Type**: Single project (Python CLI)
**Performance Goals**: Module initialization < 10 seconds, registry operations < 1 second
**Constraints**: < 500ms CLI cold start, < 256MB memory
**Scale/Scope**: Modules with < 50 skills/commands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Code Quality First** | ✅ PASS | All code will pass `ruff check`, `basedpyright`, use `uv` for deps |
| **II. Testing Standards** | ✅ PASS | Will use pytest + CliRunner, tests in `tests/test_mod.py` |
| **III. User Experience Consistency** | ✅ PASS | Clear error messages, exit codes (0/1/2), progress feedback, --help |
| **IV. Performance Requirements** | ✅ PASS | Local filesystem ops only, well under 5s limit |

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/001-mod-init-template/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/lola/
├── cli/
│   ├── mod.py           # MODIFY: Enhanced init_module() with module/ structure
│   └── install.py       # MODIFY: Add module/ subdirectory lookup, dot naming
├── models.py            # MODIFY: Module.from_path() to support module/ subdirectory
├── parsers.py           # REVIEW: Module fetching may need adjustment
├── exceptions.py        # MODIFY: Add LegacyModuleStructureError
└── targets/             # REVIEW: Naming convention change for installed files
    ├── base.py
    ├── claude_code.py
    ├── cursor.py
    ├── gemini.py
    └── opencode.py

tests/
├── test_mod.py          # ADD: Tests for new init behavior
├── test_install.py      # MODIFY: Tests for module/ structure handling
└── conftest.py          # REVIEW: May need new fixtures
```

**Structure Decision**: Single project structure with CLI entry point. Source modifications focus on `cli/mod.py` for template generation and `cli/install.py` for installation logic changes.

## Complexity Tracking

> No constitution violations requiring justification.
