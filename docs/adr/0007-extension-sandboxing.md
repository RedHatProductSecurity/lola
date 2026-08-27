# ADR-0007: Extension Sandboxing

**Status**: Proposed
**Date**: 2026-08-25
**Last Updated**: 2026-08-26
**Authors**: trevor-vaughan
**Reviewers**:

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

## Context

[ADR-0003: Extension Architecture](extension-architecture.md) establishes that
any developer can add targets, sources, and catalogs without forking Lola. That
is the goal. It also means Lola will execute third-party code on developer
workstations and in CI, during `lola install`.

That code runs as an ordinary subprocess owned by the invoking user, under both
the accepted design and the proposed one. ADR-0003 specifies that external
extensions run as separate processes and gives the reason as "protecting core
stability". The provider architecture proposed in #221 runs them through
`hashicorp/go-plugin`, which describes its own isolation as:

> Plugins can be relatively secure: The plugin only has access to the interfaces
> and args given to it, **not to the entire memory space of the process**.

That is memory isolation between host and plugin: it prevents a plugin crash
from taking down the host. It is not privilege isolation. A subprocess extension
can read `~/.ssh`, write `~/.bashrc`, and open outbound network connections,
because it runs as the user. The provider architecture design compounds this by
specifying provider-owned filesystem writes.

Shipped code has the same shape. Issue #42 records that pre- and post-install
hooks execute automatically, with the user's permissions and without a consent
prompt, and asks for a warning and a confirmation before each one. A prompt is
worth having. It also asks the person least able to answer it, at the moment
they want the install to finish, about a script they have not read. Bounding
what the script can reach is the part a prompt cannot do.

The proposed sigstore integration ADR supplies *provenance* — who published this
artifact. *Confinement* — what the artifact may do once running — is a separate
axis. ADR-0006 covers the first; this ADR proposes the second.

Extension authors must be able to use **Python, JavaScript, Go, and Rust**.

## Decision

Confinement comes from two layers, in priority order.

### 1. Effects are host-mediated (primary guarantee)

Extensions do not write files or open sockets. An extension receives input and
returns a **plan**, a declarative description of the effects it wants. The host
validates the plan against the extension's granted capabilities and performs the
effects itself.

This puts path validation, dry-run, atomic rollback, conflict detection, and
audit logging in one place in the host, where they are written once and apply to
every extension in every language and every tier.

### 2. Execution is tiered

| Tier               | Mechanism                                                                     | Languages             | Trust                                        |
|--------------------|-------------------------------------------------------------------------------|-----------------------|----------------------------------------------|
| **1 — WASM**       | `.wasm` module, WASI preview 1, run by wazero inside a self-exec shim process | Go, Rust, JavaScript  | Default. Capability-confined by the runtime. |
| **2 — Subprocess** | Ordinary process speaking the same plan protocol over a pipe                  | Any, including Python | Opt-in per extension, signature required.    |

Tier 1 is the default and the documented path. Tier 2 exists because Python
cannot be compiled to WASI preview 1 without shipping a CPython interpreter, and
Python is a required language. A tier-2 extension is still bound by the
host-mediated interface: it receives input on stdin and returns a plan on
stdout, and is granted no filesystem or network capability. Its additional risk
is that nothing *enforces* that at the OS level.

Installing a tier-2 extension requires an explicit opt-in and a valid signature.
Lola reports the tier of every installed extension in `lola ext ls`.

### 3. The shim is a self-exec

The host re-executes its own binary as a hidden `lola __extension-host`
subcommand. The child applies OS-level confinement, instantiates the WASM module
through wazero with only the granted capabilities, and communicates with the
parent over a pipe.

Self-exec rather than a separate runner binary keeps Lola a single static
artifact, which is the primary rationale of [ADR-0002: Go
Migration](go-migration.md). Process isolation and capability isolation stack: a
wazero bug does not immediately become host compromise, and the child can be
resource-limited by the OS.

On Linux the child also applies Landlock. This is defense in depth, not the
guarantee — Landlock is unavailable on macOS and Windows, and the design must be
safe without it.

### 4. Capabilities are declared and granted, never assumed

An extension declares required capabilities in its manifest. The host grants the
narrowest set that satisfies the declaration, and denies by default. A target
extension that declares no capabilities (the expected case, since it returns a
write plan) runs with none.

Credentials are held by the host and never handed to an extension. Issue #175
asks for authenticated HTTP cloning of private repositories. Under a plan, the
extension emits a `clone` intent naming the remote, and the host attaches
whatever credential it holds for that remote. A source extension therefore never
sees a token, which removes the question of whether it can be trusted with one.

## Rationale

- **The interface carries more weight than the sandbox.** A pure extension that
  describes its effects is safe in any tier. An effectful extension needs a
  perfect sandbox forever. Choosing the second is picking the harder problem.
- **wazero is the only viable embedded runtime.** It is pure Go with no cgo,
  which preserves the single static binary and one-step cross-compilation that
  motivated the Go migration. `wasmtime-go` requires cgo and supports only
  Linux/macOS/Windows on x86_64 — no Apple Silicon.
- **Confinement and provenance are complementary.** Signing tells you who wrote
  an extension; sandboxing bounds what it can do when the signer is wrong or
  compromised.
- **`lola install` runs in CI.** CI holds credentials and runs unattended, so an
  unconfined extension has both the most to reach and the least chance of being
  noticed.

## Consequences

### Positive Consequences

- A malicious tier-1 extension cannot read `~/.ssh` or reach the network,
  regardless of what its code attempts
- Path validation, dry-run, and rollback are implemented once in the host rather
  than correctly-or-otherwise in every extension
