# ADR-0004: Go Project Structure

**Status**: Proposed
**Date**: 2026-04-29
**Last Updated**: 2026-08-26
**Authors**: Igor Brandao
**Reviewers**:

## Context

The Go migration (ADR-0002) and extension architecture (ADR-0003) require a
well-defined project layout. The directory structure must clearly separate
public packages (importable by extension developers) from private implementation
(CLI commands, internal logic), following established Go community conventions.

Lola has two distinct audiences for its Go packages:

1. **Extension developers** who need to import the extension SDK interfaces and
   model types
2. **Core contributors** who work on the CLI commands, extension lifecycle, and
   internal logic

These audiences require different access levels, which Go's `internal/` package
convention enforces at the compiler level.

## Decision

Adopt a three-directory layout:

| Directory   | Visibility                                                          | Contents                                                                                     |
|-------------|---------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| `cmd/`      | —                                                                   | Binary entry points. `cmd/lola/main.go` is a thin entry that calls `internal/cli`.           |
| `internal/` | **Private** — compiler-enforced, not importable outside this module | CLI commands, extension lifecycle, configuration, sync orchestration, repository management |
| `pkg/`      | **Public** — importable by extension developers                     | Extension SDK interfaces, shared model types, built-in extension implementations             |

Two rules govern the split:

- **`pkg/` must never import `internal/`.** Dependencies flow `cmd/` →
  `internal/` → `pkg/`. The compiler enforces only the external half of this, so
  it is checked in CI.
- **A package enters `pkg/` only when an extension developer must import it to
  compile.** Promotion from `internal/` to `pkg/` is a non-breaking addition;
  demotion is a breaking change. When in doubt, start in `internal/`.

The package-by-package tree lives in the paired design document, not here, so
that implementation detail can evolve without amending this ADR.

## Rationale

- Go's `internal/` package convention is the idiomatic way to enforce
  public/private boundaries in Go projects
- Three top-level directories is the minimum needed to separate concerns (entry
  point, private, public)
- This layout matches the pattern used by other Go CLI tools with extension
  systems

## Consequences

### Positive Consequences

- Extension developers have a clear, stable import path (`pkg/sdk/` and
  `pkg/models/`)
- Core contributors can freely refactor everything in `internal/` without
  breaking extension code
- One file per command in `internal/cli/` keeps the command tree easy to read
  for new contributors
- Built-in implementations in `pkg/builtin/` serve as development reference for
  extension authors
- Three-directory root keeps project navigation simple

### Negative Consequences

- Every new public type or interface must be consciously placed in `pkg/` —
  adding friction to API decisions
- Moving a package between `internal/` and `pkg/` is a breaking change requiring
  a semver bump
- Developers unfamiliar with Go conventions may not immediately understand the
  `internal/` restriction

## Alternatives Considered

### Alternative 1: Everything under pkg/
- Description: No `internal/` directory — all packages under `pkg/`
- Pros: Minimal root, everything importable
- Cons: Exposes private CLI internals to importers; no compiler-enforced
  boundary
- Reason for rejection: Extension developers should not depend on CLI handler
  internals

### Alternative 2: Flat root with many top-level directories
- Description: Each domain at root level (`sdk/`, `builtin/`, `cli/`, `config/`,
  etc.)
- Pros: Maximum visibility for each domain
- Cons: Too many top-level directories; loses the public/private distinction
- Reason for rejection: Cluttered root, no clear import guidance for extension
  developers

## Implementation Notes

- Prerequisite: [ADR-0002: Go Migration](go-migration.md)
- Paired design: [Go Project Structure
  design](../dev-guide/design/go-project-structure.md)
- The `pkg/builtin/` tree assumes built-in extensions are compiled into the
  `lola` binary, per [ADR-0003: Extension
  Architecture](extension-architecture.md). A decision to ship built-ins as
  external processes instead would replace that tree and require revising this
  ADR.

## References

- [ADR-0002: Go Migration](go-migration.md)
- [ADR-0003: Extension Architecture](extension-architecture.md)
- ADR-0007: Extension Sandboxing, proposed separately and not yet on `main`
