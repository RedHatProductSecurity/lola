# ADR: Support the Agent Plugins Format

**Status**: Accepted
**Date**: 2026-08-13
**Last Updated**: 2026-08-14
**Authors**: Lola maintainers
**Reviewers**: Lola maintainers

## Context

Agent Plugins 1.0 defines a portable package root containing a strict
`plugin.json` manifest, Agent Skills under `skills/`, and MCP configuration in
`mcp.json`. Lola's native module layout has the same portable concepts but uses
different metadata and MCP filenames. Lola also supports commands, agents, and
instructions, which are deliberately outside the portable specification.

Requiring authors to repackage the same skills and MCP servers for Lola adds
friction and prevents Lola-authored modules from being consumed directly by
other conformant clients.

## Decision

Lola detects `plugin.json` at a module source root and adapts Agent Plugins 1.0
into its existing `Module` installation contract. The manifest's `name` is the
module identity. Lola validates the manifest locally without retrieving its
schema and discovers skills and MCP servers only from their fixed portable
locations.

Manifest validation follows the v1.0.0 closed schema: the canonical
`$schema` value is required, unsupported versions are rejected before
discovery, and unknown top-level fields are reported as warnings then
ignored. Unknown extension namespaces are ignored without validating their
contents, as the specification requires.

Lola owns the stable `dev.getlola` extension namespace. Commands, agents, and
instructions emitted by Lola live under the top-level `dev.getlola/` directory
and are declared by plugin-relative paths in the manifest extension object.

Lola also reads `commands`, `agents`, and `instructions` path declarations from
known client namespaces. In compatibility order, Lola checks:

1. `com.anthropic.claude`
2. `com.anthropic.claude-code`
3. `com.cursor.editor`
4. `com.github.copilot`
5. `com.google.gemini-cli`
6. `com.openai`
7. `com.openai.codex`
8. `ai.opencode`
9. `dev.getlola` (authoritative)

Unknown namespaces are ignored without validation, as required by Agent
Plugins. When component names collide, later namespaces in this order win,
so `dev.getlola` is authoritative. This collision precedence is Lola-specific:
Agent Plugins 1.0 deliberately defines no cross-namespace precedence rules.

`lola mod init` emits the portable package root directly by default, without a
native `module/` wrapper. The legacy layout remains available via
`--format lola`.

## Rationale

Keeping format handling at the model boundary lets every existing target reuse
the same installation and conversion behavior. Explicit source paths preserve
client-owned layouts without copying or repackaging source content. A dedicated
adapter also contains the stricter Agent Plugins validation and failure rules so
native Lola modules retain backward compatibility.

## Consequences

### Positive Consequences

- Agent Plugins packages install directly through Lola.
- Lola-authored packages expose a portable skills and MCP core.
- Client-specific commands and agents can use Lola's existing target
  translators.
- Invalid skills and MCP entries fail independently as required by the spec.
- MCP failures respect two boundaries: an invalid or incompatible root
  `mcp.json` disables MCP for the entire plugin, while invalid server
  entries, unsupported transports, and connection failures skip only the
  affected server.

### Negative Consequences

- Lola must maintain compatibility mappings for client-owned namespaces.
- Portable MCP paths and placeholders are never rewritten in the source
  package. Install and update operations rebase component paths onto the
  project-local package copy; `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` are
  expanded only when that copy is materialized, and the per-module
  `PLUGIN_DATA` directory is preserved across plugin updates.
- `plugin.json.name` can differ from a repository name, so registry directories
  must be aligned after fetching.

## Alternatives Considered

### Treat Agent Plugins as Filename Aliases

- Description: Read `plugin.json` as optional metadata and treat `mcp.json` as
  `mcps.json`.
- Pros: Small implementation.
- Cons: Misses schema, containment, namespace, and per-component failure rules.
- Reason for rejection: It would accept packages without conforming to the
  published format.

### Repackage on Import

- Description: Copy portable packages into Lola's native `module/` layout.
- Pros: No changes to the common model contract.
- Cons: Duplicates source content and loses the package's canonical layout.
- Reason for rejection: Direct consumption is a core requirement of issue 232.

## Implementation Notes

The adapter lives in `src/lola/agent_plugins.py`. It resolves every component
path against the resolved plugin root and rejects traversal, symlink, or
junction escapes before constructing `Module` paths or invoking installation.
The common `Module` model stores explicit component paths and normalized MCP
data. Install and update operations rebase those paths onto the project-local
package copy.

## References

- https://github.com/LobsterTrap/lola/issues/232
- https://agent-plugins.org/specification
