# ADR: Use Architecture Decision Records

**Status**: Accepted
**Date**: 2026-04-28
**Last Updated**: 2026-08-26
**Authors**: Igor Brandao
**Reviewers**:

## Context

We need to record the architectural decisions made on this project in a way that is
accessible, versioned, and avoids merge conflicts when multiple ADRs are submitted
concurrently.

## Decision

We will use Architecture Decision Records (ADRs) as
[described by Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).
Each ADR documents one architectural decision and lives as a single markdown file in
`docs/adr/`.

## How We Use ADRs

**Creating an ADR:**
Copy `docs/adr/template.md` to `docs/adr/<nnnn>-<topic-name>.md`, taking the
next unused number, fill in all sections, and open a pull request. Use
`make adr-new 0012-topic-name` for convenience; the target writes whatever
filename you give it.

**Updating an ADR:**
If a decision changes, update the existing ADR in place and bump `Last Updated` to
today's date. The git history provides a full audit trail of what changed and when.

**Deprecating an ADR:**
If a decision is no longer relevant, set `Status` to `Deprecated` and update
`Last Updated`. Add a brief note explaining why.

## ADR Statuses

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion, not yet accepted |
| **Accepted** | Approved and in effect |
| **Deprecated** | No longer relevant |

## Naming Convention

ADR files use a sequential number prefix followed by a descriptive kebab-case
name. The number is allocated when the ADR is opened. The date lives inside the
document, and topic names must be unique.

```text
docs/adr/<nnnn>-<topic-name>.md
```

ADRs written before this rule keep their existing unnumbered filenames. Nothing
is renamed retroactively, so cite an older ADR by its actual filename and put
the number in the link text.

## Template Changes

If the template needs to change, describe what changed and why in `docs/adr/README.md`,
apply the change to `docs/adr/template.md`, and open a pull request for Core Maintainer
approval. Existing ADRs are not retroactively reformatted.

## Rationale

A number gives every decision a short, stable handle to cite in review and from
other ADRs, and the kebab-case suffix keeps the subject clear from the filename.
Updating ADRs in place keeps one file per topic with git as the audit trail.

## Consequences

### Positive Consequences

- Every ADR has a short, stable identifier to cite
- ADR filenames are self-describing
- No external tooling dependency
- One file per topic

### Negative Consequences

- Two ADRs drafted concurrently can claim the same number; the later one is
  renumbered before merge
- Numbers record allocation order, not the date inside the document; use
  `git log docs/adr/` for true chronological ordering

## References

- [Michael Nygard on ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR README](README.md)
- [ADR Template](template.md)
