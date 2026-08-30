# CLI Object Model

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

Implementation design for
[ADR: CLI Object Model](../../adr/cli-object-model.md). The ADR argues which
object each command acts on; this document is the resulting command map, the
migration, and how to check it.

Read [CLI Verb Conventions](cli-verb-conventions.md) and its
[ADR](../../adr/cli-verb-conventions.md) first. Every rename below is additive
only because that alias regime exists.

## Placement rule

One question decides where a command goes:

```text
Does it act on a module?
├── yes, in the project  → top level, object implied   lola install
├── yes, in the cache    → lola cache <verb>           lola cache add
├── yes, on disk here    → top level, authoring verb   lola init
└── no                   → lola <noun> <verb>          lola market add
```

Object type is never a flag. `--mod` and `--market` on `lola search` are the
only violations and they are retired.

## Command map

Canonical on the left, and every listed alias keeps working permanently.

| Operation | Canonical | Aliases | Acts on |
|---|---|---|---|
| Install into project | `lola install` | `add` | project |
| Remove from project | `lola uninstall` | Verb Conventions ADR §2 set | project |
| List installed | `lola list` | `ls` | project |
| Regenerate assistant files | `lola render` | `update` | project |
| Apply `.lola-req` | `lola sync` | — | project |
| Author a new module | `lola init` | `mod init` | working directory |
| Fetch into cache | `lola cache add` | `mod add` | cache |
| Drop from cache | `lola cache rm` | `mod rm`, `cache remove` | cache |
| List cached | `lola cache list` | `mod ls`, `cache ls` | cache |
| Describe cached | `lola cache info` | `mod info`, `cache show` | cache |
| Re-fetch from source | `lola cache update` | `mod update` | cache |
| Search | `lola search` | `find` | all tiers |
| Search the cache | `lola cache search` | `mod search` | cache |
| Register a marketplace | `lola market add` | — | marketplace |
| Drop a marketplace | `lola market rm` | Verb Conventions ADR §2 set | marketplace |
| List marketplaces | `lola market list` | `ls` | marketplace |
| Enable/disable | `lola market set` | — | marketplace |
| Refresh catalogs | `lola market update` | — | marketplace |

Three groups exist: top level (module, implied), `cache`, and `market`.
The remaining kinds from
[Extension Architecture](../../adr/extension-architecture.md) — `target`,
`runtime`, `source`, `scan` — become groups on the same pattern if they gain
commands.

## `install` accepts sources

Today `install` takes a module name and searches marketplaces when it misses
the cache (`src/lola/cli/install.py`). Direct sources have no such path, so a
git URL needs `lola mod add` first. That asymmetry is what the ADR's §3
removes.

Resolution order for `lola install <arg>`:

1. `@marketplace/module` — explicit marketplace, unchanged
2. Present in the cache — install from cache, unchanged
3. Parses as a source that a `SOURCE_HANDLER` accepts — fetch into the cache,
   then install
4. Found in exactly one enabled marketplace — fetch, then install, unchanged
5. Found in several — prompt, unchanged
6. Otherwise — error naming both what was searched and the source forms
   accepted

Step 3 is the new one and it must come *after* the cache check, so that a
cached module named like a path still resolves to the cached copy. It reuses
`parsers.SOURCE_HANDLERS` rather than re-implementing detection; whatever
`lola cache add` accepts, `lola install` accepts, with no second list to drift.

A source that fetches but fails to install leaves the module cached. That is
the same end state as `lola cache add` and is worth saying in the error,
because the retry is then `lola install <name>` and not the URL again.

Check #217 ("install only works the first time") against step 2 before
building step 3. If it is a cache-hit bug, it lives in the code path this
change reorders.

## Renaming without breaking

`mod` and `update` are the two spellings in the wild. Both survive as aliases,
so the migration is documentation and defaults rather than behaviour.

| Concern | Handling |
|---|---|
| Existing scripts | Aliases resolve identically, no warning on the alias path |
| `.lola-req` files | Unaffected — a declarative file, no verbs |
| Shell completion | Offers canonical names; aliases complete but rank below |
| `--help` | Lists every accepted spelling, per Verb Conventions ADR §5 |
| Docs and tutorials | Must switch to canonical names in the same release |

`lola mod search` is currently documented as deprecated in favour of
`lola search --mod`. That deprecation reverses: `--mod` is the Grammar C
violation, so `lola cache search` becomes canonical and `mod search` becomes a
plain alias rather than a deprecated one.

## Tier vocabulary

One word per tier, in code, docs and error messages:

| Tier | Path | Word | Never |
|---|---|---|---|
| Source | git, archive, folder, marketplace | source | origin, upstream |
| Machine-global | `~/.lola/modules/` | cache | registry, store, global |
| Project | `<project>/.lola/modules/` | project | local, workspace |

"Registry" is retired for the local tier: `npm config get registry` returns
`https://registry.npmjs.org/`, so the word means the remote everywhere else,
and Lola's remote is a marketplace.

Two files disagree today and both change:

- `docs/dev-guide/architecture.md` — "Local Cache" (keep, drop "Local")
- `docs/concepts/what-is-lola.md` — "GLOBAL REGISTRY" (change to "CACHE")

`architecture.md`'s diagram also labels two different arrows `lola install`
(markets → cache, and cache → project). Under the ADR's §3 the first is no
longer a separate user action, so that arrow becomes unlabelled or is folded
into the source node.

## Verification

- `lola cache add <git-url>` and `lola mod add <git-url>` produce identical
  state
- `lola install <git-url>` on an empty cache leaves the module both cached and
  installed
- `lola install <name>` with `<name>` cached does not hit the network, even if
  a file of that name exists in the working directory
- `lola install ./does-not-exist` errors naming both the marketplaces searched
  and the accepted source forms
- `lola render` and `lola update` produce identical state
- `lola init` and `lola mod init` both scaffold into the working directory
- `lola cache bogsu` exits non-zero rather than listing, per
  [CLI Verb Conventions](cli-verb-conventions.md)
- `--help` for every renamed command lists the old spelling
- No occurrence of "registry" referring to `~/.lola/modules/` remains in
  `docs/` or in user-facing strings under `src/`
- `mkdocs build` succeeds
