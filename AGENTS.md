# Lola — Agent Instructions

Lola is an AI skills package manager. Write AI context and skills
once, install them everywhere — Claude Code, Cursor, Gemini CLI,
OpenCode, and more.

## Working in this repo

- Before making changes: read the topic guide below and follow
  the referenced file for your task
- Commit format: Conventional Commits (feat, fix, docs, chore,
  test, refactor)
- Line limit: 80 characters — code, markdown, and comments
- Python: `ruff check src tests` and `uv run ty check` must pass
- Go: `golangci-lint run` and `go vet ./...` must pass
- Tests: `pytest` (Python), `go test -race ./...` (Go)
- Coverage: >80% on changed source files
- New CLI commands require e2e BDD tests in `e2e/features/`
- Use `uv` for Python deps, standard Go toolchain for Go code
- Never commit secrets, API keys, or internal hostnames

## Development Commands

```bash
# Python
source .venv/bin/activate
uv sync --group dev
pytest                        # All tests
pytest tests/test_cli_mod.py  # Single file
pytest -k test_add            # Pattern match
pytest --cov=src/lola         # Coverage
ruff check src tests          # Linting
uv run ty check               # Type checking (primary)
uv run mypy src               # Type checking (secondary)

# Go
go test -race ./...           # All Go tests
golangci-lint run             # Go linting
go vet ./...                  # Go vet

# E2E
make e2e                      # BDD tests (behave)
make e2e-wip                  # @wip tagged only

# CLI
lola --help
lola mod ls
lola install <module> -a claude-code
```

## Topic Guide

| Task | Read this |
|------|-----------|
| Project principles and standards | `.specify/memory/constitution.md` |
| SDD process | `docs/adr/spec-driven-development.md` |
| Contribution workflow | `CONTRIBUTING.md` |
| Architectural decisions | `docs/adr/` |
| Roles and decision-making | `GOVERNANCE.md` |
| Architecture overview | `docs/dev-guide/architecture.md` |
| E2E tests | `docs/dev-guide/design/e2e-bdd.md` |
| CLI reference | `docs/cli-reference/` |
| Proposing a change | `openspec/changes/` or `specs/` |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` |

## Architecture

### Core Data Flow

1. **Module Registration**: `lola mod add <source>` fetches
   modules (from git, zip, tar, or folder) to `~/.lola/modules/`
2. **Installation**: `lola install <module>` copies modules to
   project's `.lola/modules/` and generates assistant-specific
   files
3. **Updates**: `lola update` regenerates assistant files from
   source modules
4. **Marketplace**: `lola market add <name> <url>` fetches
   catalogs; `lola search <query>` searches across all sources

### Key Source Files

- `src/lola/main.py` — CLI entry point
- `src/lola/cli/mod.py` — Module management
- `src/lola/cli/install.py` — Install/uninstall/update
- `src/lola/cli/market.py` — Marketplace management
- `src/lola/models.py` — Data models
- `src/lola/config.py` — Global paths
- `src/lola/targets/` — Assistant definitions
- `src/lola/parsers.py` — Source fetching (strategy pattern)

### Target Assistants

| Assistant | Skills | Commands | Agents |
|-----------|--------|----------|--------|
| claude-code | `.claude/skills/` | `.claude/commands/` | `.claude/agents/` |
| cursor | `.cursor/skills/` | `.cursor/commands/` | `.cursor/agents/` |
| gemini-cli | `GEMINI.md` | `.gemini/commands/` | N/A |
| opencode | `AGENTS.md` | `.opencode/commands/` | `.opencode/agents/` |
| copilot-cli | `.github/skills/` | `.github/prompts/` | `.github/agents/` |
| copilot-vscode | `.github/skills/` | `.github/prompts/` | `.github/agents/` |

### Module Structure

```text
my-module/
  skills/
    skill-name/
      SKILL.md           # Required: skill definition
      scripts/            # Optional: supporting files
  commands/
    deploy.md            # Command entry file
    deploy/              # Optional: sidecar directory
      step1.md
  agents/
    reviewer.md          # Subagent definition
```

### Testing Patterns

Tests use Click's `CliRunner` for CLI testing. Key fixtures
in `tests/conftest.py`: `mock_lola_home`, `sample_module`,
`registered_module`, `mock_assistant_paths`,
`marketplace_with_modules`.

## Review Council Configuration

Constitution: .specify/memory/constitution.md

## Lola Skills

These skills are installed by Lola and provide specialized
capabilities. When a task matches a skill's description, read
the skill's SKILL.md file for detailed instructions.

<!-- lola:skills:start -->
<!-- lola:skills:end -->
