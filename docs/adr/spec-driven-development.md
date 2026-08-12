# ADR: Adopt Spec-Driven Development

**Status**: Accepted
**Date**: 2026-08-12
**Last Updated**: 2026-08-12
**Authors**: Igor Brandao
**Reviewers**: @SecKatie

## Context

LoLa increasingly uses AI-assisted development. The project
already practices spec-first development informally — change
proposals and spec directories exist, and ADRs are established.
This decision makes the implicit practice explicit and gives AI
tools and human contributors a shared, tool-agnostic source of
truth.

## Decision

LoLa adopts Spec-Driven Development (SDD) governed by two
co-authoritative documents:

1. **AGENTS.md** — navigation guide and entry point for all AI
   tools and contributors
2. **.specify/memory/constitution.md** — project standards and
   principles

AGENTS.md points AI agents to the right artifacts for any task.
Where specs exist, AI agents find them by following the topic
guide in AGENTS.md. No specific spec format or tooling is
mandated.

Architectural and process changes require an ADR in `docs/adr/`
before implementation begins.

New CLI commands and features require e2e BDD tests (Gherkin,
in `e2e/features/`). Existing coverage gap is acknowledged and
tracked as a follow-on task.

## Bootstrap Exception

This ADR is authored outside the process it defines. The SDD
process cannot be used to create itself. All subsequent
architectural decisions follow the ADR → implementation binding
established here.

## Rationale

- Formalizes and stabilizes what already works informally in LoLa
- AGENTS.md as a lean navigation guide keeps AI instructions
  maintainable without prescribing tools or formats
- Tool-agnostic stance: contributors use whatever workflow fits;
  AI agents find specs by following AGENTS.md
- Constitution survives any tool change — not tied to a specific
  toolchain

## Consequences

### Positive Consequences

- Any AI tool starts from AGENTS.md and finds the right context
- No contributor lock-in to a specific spec format or toolchain
- Formalizes existing practice without adding bureaucracy
- Constitution is the single source of truth for quality standards

### Negative Consequences

- Requires discipline to keep AGENTS.md topic pointers accurate
  as the project evolves

## Alternatives Considered

### Alternative 1: Mandate a specific SDD toolchain
- Description: Require all contributors to use Speckit, OpenSpec,
  or uf for spec-driven development
- Pros: Enforced uniformity, single process
- Cons: Tool lock-in, friction for new contributors, blocks
  adoption if tooling changes
- Reason for rejection: Tool-agnostic approach is more resilient
  and inclusive

### Alternative 2: No formal SDD — keep the informal practice
- Description: Continue with the current ad-hoc spec-first
  approach without documenting it
- Pros: No overhead, no process to maintain
- Cons: AI tools lack a shared entry point, inconsistent practice
  across contributors, no enforceable standards
- Reason for rejection: Formalization costs little and stabilizes
  what already works

## Implementation Notes

The implementation PR (`feat/sdd-implementation`) follows once
this ADR is accepted. It delivers:

- Updated `AGENTS.md` (navigation guide with topic index)
- Updated `.specify/memory/constitution.md` (SDD section, Go
  standards)
- Filled `openspec/config.yaml` (LoLa project context)
- `.gitignore` update (add `.opencode/`)
- `CONTRIBUTING.md` SDD section
- `.github/PULL_REQUEST_TEMPLATE.md` spec link field

## References

- [LoLa's ADR convention](use-adrs.md)
- Existing informal practice: `openspec/changes/` and `specs/`
