# Lola Constitution

## Core Principles

### I. Modular Design (NON-NEGOTIABLE)
Every feature must respect clear separation of concerns. Code is
organized into composable, interchangeable components:
- CLI commands live in `src/lola/cli/`
- Data models in `src/lola/models.py`
- Parsing logic in `src/lola/parsers.py`
- Target generation in `src/lola/targets/`
- No circular dependencies between modules
- Favor composition over inheritance

### II. Flexible Configuration
Support multiple module structures and discovery patterns:
- Auto-discovery of skills from `skills/<name>/SKILL.md`
- Auto-discovery of commands from `commands/*.md`
- Auto-discovery of agents from `agents/*.md`
- Backward compatibility with legacy structures required
- No mandatory manifest files - prefer convention over config
- Extensible source handling via strategy pattern

### III. Type Safety & Modern Python (NON-NEGOTIABLE)
Leverage Python 3.13+ features for code quality:
- Type hints required on all functions (params + returns)
- Use modern syntax: `list[str]` not `List[str]`
- Dataclasses for data models
- Immutable data structures preferred
- Pass type checking: `uv run ty check` (primary),
  `uv run mypy src` (secondary)
- No `typing.Any` without justification

### IV. Testing Philosophy (NON-NEGOTIABLE)
Comprehensive testing using pytest with fixture-based approach:
- Tests written BEFORE implementation (TDD when possible)
- Use `tests/conftest.py` fixtures for common setup
- Test multiple scenarios and edge cases
- Mock external dependencies (filesystem, git, etc)
- Isolate test environments (temp directories)
- CLI tests use Click's `CliRunner`
- Maintain >80% code coverage

### V. Robust Error Handling
Validate inputs and provide clear, actionable error messages:
- Custom exceptions in `src/lola/exceptions.py`
- User-facing errors use Rich console formatting
- Prevent security issues (path traversal, etc)
- Fail fast with meaningful context
- No silent failures or generic exceptions

### VI. Extensibility via Strategy Pattern
New capabilities added without modifying core logic:
- Source handlers implement common interface
- Target generators follow consistent pattern
- Easy to add new assistants in `src/lola/targets/`
- Plugin-like architecture for formats
- No hardcoded assistant names in core logic

### VII. Line Length Limit (NON-NEGOTIABLE)
All files must respect 80-character line limit:
- Code lines: max 80 characters
- Markdown lines: max 80 characters (except URLs/code blocks)
- Comments: max 80 characters
- Properly break, fold, or escape long lines
- Use implicit string concatenation for long strings
- Use parentheses for multi-line expressions

### VIII. Spec-Driven Development
Architectural and process changes require an ADR in `docs/adr/`
before implementation begins. For significant features, a
proposal is recommended in `openspec/changes/` or `specs/`.
No specific spec format or tooling is mandated — contributors
use whatever workflow fits; AI agents find specs by following
the topic guide in `AGENTS.md`.

See `docs/adr/spec-driven-development.md` for the full decision.

## Development Standards

### Python Code Style
- Ruff linter must pass (configured in pyproject.toml)
- Consistent naming: snake_case for functions/vars,
  PascalCase for classes
- Docstrings for public functions (Google style preferred)
- No magic numbers — use named constants
- Single responsibility per function

### Go Code Style
- `gofmt` formatting required (no exceptions)
- `golangci-lint run` must pass
- Errors wrapped with context (`fmt.Errorf("x: %w", err)`)
- No global mutable state
- Tests use `testify` with `-race` flag enabled

### Commit Message Standards
- Format: Conventional Commits (feat, fix, docs, chore,
  test, refactor)
- Subject line: max 50 characters (tpope 50/72 rule)
- Body lines: wrap at 72 characters
- Blank line required between subject and body
- Subject in imperative mood: "fix bug" not "fixed bug"

### Dependency Management
- Python: use `uv`, pin major versions in pyproject.toml,
  dev deps in `[dependency-groups]` (PEP 735)
- Go: standard `go.mod` / `go.sum`, justify additions
- Minimal dependency footprint in both languages

### File Organization
```text
src/lola/                     # Python source
├── cli/                      # Command implementations
├── targets/                  # Assistant-specific generators
├── main.py                   # Entry point
├── models.py                 # Core data structures
├── parsers.py                # Module parsing & fetching
├── config.py                 # Global paths & settings
├── frontmatter.py            # YAML frontmatter handling
├── utils.py                  # Shared utilities
└── exceptions.py             # Custom exceptions

cmd/                          # Go CLI entry points
internal/                     # Go internal packages

tests/                        # Python tests
├── conftest.py               # Shared fixtures
├── test_*.py                 # Test modules

e2e/features/                 # BDD Gherkin tests
├── steps/                    # Step implementations
├── support/                  # Test helpers
├── *.feature                 # Feature files
```

### Documentation Requirements
- README.md: User-facing, installation & quick start
- AGENTS.md: Navigation guide for AI tools (topic index)
- Code comments: Explain WHY, not WHAT
- Docstrings: Public API only, focus on usage

## Quality Gates

### Pre-Commit (Automated)
- Python: Ruff linting, ty check, mypy
- Go: golangci-lint, go vet
- 80-character line limit enforced
- No trailing whitespace
- YAML/Markdown valid

### Pre-Merge (Required)
- All tests pass (`pytest` + `go test -race ./...`)
- Code coverage >80% for changed source files
- No new type errors introduced
- New CLI commands have e2e BDD tests
- Updated AGENTS.md if dev workflow changes

## Complexity Budget

### Maximum Complexity Thresholds
- **Cyclomatic complexity**: <10 per function
- **Source files**: <500 lines (refactor if exceeded)
- **Function parameters**: <5 (use dataclasses for more)
- **Nesting depth**: <4 levels
- **Test files**: No limit (clarity over brevity)

### Violations Requiring Justification

| Pattern | When Allowed | Justification Required |
|---------|--------------|------------------------|
| Circular imports | Never | Hard error |
| `typing.Any` | External API boundaries | Document why |
| >80 chars | URLs in markdown | N/A |
| Magic numbers | Test data | Use descriptive vars |
| God classes | Never | Split responsibilities |

## Governance

### Constitution Authority
- This constitution supersedes code review preferences
- All PRs must verify compliance via checklist
- Violations require justification in PR description
- Amendments require approval from at least two maintainers

### Amendment Process
1. Propose change with rationale
2. Discuss impact on existing code
3. Document migration plan if breaking
4. Require approval from at least two maintainers
5. Update constitution and announce

### Runtime Guidance
For implementation-specific guidance during development, see
`AGENTS.md` which provides:
- Development commands
- Architecture overview
- Testing patterns
- Common tasks

**Version**: 2.0.0 | **Ratified**: 2025-12-19 | **Last Amended**:
2026-08-12
