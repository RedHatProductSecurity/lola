# Polyglot Format Handling

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

Implementation detail for
[ADR: Polyglot Format Handling](../../adr/polyglot-formats.md). The ADR owns
the decision; this document owns the IR schema, the normalisation algorithm,
the capability grants, and what round-trip means.

Per-format field mappings live with each adapter. The first one is the
[Claude adapter](claude-adapter.md).

## The intermediate representation

`lola.yml` is what every adapter produces and every template consumes.

| Field         | Type                             | Required | Source                     |
|---------------|----------------------------------|----------|----------------------------|
| `name`        | string                           | yes      | module identity            |
| `description` | string                           | no       |                            |
| `version`     | string                           | no       | absent means unversioned   |
| `author`      | object: `name`, optional `email` | no       |                            |
| `license`     | SPDX identifier string           | no       |                            |
| `homepage`    | URL string                       | no       |                            |
| `repository`  | URL string                       | no       |                            |
| `keywords`    | list of strings                  | no       | search terms               |
| `targets`     | list of target ids               | no       | the multi-assistant matrix |
| `formats`     | map of format id to object       | no       | passthrough residue        |

Only `name` is required. Two thirds of the 26 surveyed Claude plugins carry no
`version`, and a manifest is never rejected for omitting metadata.

`targets` is the field that makes a Lola module install to five assistants. No
client format has a home for it, which is the concrete reason the ADR declines
to adopt one of them as native.

### The `formats` passthrough

Fields an adapter reads but the IR has no first-class home for are preserved
verbatim, keyed by format id:

```yaml
formats:
  claude-code:
    category: workflow
    renames: {old-name: superpowers}
  agent-plugins:
    policy: {installation: ..., authentication: ...}
```

Rules:

- An adapter writes only under its own format id. Cross-writing is a bug.
- Values are stored as read. No coercion, no defaulting, no normalisation.
- The exporter for a format reads that format's block back and nothing else. A
  Claude export never consults the `agent-plugins` block.
- A field promoted to first class in a later release moves out of `formats` and
  the adapter stops writing it there. That is a breaking change to the cached
  representation and needs a cache version bump.

The name is `formats`, not `x-format`. The Claude adapter argues against
`x-`-prefixed vendor extensions in someone else's schema; foreign data held
inside Lola's own schema is a different thing, and the name should not blur the
two.

## `.lola-origin`

Written beside the normalised `lola.yml` in the module cache. Records what
normalisation decided, so none of it has to be re-derived or remembered.

```yaml
format: claude-code                  # which adapter ran
manifest: .claude-plugin/plugin.json # which file won precedence
others_present:                      # what else was there, and ignored
  - .agents/plugins/marketplace.json
sha: 4f2c1ab...                      # from the catalog entry, where supplied
scan:
  extension: unicode-guard
  verdict: clean
  at: 2026-08-26T14:02:11Z
```

`sha` comes free from Claude's `git-subdir` source shape, which supplies it for
83 of the 286 entries in the official catalog. Recording it costs nothing and
is the integrity pin APM's lockfile pays for separately.

## Normalisation

Runs once, on `lola mod add`. The source package is never mutated.

1. Fetch content into the module cache through the existing `source` handlers.
2. Detect every recognised manifest at the source root.
3. Apply precedence. Record the winner and the others in `.lola-origin`.
4. Run the `scan` extension over the fetched content. A failed scan aborts the
   add; the cache entry is not written.
5. Run the winning format's adapter. Mapped fields become IR fields; unmapped
   fields go to `formats` under that adapter's id.
6. Write `lola.yml` and `.lola-origin` into the cache entry.

`lola mod convert <path>` runs steps 2 through 5 against a package in place and
writes `lola.yml` into it. It is the only operation that writes into a package
Lola did not fetch, and it runs only when invoked directly.

### Precedence

First match wins. Nothing merges.

```text
1. lola.yml                      Lola's own
2. plugin.json (at root)         Agent Plugins
3. .claude-plugin/plugin.json    Claude Code
```

Merging would make the resulting module depend on which formats a package
happened to ship, which is not reproducible.

Report the choice on every add: `using .claude-plugin/plugin.json (2 other
manifests present)`. Someone who adds a Claude manifest to a package that
already has `lola.yml` and sees no change needs to be told why.

### Round-trip

`import <format>` followed by `export <format>` is **semantically identical**,
not byte-identical. Key order, indentation and whitespace are not preserved;
parsed-equal is the test.

Byte-identity is a promise the YAML and JSON serialisers cannot keep, and
asserting it produces a test that fails for reasons nobody cares about.

