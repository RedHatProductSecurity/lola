# ADR-0004: Go Project Structure

**Status**: Proposed
**Date**: 2026-04-29
**Authors**: Igor Brandao
**Reviewers**:

## Context

The Go migration (ADR-0002) and extension architecture (ADR-0003) require a well-defined project layout. The directory structure must clearly separate public packages (importable by extension developers) from private implementation (CLI commands, internal logic), following established Go community conventions.

Lola has two distinct audiences for its Go packages:
1. **Extension developers** who need to import the extension SDK interfaces and model types
2. **Core contributors** who work on the CLI commands, extension lifecycle, and internal logic

These audiences require different access levels, which Go's `internal/` package convention enforces at the compiler level.

## Decision

Adopt a three-directory layout: `cmd/`, `internal/`, `pkg/`.

```
cmd/                               # Binary entry points
  lola/
    main.go

internal/                          # PRIVATE — compiler-enforced, not importable
  cli/                            # Cobra commands (one file per subcommand)
  extensions/                     # Extension discovery, registration, lifecycle
  config/                        # Viper configuration and LOLA_HOME paths
  sync/                          # Install/uninstall/update orchestration
  frontmatter/                   # YAML frontmatter parser
  repo/                          # Repository management
  serve/                         # API server (future)

pkg/                               # PUBLIC — importable by extension developers
  sdk/                            # Extension SDK: interfaces and manifest types
  builtin/                       # Built-in extension implementations
  models/                        # Shared model types (Module, Skill, etc.)
```

**`cmd/lola/main.go`**: Thin entry point that calls `internal/cli`.

**`internal/`**: All private implementation. Go compiler prevents any code outside this module from importing these packages.

**`pkg/`**: All public packages. Extension developers import `pkg/sdk/` for interfaces and `pkg/models/` for shared types. `pkg/builtin/` contains built-in implementations — public so they serve as reference for extension authors.

## Rationale

- Go's `internal/` package convention is the idiomatic way to enforce public/private boundaries in Go projects
- Three top-level directories is the minimum needed to separate concerns (entry point, private, public)
- This layout matches the pattern used by other Go CLI tools with extension systems

## Consequences

### Positive Consequences

- Extension developers have a clear, stable import path (`pkg/sdk/` and `pkg/models/`)
- Core contributors can freely refactor everything in `internal/` without breaking extension code
- One file per command in `internal/cli/` makes the command tree easy to navigate for new contributors
- Built-in implementations in `pkg/builtin/` serve as development reference for extension authors
- Three-directory root keeps project navigation simple

### Negative Consequences

- Every new public type or interface must be consciously placed in `pkg/` — adding friction to API decisions
- Moving a package between `internal/` and `pkg/` is a breaking change requiring a semver bump
- Developers unfamiliar with Go conventions may not immediately understand the `internal/` restriction

## Alternatives Considered

### Alternative 1: Everything under pkg/
- Description: No `internal/` directory — all packages under `pkg/`
- Pros: Minimal root, everything importable
- Cons: Exposes private CLI internals to importers; no compiler-enforced boundary
- Reason for rejection: Extension developers should not depend on CLI handler internals

### Alternative 2: Flat root with many top-level directories
- Description: Each domain at root level (`sdk/`, `builtin/`, `cli/`, `config/`, etc.)
- Pros: Maximum visibility for each domain
- Cons: Too many top-level directories; loses the public/private distinction
- Reason for rejection: Cluttered root, no clear import guidance for extension developers

## Implementation Notes

See paired design document: `docs/dev-guide/design/go-project-structure.md`

## References

- [ADR-0002: Go Migration](0002-go-migration.md)
- [ADR-0003: Extension Architecture](0003-extension-architecture.md)