- `.wasm` modules are single content-addressable artifacts, which fits the
  `lola.sum` hashing proposed in the module package format ADR, and sigstore
  bundle signing, directly
- Dry-run (`--dry-run`) becomes trivial: execute the extension, print the plan,
  do not apply
- Extension crashes and infinite loops are contained by the shim process

### Negative Consequences

- Extension authors must target WASI preview 1 rather than writing a native
  binary, which is a real ergonomic cost relative to a drop-in script
- Python extensions get weaker enforcement than the other three languages — an
  asymmetry that must be documented honestly rather than glossed
- The plan protocol must express every effect an extension needs; an effect the
  protocol cannot describe forces an extension into tier 2
- Templating has to be placed deliberately. Issue #195 asks for inline
  templating, and template expansion is evaluation, so the protocol must say
  whether it happens inside the extension or in the host. If a plan can carry an
  unexpanded template, then expanded output reaching a path field is
  attacker-influenced input, and host-side path validation has to run after
  expansion rather than before it
- Two execution paths mean two code paths in the host and two sets of
  integration tests
- WASI preview 1 has no standard interface-type story, so the ABI is Lola's to
  define and version
- The self-exec shim adds process-spawn latency to every extension invocation

## Alternatives Considered

### Alternative 1: Unsandboxed subprocess only
- Description: extensions are ordinary binaries; security rests on signing. This
  is the status quo of both the extension architecture and provider architecture
  proposals.
- Pros: any language including shell; simplest possible authoring; no ABI to
  define
- Cons: no confinement whatsoever; a compromised signing identity or a malicious
  extension in a marketplace has full user privileges, including in CI
- Reason for rejection: provenance without confinement is a single point of
  failure. This remains available as tier 2 for cases that need it, with opt-in
  and signing.

### Alternative 2: WebAssembly Component Model (WASI 0.2)
- Description: target WASI 0.2 with WIT interfaces; first-class Python via
  `componentize-py` and JavaScript via ComponentizeJS
- Pros: typed interfaces with generated bindings; Python is first-class rather
  than an exception; the direction the ecosystem is moving
- Cons: no pure-Go runtime implements it. Reaching it requires `wasmtime-go`
  (cgo, x86_64-only) or shipping a second non-Go runner binary, forfeiting the
  single-binary property
- Reason for rejection: deferred, not rejected on merit. Revisit when a pure-Go
  component-model runtime exists; the plan protocol should not obstruct that
  migration.

### Alternative 3: Extism
- Description: an established plugin framework built on wazero, with PDKs for
  several languages
- Pros: solves memory management and host functions; proven pattern; avoids
  defining an ABI
- Cons: no Python PDK, which fails a stated requirement. Separately,
  `extism/go-sdk` — the exact component Lola would depend on — was last updated
  2025-05-14
- Reason for rejection: fails the language requirement, with a maintenance
  concern on the specific dependency as a second reason

### Alternative 4: OCI containers per extension
- Description: each extension is a container image, executed by a container
  runtime
- Pros: strong isolation; any language; familiar packaging
- Cons: requires a container runtime on every user's machine and in CI; startup
  cost; poor fit for a tool whose selling point is a single static binary
- Reason for rejection: contradicts the distribution model established by the Go
  migration

### Alternative 5: Subprocess plus OS sandboxing only
- Description: keep native binaries, confine with Landlock, `sandbox-exec`, and
  AppContainer
- Pros: any language including shell, with real confinement on Linux
- Cons: three separate platform implementations with materially different
  guarantees; the macOS and Windows stories are substantially weaker; nothing is
  portable
- Reason for rejection: the guarantee would vary by platform, which is the
  hardest kind of security property to document or reason about. Retained as a
  hardening layer on Linux.

## Implementation Notes

- Prerequisites: [ADR-0002: Go Migration](go-migration.md), [ADR-0003: Extension
  Architecture](extension-architecture.md)
- Paired design: [Extension Sandboxing
  design](../dev-guide/design/extension-sandboxing.md)
- New dependencies, vetted and approved:
  - `github.com/tetratelabs/wazero` v1.12.0 — Apache-2.0, zero transitive
    dependencies, 81 contributors, last release 2026-05-29
  - `github.com/landlock-lsm/go-landlock` v0.10.0 — MIT, Linux-only hardening.
    Single-maintainer risk accepted: the API surface is small, the layer is
    strictly additive, and abandonment means dropping the layer rather than a
    rewrite.
- This ADR constrains but does not decide the extension transport. It is
  compatible with either the stdin/stdout protocol or a gRPC provider model,
  because the plan protocol is a payload shape rather than a transport.
  Whichever transport is chosen must carry plans rather than granting effects.
- ADR-0004 (Go Project Structure, in review as #111) gains an
  `internal/extensions/host/` package for the shim. `pkg/sdk/` gains the plan
  types, which are part of the public contract.

## References

- [ADR-0003: Extension Architecture](extension-architecture.md)
- [ADR-0002: Go Migration](go-migration.md)
- ADR-0004: Go Project Structure, in review as #111
- [wazero specifications](https://wazero.io/specs/) — Core 1.0/2.0 and
  `wasi_snapshot_preview1`
- [wasmtime-go README](https://github.com/bytecodealliance/wasmtime-go) — cgo
  and x86_64-only support statement
- [hashicorp/go-plugin
  architecture](https://github.com/hashicorp/go-plugin#architecture) —
  "relatively secure" isolation claim
- [Landlock LSM](https://landlock.io/)
- Issue #42 — install hooks execute without a consent prompt
- Issue #175 — authenticated HTTP cloning for private repositories
- Issue #195 — inline templating
