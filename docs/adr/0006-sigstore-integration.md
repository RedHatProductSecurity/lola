# ADR-0006: Sigstore Integration

**Status**: Proposed
**Date**: 2026-04-29
**Authors**: Igor Brandao
**Reviewers**:

## Context

From the roadmap: "As AI skills become a standard way to inject context into agents, they also become a vector for prompt injection attacks and supply chain compromises." Skills can contain executable scripts, and without verification there is no way to validate their integrity or origin.

Issue #84 proposes an MVP for signature verification at `lola mod add` time using [Sigstore](https://www.sigstore.dev/) — the same standard used by PyPI, npm, and Maven Central. Issue #62 introduces the nono trust system as a reference implementation.

The Lola + Skill Image collaboration establishes that skillctl handles signing (via cosign at pack time) and Lola handles verification (at add/install time). In Go, Lola can use [sigstore-go](https://github.com/sigstore/sigstore-go) — a stable, production-ready Go library for sigstore verification with minimal dependencies.

The module package format (ADR-0005) defines `lola.mod` + `lola.sum` for dependency management and integrity checking. This ADR addresses cryptographic verification of module origin and tamper resistance on top of that foundation.

## Decision

Integrate sigstore bundle verification into the fetch pipeline for all add operations (`lola mod add`, `lola skill add`, `lola plugin add`, `lola ext add`). Use `sigstore-go` as a compiled-in library dependency.

**Verification flow**: fetch → verify → cache. Verification happens after fetching to a temp directory and before promoting to the local cache. If verification fails, the fetched content is discarded (strict mode) or cached with a warning (warn mode).

**Identity derivation**: For GitHub-hosted modules, the expected OIDC issuer and subject are derived automatically from the repository URL:
```
https://github.com/org/repo
  → issuer:  https://token.actions.githubusercontent.com
  → subject: repo:org/repo:*
```
No additional configuration needed for GitHub sources.

**Enforcement levels**: Opt-in via the repo/marketplace YAML `sign:` field:

```yaml
modules:
  - name: "openssf-skill"
    repository: "https://github.com/ryanwaite/openssf-skill.git"
    sign:
      enforcement: warn    # warn | strict
```

| `sign:` present | Bundle present | `enforcement` | Result |
|---|---|---|---|
| no | any | — | skip verification, cache |
| yes | no bundle | `warn` | warn, cache |
| yes | no bundle | `strict` | error, discard |
| yes | invalid bundle | `warn` | warn, cache |
| yes | invalid bundle | `strict` | error, discard |
| yes | valid bundle | any | verified, cache |

**OCI sources**: For OCI-distributed modules, cosign signature verification is handled by skillimage's `pkg/oci` which has built-in cosign support. No separate verification step needed.

**Go library**: `sigstore-go` (`github.com/sigstore/sigstore-go`) v1.0+:
- `pkg/verify` — core verification APIs
- `pkg/bundle` — sigstore bundle handling
- `pkg/root` — TUF-based trusted root management

## Rationale

- Sigstore is the industry standard for software signing — adopted by PyPI, npm, Maven Central, and the Linux kernel
- `sigstore-go` is stable (v1.0+), production-ready, and has minimal dependencies
- Verification at add time (not install time) ensures unsigned or tampered content never enters the cache
- Enforcement is opt-in — existing workflows are not broken; signing adoption is gradual
- Identity derivation from repository URL eliminates configuration overhead for the common case (GitHub Actions)
- For OCI sources, skillimage already handles cosign verification — no duplication

## Consequences

### Positive Consequences

- Skills from trusted sources are verifiable — publisher identity and tamper resistance
- Enforcement is progressive: start with `warn`, move to `strict` as signing adoption grows
- No configuration needed for GitHub-hosted modules — identity derived automatically
- OCI verification reuses skillimage's existing cosign support
- Verification is a compiled-in library call, not a subprocess — aligns with single-binary goal

### Negative Consequences

- `sigstore-go` adds to the transitive dependency tree (sigstore crypto libs)
- Skills without signatures are not blocked by default — requires marketplace authors to opt in
- GitLab, Bitbucket, and self-hosted sources need custom issuer/subject configuration (not covered in MVP)

## Alternatives Considered

### Alternative 1: No verification
- Description: Skip signature verification entirely
- Pros: No additional complexity or dependencies
- Cons: No protection against tampered skills or impersonated publishers
- Reason for rejection: The roadmap explicitly identifies this as a security priority

### Alternative 2: Shell out to cosign CLI
- Description: Execute `cosign verify` as a subprocess
- Pros: Simpler integration, no library dependency
- Cons: Requires cosign binary to be installed; defeats single-binary distribution goal
- Reason for rejection: Go library is available and stable; subprocess adds a runtime dependency

### Alternative 3: Custom signing with GPG
- Description: Implement a custom GPG-based signing scheme
- Pros: Well-understood technology, widely available
- Cons: Key management overhead, no keyless mode, no transparency log
- Reason for rejection: Sigstore solves key management with keyless signing (Fulcio + OIDC)

## Implementation Notes

See paired design document: `docs/dev-guide/design/sigstore-integration.md`

**Out of scope for MVP** (future work):
- Per-module `lola.yml` signing override
- GitLab / self-hosted OIDC issuers
- Key-pair (offline) signing mode
- SLSA provenance attestation verification
- nono integration (issue #62)

## References

- [GitHub Issue #84](https://github.com/LobsterTrap/lola/issues/84) — sigstore MVP proposal
- [GitHub Issue #62](https://github.com/LobsterTrap/lola/issues/62) — skill attestation / nono
- [CY26 Roadmap](../concepts/roadmap.md) — trusted catalogs vision
- [ADR-0005: Module Package Format](0005-module-package-format.md) — what gets signed
- [sigstore-go](https://github.com/sigstore/sigstore-go) — Go verification library
- [Sigstore](https://www.sigstore.dev/) — signing standard
- [skillimage.dev](https://skillimage.dev/) — cosign integration for OCI skills
