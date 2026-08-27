# ADR-0005: Module Package Format

**Status**: Proposed
**Date**: 2026-04-29
**Authors**: Igor Brandao
**Reviewers**:

## Context

Lola modules bundle multiple components — skills, commands, agents, MCPs, and hooks — into a single distributable unit. Currently modules are fetched as loose files from git repositories, zip archives, or local folders. There is no manifest listing module contents, no integrity checksums, and no standard packaging format for registry-based distribution.

For Lola to support trusted skill catalogs (per the roadmap) and integrate with OCI-based registries (per the Lola + Skill Image collaboration), we need:

1. A dependency declaration file (`lola.mod`) replacing the existing `.lola-req`
2. An integrity verification file (`lola.sum`) tracking checksums of installed modules
3. An OCI artifact type for distributing modules via OCI registries
4. A tarball format for file-based distribution

The Lola + Skill Image collaboration establishes that skillctl handles single-skill OCI packaging and signing, while Lola handles multi-component module bundling and installation. This ADR addresses Lola's packaging side.

## Decision

Introduce `lola.mod` + `lola.sum` as the dependency and integrity pair (mirroring Go's `go.mod` + `go.sum`), and define OCI and tarball distribution formats for modules.

**`lola.mod`**: Declares module dependencies and version requirements. Replaces `.lola-req` which becomes a backwards-compatible alias. Written by `lola mod add`, consumed by `lola sync`.

**`lola.sum`**: Project-level file storing SHA256 checksums of all installed module files. Generated automatically during `lola mod add`. Validated during `lola sync` and `lola install`. Committed to version control alongside `lola.mod` for team reproducibility.

**OCI module artifact**: Modules are packageable as OCI images with artifact type `application/vnd.lola.module.v1`. A single cosign signature covers the entire artifact. Compatible with any OCI-compliant registry (Quay, GHCR, Docker Hub, private).

**Tarball package**: Modules are packageable as `.tar.gz` archives for git and file-based distribution. A single sigstore bundle (`.tar.gz.bundle`) covers the entire archive.

**`lola.yml`** (or `lola.toml`): Optional module metadata file within a module, declaring name, version, description, components, and hooks. When present, used instead of auto-discovery. Viper supports both YAML and TOML formats.

## Rationale

- `lola.mod` + `lola.sum` mirrors Go's proven dependency model — well understood by the Go community and simple to implement
- `.lola-req` backwards compatibility ensures existing projects continue working
- OCI artifact type aligns with skillimage and the broader cloud-native distribution ecosystem
- Tarball format covers the common case of git-based module distribution
- Single signature per module (not per file) scales to modules with many components

## Consequences

### Positive Consequences

- Teams get reproducible installs by committing `lola.mod` and `lola.sum` to version control
- Module integrity is verifiable at install time via checksums
- OCI distribution enables registry-based discovery and cosign signing
- Existing modules without `lola.yml` continue working via auto-discovery
- `.lola-req` backwards compatibility avoids breaking existing projects

### Negative Consequences

- Two new files (`lola.mod`, `lola.sum`) in projects — though they replace the existing `.lola-req`
- OCI module format requires collaboration with skillimage team on layer structure
- Module authors who want signing must learn tarball or OCI packaging workflows

## Alternatives Considered

### Alternative 1: Sign individual files
- Description: Each file in a module gets its own `.bundle` signature file
- Pros: No packaging step needed
- Cons: Does not scale — a module with 10 components needs 10+ signature files
- Reason for rejection: Per-file signing is impractical for multi-component modules

### Alternative 2: npm-style tarball with package.json
- Description: Use a `package.json` manifest with npm-like `lola pack` / `lola publish`
- Pros: Familiar to JavaScript developers
- Cons: Introduces npm conventions into a Go tool; JSON is inconsistent with Lola's YAML-first approach
- Reason for rejection: Go's `go.mod` + `go.sum` model is a better fit for a Go-based tool

### Alternative 3: No manifest, rely solely on sigstore
- Description: Skip `lola.sum` and use sigstore bundles for all integrity verification
- Pros: Single verification mechanism
- Cons: Sigstore requires signing infrastructure; many modules will not be signed initially; no lightweight integrity check for unsigned modules
- Reason for rejection: `lola.sum` provides integrity verification regardless of whether modules are signed

## Implementation Notes

See paired design document: `docs/dev-guide/design/module-package-format.md`

## References

- [ADR-0002: Go Migration](0002-go-migration.md) — Go tech stack and skillimage integration
- [CY26 Roadmap](../concepts/roadmap.md) — trusted catalogs vision
- [Lola + Skill Image Collaboration](https://skillimage.dev/) — responsibility split
- [GitHub Issue #84](https://github.com/LobsterTrap/lola/issues/84) — sigstore MVP