The claim covers **manifests only**. Skill bodies are copied verbatim and are
not part of it.

## Templates

Two populations, one engine, one dialect. The capability grant varies by
origin.

|              | Target templates            | Content templates                                               |
|--------------|-----------------------------|-----------------------------------------------------------------|
| Author       | Lola, or a target extension | module publisher                                                |
| Arrives from | the installed toolchain     | a catalog                                                       |
| Renders      | IR → client manifest        | per-target variation in skill markdown                          |
| Grant        | trusted, host-side          | empty                                                           |
| Confinement  | none needed                 | tier-1 WASM, Extension Sandboxing (proposed separately)         |

A content template that requests any capability is refused by the host, not
contained and then run. Extension Sandboxing's guarantee is that effects are
host-mediated: the template returns a plan, the host checks it against the
grant, and an empty grant means every requested effect is denied.
`{{ exec ... }}` in a catalog-sourced template produces a refusal, not a
subprocess.

Keeping one dialect and varying the grant puts the restriction in a single
enforcement point. A second reduced dialect for untrusted templates would be a
second thing to write, document and keep in sync with the first.

## Export

`lola mod export --target <id>` renders one format. `--all` renders every
format in the module's `targets`. Neither has a bare default.

The render pipeline is structured, never textual:

```text
IR + formats[id]  →  template  →  data structure
                                       │
                                       ├→ marshal (JSON or YAML)
                                       ├→ validate against vendored schema
                                       └→ write
```

A template produces a data structure, so it cannot emit a stray comma into
another vendor's manifest. Invalid structure fails at marshal. Unknown fields
warn at validate and are written, because a client adding a field should not
break an older Lola.

Where a target format supports a reference, emit a reference rather than an
inlined copy. Inlined content is the copy that drifts.

### Required fields

Where a target format requires a field the module does not carry, export
refuses and names both the field and the target:

```text
cannot export superpowers to codex: format requires `version`,
module has none. Set it in lola.yml or export to a format that
does not require it.
```

Lola does not synthesise a value. A `0.0.0` version means something false
downstream, and a wrong value is worse than a missing one.

### What export does not claim

An exported manifest is a narrower artifact than the module it came from.
`targets` and install hooks have no home in any client format, and export says
so once rather than implying fidelity Lola cannot deliver.

Do not invent vendor extensions to carry what does not fit. An `x-lola-targets`
key in someone else's schema is a private convention wearing a standard's
clothes, and it will not survive their next schema revision.

## The adapter contract

A target extension supplies four things. Adding one leaves the adapter
dispatch, the normalise step, the IR schema and the export driver unchanged.

| Artifact             | Direction     | Contract                                            |
|----------------------|---------------|-----------------------------------------------------|
| ingest adapter       | manifest → IR | maps known fields, routes the rest to `formats[id]` |
| export template      | IR → manifest | returns a data structure, never text                |
| target descriptor    | —             | content paths, required fields, capability grant    |
| conformance fixtures | —             | a real package and its expected round-trip          |

Any core change a new target needs is a finding about the extension interface,
and belongs in a note on Extension Architecture rather than in a quiet patch.

## Testing

Fixtures come from real packages. Hand-written examples encode assumptions
rather than testing them. The official Claude catalog and its 286 entries are
the corpus; `superpowers` is the ready-made dual-catalog case, since it ships
both `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json`
for the same package.

Precedence is the exception. All 26 packages surveyed carry
`.claude-plugin/plugin.json` and none carries a root `plugin.json`, so the
corpus never reaches the second rung of the ladder. Build that fixture by hand
and mark it synthetic.

- Precedence resolves to Agent Plugins for a package carrying both, reports the
  other, and records both in `.lola-origin` (synthetic fixture)
- Precedence is reported even when only one manifest is present
- A manifest carrying only `name`, `description` and `author` is accepted
- An unknown top-level field warns, lands in `formats`, and does not fail the
  parse
- Round-trip: `import claude → export claude` is parsed-equal, including the
  `formats` residue
- An adapter writing outside its own `formats` id fails the test suite
- Export to a format requiring an absent field fails and names field and target
- Export of a module with `targets` set reports that `targets` was not carried
- A content template requesting any capability is refused
- `mod convert` writes `lola.yml` and leaves every other file in the package
  untouched
- Adding a target extension leaves core unchanged
- Validation runs with no network access

Per-format coverage is published as a generated conformance statement rather
than asserted in prose: each requirement marked active, skipped or xfail, with
a written waiver for every skip.
