# Sigstore Integration — Implementation Design

Paired with [ADR-0006: Sigstore Integration](../../adr/0006-sigstore-integration.md).

## Verification Flow

Based on [issue #84](https://github.com/LobsterTrap/lola/issues/84):

```mermaid
flowchart TD
    A([lola mod add source]) --> B{Source type?}
    B -->|OCI| C[Pull OCI artifact via skillimage pkg/oci]
    C --> D{Cosign signature present?}
    D -->|yes| E[Verify via pkg/oci cosign support]
    D -->|no| F{Enforcement?}

    B -->|git / tar / zip| G[Fetch to temp/]
    G --> H{.bundle file present?}
    H -->|yes| I[Verify bundle via sigstore-go]
    H -->|no| F

    F -->|strict| J[ERROR: unsigned module]
    F -->|warn| K[WARN: unsigned, cache anyway]
    F -->|absent| L[Skip verification, cache]

    E --> M{Valid?}
    M -->|yes| N[Cache module]
    M -->|no + strict| O[ERROR: invalid signature]
    M -->|no + warn| K

    I --> P{Valid?}
    P -->|yes| N
    P -->|no + strict| O
    P -->|no + warn| K
```

## Enforcement Matrix

| `sign:` in repo | Bundle present | `enforcement` | Result |
|---|---|---|---|
| no | any | — | skip verification, cache |
| yes | no bundle | `warn` | warn, cache anyway |
| yes | no bundle | `strict` | error, discard |
| yes | invalid bundle | `warn` | warn, cache anyway |
| yes | invalid bundle | `strict` | error, discard |
| yes | valid bundle | any | verified, cache |

## Repo YAML Sign Field

```yaml
modules:
  - name: "openssf-skill"
    description: "OpenSSF Security Instructions"
    version: "v0.1.0"
    repository: "https://github.com/ryanwaite/openssf-skill.git"
    tags: ["openssf", "security"]
    sign:
      enforcement: warn    # warn | strict
```

## Identity Derivation

For GitHub-hosted modules, identity is derived from the repository URL:

```
Repository: https://github.com/org/repo
  → OIDC Issuer:  https://token.actions.githubusercontent.com
  → Subject:      repo:org/repo:*
```

This means skill authors sign using GitHub Actions OIDC (keyless) and Lola verifies against the expected identity without any additional configuration.

## Sigstore Components

```mermaid
graph LR
    Author["Skill Author"] -->|signs with| Cosign["cosign / GH Actions"]
    Cosign -->|gets cert from| Fulcio["Fulcio<br/>OIDC CA"]
    Cosign -->|logs to| Rekor["Rekor<br/>Transparency Log"]
    Cosign -->|pushes| Registry["OCI Registry<br/>or .bundle file"]

    Lola["Lola (verifier)"] -->|reads| Registry
    Lola -->|verifies cert via| Fulcio
    Lola -->|checks log via| Rekor
```

- **Fulcio**: Free OIDC-based certificate authority, issues short-lived (10 min) certificates
- **Rekor**: Append-only transparency log for non-repudiation
- **cosign**: CLI/library for signing and verifying OCI artifacts and bundles

## GitHub Actions Signing Workflow

Reference workflow for skill authors to sign their modules:

```yaml
# .github/workflows/sign.yml
name: Sign Skills
on:
  push:
    tags: ['v*']

permissions:
  id-token: write    # Required for keyless signing
  contents: read

jobs:
  sign:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sigstore/cosign-installer@v3
      - run: |
          for f in skills/*/SKILL.md commands/*.md agents/*.md; do
            [ -f "$f" ] && cosign sign-blob "$f" --bundle "$f.bundle"
          done
```

## Scope Boundaries

**In scope (MVP):**
- Verification at add time for all add operations
- GitHub Actions OIDC identity derivation
- `sigstore-go/pkg/verify` for bundle verification
- OCI verification via skillimage `pkg/oci`
- Enforcement via repo YAML `sign:` field

**Out of scope (future):**
- GitLab, Bitbucket, self-hosted OIDC issuers
- Key-pair (offline) signing verification
- SLSA provenance attestation verification
- nono trust system integration (issue #62)
- Per-module `lola.yml` signing override
