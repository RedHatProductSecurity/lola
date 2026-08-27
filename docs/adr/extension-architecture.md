# ADR: Extension Architecture

**Status**: Proposed
**Date**: 2026-04-28
**Last Updated**: 2026-08-26
**Authors**: Igor Brandao
**Reviewers**:

## Context

Lola's current Python implementation has hardcoded registries for assistant targets
(`TARGETS` dict in `targets/__init__.py`) and source handlers (`SOURCE_HANDLERS` list
in `parsers.py`). Adding support for a new AI assistant or module source type requires
modifying the core codebase.

As the AI assistant ecosystem grows — new assistants, agent frameworks, skill
registries, and security scanning needs emerging regularly — this hardcoded approach
does not scale. We need an extension system that allows any developer to add support
for new capabilities without forking or modifying the Lola core binary.

## Decision

Introduce a formal extension system with the following extension kinds:

| Kind          | What it extends                                               | Built-in examples                                   |
|---------------|---------------------------------------------------------------|-----------------------------------------------------|
| `target`      | Where skills are installed (assistant file formats and paths) | claude-code, cursor, gemini-cli, openclaw, opencode |
| `marketplace` | Where skills are discovered (catalogs and registries)         | yaml-catalog                                        |
| `runtime`     | Where skills are executed (agent framework environments)      | — (future)                                          |
| `source`      | How skills are fetched (transport protocols)                  | git, zip, tar, folder                               |
| `scan`        | How skills are validated (security scanning)                  | — (future)                                          |

The kind identifier `marketplace` is canonical, because a registry needs one
key per kind. "Repository" and "repo" remain accepted synonyms in prose and as
CLI aliases, in the same way `lola mod search` aliases `lola search --mod`.
Aliasing the surface while keeping one identifier lets readers arriving from
DNF, YUM or APT use the word they expect without making an extension manifest
ambiguous about which kind it declares.

Extensions will use a YAML manifest (`extension.yaml`) and a language-agnostic
communication protocol. The detailed design — manifest schema, discovery flow,
protocol spec, and SDK interfaces — will be defined in a separate design document
once the Go project structure is established.

## Rationale

- **Language-agnostic**: Extensions can be written in any language
- **Process isolation**: External extensions run as separate processes, protecting core stability
- **Community extensibility**: Anyone can add a new assistant or catalog without a core release
- **Forward-compatible**: New extension kinds can be added without architectural changes

## Consequences

### Positive Consequences

- Community can add support for new assistants without forking Lola
- Custom skill catalogs are addable as marketplace extensions
- Security scanning is pluggable via scan extensions
- Built-in and external extensions share the same interface contract

### Negative Consequences

- External extensions have subprocess overhead compared to compiled built-ins
- Extension protocol must be versioned to avoid breaking changes

## Alternatives Considered

### Alternative 1: Hardcoded handlers only
- Description: Continue adding new targets and sources directly to the core codebase
- Pros: Simple, no extension infrastructure needed
- Cons: Every new assistant requires a core release; community cannot contribute independently
- Reason for rejection: Does not scale with the growing AI assistant ecosystem

### Alternative 2: Shared library plugins (.so files)
- Description: Extensions as dynamically linked shared libraries
- Pros: No subprocess overhead, full Go type safety
- Cons: Not language-agnostic (Go-only), platform-specific binary compatibility issues
- Reason for rejection: Language-agnostic extensions are a core requirement

### Alternative 3: gRPC as initial protocol
- Description: Use gRPC from day one instead of stdin/stdout
- Pros: Strongly typed, supports streaming, concurrent calls
- Cons: Higher initial complexity, requires protobuf compilation for extension authors
- Reason for deferral: Start simple; gRPC is a planned future transport option

## References

- [ADR: Go Migration](go-migration.md) — prerequisite decision
- [Current Architecture](../dev-guide/architecture.md) — existing SourceHandler strategy pattern that extensions generalize
