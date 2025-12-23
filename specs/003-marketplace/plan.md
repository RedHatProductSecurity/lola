# Implementation Plan: Module Marketplace

**Branch**: `003-marketplace` | **Date**: 2025-12-22 | **Spec**:
[spec.md](./spec.md)
**Input**: Feature specification from
`/specs/003-marketplace/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See
`.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement a marketplace command system modeled after dnf/yum package managers.
The `lola market` command enables users to add, remove, update, enable,
disable, and list marketplace repositories. The implementation uses a
class-based architecture with a Marketplace class containing methods for each
operation, ensuring scalability, readability, and ease of contribution.
Marketplaces are YAML-based module catalogs with references stored at
`$LOLA_HOME/market/<name>.yml` and cached data at
`$LOLA_HOME/market/cache/<name>.yml`. Users can search across enabled
marketplaces and install modules directly without manual repository lookup,
with automatic module registration via `lola mod add` integration.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: click (CLI), rich (console output), pyyaml
(marketplace files), python-frontmatter (if needed for metadata), requests
(HTTP downloads) [NEEDS CLARIFICATION: Which HTTP library to use]
**Storage**: YAML files at `$LOLA_HOME/market/*.yml` (references) and
`$LOLA_HOME/market/cache/*.yml` (cached marketplace data)
**Testing**: pytest with pytest-cov, following existing test patterns in
`tests/test_cli_*.py`
**Target Platform**: Cross-platform (Linux, macOS, Windows) - CLI tool
**Project Type**: Single project (CLI extension to existing Lola codebase)
**Performance Goals**: Search results < 2 seconds for 500 modules,
marketplace updates < 5 seconds, cache recovery < 3 seconds
**Constraints**: Offline capability after initial cache, incremental commits
~150 LOC, follow PEP8/ruff standards, all code must be testable
**Scale/Scope**: Support 100+ modules across multiple marketplaces without
performance degradation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Code Quality Standards
- [x] PEP8 compliance enforced via ruff
- [x] All code must be testable (small functions, clear interfaces)
- [x] Incremental commits (~150 LOC per commit)
- [x] Functions must be small and readable
- [x] pytest best practices followed

### Architecture Standards
- [x] Class-based design for Marketplace operations
- [x] Methods for each operation (add, remove, update, enable, disable, list)
- [x] Follows existing Lola patterns (similar to mod.py CLI structure)
- [x] Integration with existing `lola mod add` and `lola install` commands

### Testing Requirements
- [x] All new code must have corresponding tests
- [x] Tests must follow existing patterns in `tests/test_cli_*.py`
- [x] Integration tests for marketplace + install workflow
- [x] Unit tests for Marketplace class methods

### Line Length Constraint
- [x] All files (including markdown) must have lines <= 80 characters
- [x] Long lines must be folded or escaped appropriately

**Status**: ✅ PASS - No constitution violations

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/lola/
├── cli/
│   ├── market.py          # NEW: Market CLI commands group
│   ├── mod.py             # MODIFY: Add marketplace integration
│   └── install.py         # MODIFY: Add marketplace module resolution
├── market/                # NEW: Marketplace core logic
│   ├── __init__.py
│   ├── manager.py         # Marketplace class with CRUD operations
│   ├── cache.py           # Cache management
│   ├── search.py          # Search functionality
│   └── validator.py       # YAML validation
├── models.py              # MODIFY: Add Marketplace, MarketplaceEntry models
└── config.py              # MODIFY: Add MARKET_DIR, MARKET_CACHE_DIR

tests/
├── test_cli_market.py     # NEW: CLI command tests
├── test_market_manager.py # NEW: Marketplace class tests
├── test_market_cache.py   # NEW: Cache management tests
├── test_market_search.py  # NEW: Search functionality tests
└── test_cli_install.py    # MODIFY: Add marketplace install tests
```

**Structure Decision**: Single project structure extending existing Lola
codebase. New `src/lola/market/` module contains marketplace core logic with
Marketplace class. CLI commands added to `src/lola/cli/market.py` following
existing patterns from `mod.py`. Integration points in `mod.py` and
`install.py` for seamless marketplace + module installation workflow.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
