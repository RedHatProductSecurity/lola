# Claude Code Adapter

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

Implementation detail for
[ADR: Polyglot Format Handling](../../adr/polyglot-formats.md), and the first
adapter written under it. The ADR owns the decision and
[polyglot-formats.md](polyglot-formats.md) owns the IR, normalisation,
precedence and the export pipeline. This document owns Claude Code's field
mappings and what an export to Claude's formats may and may not claim.

Every shape below was read from installed packages rather than from a
specification, so treat it as an observation of the format in use. The
authoritative schema is at
`https://anthropic.com/claude-code/marketplace.schema.json`, which
`marketplace.json` names in its own `$schema` field.

## Package manifest

`.claude-plugin/plugin.json`. Observed across 26 installed plugins:

| Field | Seen in | Maps to |
|-------|---------|---------|
| `name` | 26 / 26 | module identity |
| `description` | 26 / 26 | module description |
| `author` | 26 / 26 | object with `name`, optional `email` |
| `version` | 9 / 26 | module version; absent means unversioned |
| `homepage` | 3 / 26 | metadata only |
| `repository` | 2 / 26 | metadata only |
| `license` | 2 / 26 | metadata only |
| `keywords` | 2 / 26 | search terms |

No observed plugin declared component paths. Commands, agents and skills are
found by convention, which is how Lola already discovers module content, so
discovery needs no new mechanism — only the directory names Claude Code uses.

Absent fields are the common case rather than the exception. Two thirds of real
plugins carry no `version`. Treat everything but `name` as optional and do not
reject a manifest for omitting metadata.

## Catalog manifest

`.claude-plugin/marketplace.json`. Top-level keys observed: `$schema`, `name`,
`owner`, `description`, `plugins`, `renames`.

Each entry in `plugins` carries `name`, `description`, `author`, and a `source`,
with optional `category` and `homepage`. In the official catalog of 286 entries,
`source` takes three shapes:

| Shape | Count | Meaning | Existing Lola handler |
|-------|-------|---------|----------------------|
| `{"source": "url", "url": ...}` | 150 | fetch from a URL | url / archive |
| `{"source": "git-subdir", "url", "path", "ref", "sha"}` | 83 | a subdirectory of a git repo at a pinned ref | git with `#subdirectory=` |
| bare string | 53 | shorthand for a URL | url |

All three map onto source handling Lola already has. `git-subdir` is the one
worth care: it carries both `ref` and `sha`, and the `sha` is what should be
recorded for integrity. It also collides with the naming problem in issue #177,
where several `#subdirectory=` entries share one repository URL.

`renames` appears at catalog level and records plugins that changed name.
Reading it lets an installed module survive an upstream rename instead of
looking like a removal followed by an unrelated addition.

## Comparison with Agent Plugins

Lola already reads the vendor-neutral format. The differences that matter here:

| | Agent Plugins | Claude Code |
|---|---|---|
| Package manifest path | `plugin.json` at root | `.claude-plugin/plugin.json` |
| Catalog manifest path | `.agents/plugins/marketplace.json` | `.claude-plugin/marketplace.json` |
| Catalog top level | `interface`, `name`, `plugins` | `name`, `owner`, `description`, `plugins`, `renames` |
| Per-entry extras | `policy.installation`, `policy.authentication` | `category`, `homepage` |
| Extension mechanism | reverse-domain namespaces | none observed |

The paths never collide, so detection is unambiguous. A package carrying both is
normal rather than a conflict: `superpowers` ships both.

Agent Plugins `policy` has no Claude equivalent. When emitting Agent Plugins
output from a Lola module there is nothing to derive it from, so omit it rather
than defaulting it — a wrong `authentication` value is worse than a missing one.

## Precedence

Claude's manifest sits third, behind `lola.yml` and the Agent Plugins root
`plugin.json`. The rule itself and its reporting are general and live in
[polyglot-formats.md](polyglot-formats.md#precedence).

`superpowers` is the fixture that exercises it, since it ships both an Agent
Plugins manifest and a Claude one, and the two paths never collide.

## Ingest and export mapping

The same table read in both directions. Ingest fills IR fields from the
manifest; `lola mod export --target claude-code` fills the manifest from the
IR.

| IR field | `.claude-plugin/plugin.json` |
|----------|------------------------------|
| `name` | `name` |
| `description` | `description` |
| `version` | `version` |
| `author` | `author.name`, `author.email` |
| `license` | `license` |
| `homepage` | `homepage` |
| `repository` | `repository` |
| `keywords` | `keywords` |
| `formats.claude-code.category` | `category` (catalog entries) |
| `targets` | **no equivalent** |
| install hooks | **no equivalent** |

`category` has no first-class IR field because nothing outside Claude's catalog
uses it, so it round-trips through `formats.claude-code`. Everything above it
recurs across formats and is promoted.

`targets` is the field that makes a Lola module install to five assistants, and
no client format has a home for it. An exported manifest is therefore a
narrower artifact than the module it came from, and export says so once rather
than implying fidelity it cannot deliver.

Claude's package manifest requires only `name`, so export to this format never
fails for a missing required field. Two thirds of the corpus omits `version`,
and an export that omits it is well-formed.

Claude declares no vendor extension mechanism, and Lola does not invent one.
See [polyglot-formats.md](polyglot-formats.md#what-export-does-not-claim) for
why.

## Schema handling

Do not fetch `https://anthropic.com/claude-code/marketplace.schema.json` at
install time. An installer that makes a network call to validate is an installer
that fails offline and leaks what is being installed.

Vendor a copy, validate against it, and refresh on a deliberate cadence. Unknown
fields warn and are ignored, which is what the Agent Plugins ADR already does
and what lets a catalog add a field without breaking every older Lola.

## Testing

Fixtures come from real packages. Hand-written examples encode assumptions
rather than testing them.

Adapter-specific cases:

- Every `source` shape in the official catalog resolves: bare string, `url`, and
  `git-subdir` with `ref` and `sha`
- A `git-subdir` entry records the `sha` in `.lola-origin` alongside the `ref`
- A manifest with only `name`, `description` and `author` is accepted, since
  that is two thirds of the corpus
- A catalog `renames` entry maps an installed module to its new name rather than
  reporting a removal
- `category` survives a round-trip through `formats.claude-code`
- Exporting `.claude-plugin/` from a module with `targets` set omits `targets`
  and reports it

Precedence, unknown-field handling, round-trip equality and the offline
validation requirement are general and tested against the list in
[polyglot-formats.md](polyglot-formats.md#testing). The 286-entry catalog is
the corpus for both.
