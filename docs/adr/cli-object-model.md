# ADR: CLI Object Model

**Status**: Proposed
**Date**: 2026-08-26
**Last Updated**: 2026-08-26
**Authors**: trevor-vaughan
**Reviewers**:

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

## Context

Readers of `dev-guide/architecture.md` cannot work out why some operations
live under `lola mod` and some live at the top level. The reflex is to reach
for `lola mod install`, which does not exist, and the docs do not explain the
absence.

[CLI Verb Conventions](cli-verb-conventions.md) settled how operations are
*spelled*. It explicitly declined to settle what they operate *on*, twice: §4
routes `remove` but records that "the underlying split is the same one #48
raises about registry and cache", and §3 leaves `lola update` with "a meaning
no other manager would predict". This ADR is the record those deferrals point
at.

### Lola runs three grammars at once

**A — `lola <verb>`, object implied.**
`install`, `uninstall`, `update`, `list`, `sync`

**B — `lola <noun> <verb>`.**
`mod add|init|rm|ls|info|update|search`,
`market add|ls|set|rm|update`

**C — `lola <verb> --<noun>`.**
`search --mod`, `search --market`

Grammar A works only because the object is silently assumed to be a module.
`lola mod search` is already a deprecated alias for `lola search --mod`, so one
command has been migrated from B to C without any written rule saying that is
the direction of travel.

### What the other managers actually do

Verbs run with `--help` on this box; a command is a noun-first group when
`<manager> <noun> --help` exits zero and lists subcommands.

| Manager | Implicit primary object | Noun-first groups |
|---|---|---|
| dnf | `dnf install foo` | 4 — `group`, `module`, `history`, `mark` |
| npm | `npm install foo` | 9 — `cache`, `config`, `pkg`, `org`, … |
| pip | `pip install foo` | 3 — `cache`, `config`, `index` |
| podman | `podman run` (alias) | canonical — `container`, `image`, … |
| gh | **none** | all — `pr`, `issue`, `repo`, `alias`, … |

npm's nine are `cache`, `config`, `team`, `org`, `token`, `profile`, `pkg`,
`owner` and `access`.

Four of five accept an implicit primary object at the top level *and* carry
noun-first groups for secondary objects. **Lola's A+B mixture is the majority
pattern, not a defect.** Grammar C is the outlier: no surveyed manager selects
an object type with a flag.

### What that tier is called elsewhere, and what verbs it takes

| Manager | Name | Verbs it accepts |
|---|---|---|
| dnf | not exposed | `clean {metadata,packages,dbcache,expire-cache,all}` |
| npm | `cache` | `add`, `clean`, `ls`, `verify` |
| pip | `cache` | `dir`, `info`, `list`, `remove`, `purge` |
| **lola** | **`mod`** | `add`, `rm`, `ls`, `info`, `update`, `init`, `search` |

Two findings follow, and both are checkable rather than argued:

1. **No manager puts `install` on the cache namespace.** `npm cache add` fills
   the cache; `npm install` installs. They are different operations with
   different names. So `lola mod install` is correctly absent — but nothing in
   the CLI communicates that, because the group is named after the *domain
   noun* (`mod`) rather than after the *tier* it manages.

2. **"Registry" means the remote, everywhere else.**
   `npm config get registry` returns `https://registry.npmjs.org/`. Lola's
   `concepts/what-is-lola.md` labels the *local* directory
   `~/.lola/modules/` the "GLOBAL REGISTRY", while `dev-guide/architecture.md`
   calls the same path the "Local Cache". The two docs disagree, and the
   losing one uses the industry's word for the tier Lola calls a marketplace.
   `cli-reference/index.md` sits on the losing side too, describing
   `lola search` as covering "the local registry" and `--mod` as scoping to
   "the local module registry".

### The tier is only half transparent

`src/lola/cli/install.py` searches enabled marketplaces when a module is not
found locally, so `lola install <name>` populates the cache by itself. There is
no equivalent for direct sources: a git URL, archive or folder must go through
`lola mod add` first, because `install` takes a module name and not a source.
`architecture.md` shows this as two arrows into the cache but describes it as
one flow — "added (via `lola mod add` or through a market install)".

That asymmetry is the actual cause of the confusion. A cache you must populate
by hand for half your sources is not experienced as a cache; it is experienced
as a second install step, which is exactly what makes `lola mod install` feel
like it should exist.

## Decision

### 1. The object model is hybrid, and this is the rule

- The **module is the primary object.** Operations on modules are top-level
  verbs with the object implied: `lola install`, `lola uninstall`, `lola list`.
- **Every other object gets a noun-first group**: `lola market <verb>`, and the
  remaining kinds from [Extension Architecture](extension-architecture.md) as
  they gain commands.
- **Object type is never selected with a flag.** Grammar C is retired.
  `lola search --mod` / `--market` become scope arguments on the search itself,
  and `lola mod search` is un-deprecated as the noun-first form.

A new command answers one question first: does it act on a module, or on
something else? That determines its position before its name is chosen.

### 2. The three tiers are named source, cache and project

| Tier | Path | Name |
|---|---|---|
| Source | git, archive, folder, marketplace | **source** |
| Machine-global | `~/.lola/modules/` | **cache** |
| Project | `<project>/.lola/modules/` | **project** |

"Registry" is retired for the local tier. It is the industry's word for the
remote, and Lola already has a word for the remote. Every source handler in
`src/lola/parsers.py` copies into the cache directory rather than referencing
the original, so the tier is derived state in every case and "cache" is
accurate as well as conventional.

This resolves the registry/cache half of #48. It does not decide
marketplace-versus-repository, which is a separate question in the same thread.

### 3. The cache tier is made uniformly transparent

`lola install` accepts any source `lola mod add` accepts. Installing from a git
URL, archive or folder fetches into the cache and then installs, exactly as the
marketplace path already does.

This is the load-bearing change. Once the cache never has to be populated by
hand, it is a cache in behaviour and not only in name, and the group managing
it stops looking like a place where `install` belongs. It also answers #234.

### 4. `lola mod` is renamed to `lola cache`, with `mod` kept forever

Under the CLI Verb Conventions alias regime the rename is additive: both
spellings work everywhere, permanently, the way `podman run` and
`podman container run` both work. `lola cache add` makes the tier explicit, and
nobody types `lola cache install`.

The current group mixes three different objects, so the rename is also a split.
`lola mod init` writes to `Path.cwd()` — it authors a new module and never
touches the cache. It moves to `lola init`, matching `npm init` and `cargo new`.

| Today | Acts on | Becomes |
|---|---|---|
| `lola mod add\|rm\|ls\|info\|update` | the cache | `lola cache <verb>` |
| `lola mod init` | the working directory | `lola init` |
| `lola mod search` | the cache | `lola cache search` |

### 5. Each `update` names its tier

`lola update`, `lola mod update` and `lola market update` are three unrelated
operations sharing one word. CLI Verb Conventions excluded `update` from
cross-manager aliasing because the managers disagree about its meaning; Lola
disagrees with itself three ways, which is worse.

Under §2 each `update` is qualified by the tier it acts on: `lola cache update`
re-fetches from source, `lola market update` refreshes catalogs. Top-level
`lola update` regenerates assistant files from the project tier, which is the
divergence CLI Verb Conventions §3 named and declined to fix. It is renamed to
`lola render`, and `update` is kept as an alias so nothing breaks.

### 6. Extensions inherit the rule

Extension Architecture defines `target`, `repo`, `runtime`, `source` and
`scan`, and no command kind, so extensions cannot contribute commands today.
When they can, each kind is a noun-first group under §1. Fixing the grammar
before that gate opens is cheaper than reconciling five extension authors'
conventions after.

The `repo` kind is proposed for renaming to `marketplace` on the
`docs/marketplace-terminology` branch. Either identifier reads the same way
under §1, so this section does not depend on which name lands.

## Rationale

- **The hybrid grammar is empirically the norm.** Four of five managers do what
  Lola does. Rewriting the surface to be uniformly noun-first (`gh`) or
  uniformly flat would trade a conventional shape for an unconventional one.
- **The confusion is a naming failure, not a structural one.** `lola mod` is
  named for the domain noun, so it reads as "everything about modules" and
  invites `mod install`. `npm cache` and `pip cache` are named for the tier,
  and nobody reaches for `npm cache install`.
- **"Registry" is actively wrong, not merely inconsistent.** It names the local
  tier with the word npm uses for the remote — which is the tier Lola calls a
  marketplace. Two docs disagreeing is a drift bug; the loser being backwards
  relative to the industry is an architecture bug.
- **Half-transparency is what makes the split visible.** Marketplace installs
  need one command and direct sources need two. Users generalise from whichever
  they met first, and one of the two groups is always surprised.
- **The rename is cheap under CLI Verb Conventions.** Aliases make it additive.
  The cost is documentation choosing one voice, which is a cost that ADR
  already accepted.
- **One group holding three objects is the root cause.** `mod init` writing to
  the working directory while its siblings write to `~/.lola/modules/` is the
  clearest evidence that `mod` is a bag rather than a namespace.

## Consequences

### Positive Consequences

- The reflex to type `lola mod install` disappears, because `lola cache install`
  is self-evidently wrong
- `lola install <git-url>` works, removing the two-step asymmetry and answering
  #234
- #48's registry/cache half is settled with evidence rather than preference
- CLI Verb Conventions §4's deferred model question has an answer, so its
  `remove` routing rests on a documented model
- The three-way `update` collision is resolved
- The Extension Architecture kinds have a grammar to inherit before they need
  one

### Negative Consequences

- This is the largest user-visible rename proposed so far. Aliases keep every
  old spelling working, but tutorials, the CLI reference and every issue thread
  citing `lola mod add` now teach a non-canonical form
- `lola update` → `lola render` renames the command most users type most often.
  The alias makes it safe, not invisible
- Two names for one group is a documentation tax for as long as both are
  accepted, which under the CLI Verb Conventions rules is forever
- Making `install` accept sources widens its argument surface, and a mistyped
  module name that looks like a path now fails differently
- §5 asserts `lola render` is the better name for regenerating assistant files
  without surveying render/generate/apply/sync the way §1 surveys grammar. It
  is the weakest-evidenced decision here
- The CLI Verb Conventions §2 table lists `lola mod list` and `lola mod info`
  as canonical. If both ADRs land, that table needs amending

## Alternatives Considered

### Alternative 1: Add `lola mod install` and keep everything else

- Description: Honour the reflex directly by aliasing `lola mod install` to
  `lola install`.
- Pros: Smallest possible change; the command people reach for works.
- Cons: Puts a project-tier operation inside a cache-tier namespace, so the
  group means two tiers at once. No surveyed manager does this.
- Reason for rejection: It removes the error message without removing the
  confusion, and makes the model harder to explain afterwards.

### Alternative 2: Go uniformly noun-first, like `gh`

- Description: `lola mod install`, `lola mod list`, `lola market add`, with no
  implicit object anywhere.
- Pros: One rule, no exceptions; the reflex is correct by construction.
- Cons: One of five surveyed managers works this way, and none of the package
  managers Lola names as models do. `lola mod install` is longer than every
  equivalent it competes with.
- Reason for rejection: Consistency bought by leaving the convention Lola's own
  analogy invokes.

### Alternative 3: Hide the cache entirely, like dnf

- Description: Delete the group. `lola install <source>` does everything;
  cache maintenance is `lola clean`.
- Pros: Simplest surface; matches the DNF analogy `architecture.md` opens with.
- Cons: Destroys real workflows — pinning, offline install and inspecting what
  is cached all need the verbs. npm and pip both expose the tier for this
  reason.
- Reason for rejection: dnf can hide its cache because nothing else uses it.
  Lola's tier is shared across projects, so it is a thing users reason about.

### Alternative 4: Rename the tier only, leave the commands alone

- Description: Fix `registry` → `cache` in the docs, keep `lola mod`.
- Pros: Documentation-only; no CLI change and no alias tax.
- Cons: Leaves the group named after the domain noun, which is the thing that
  invites `mod install`. Leaves the half-transparent cache.
- Reason for rejection: It fixes the contradiction two docs have with each
  other without fixing what either of them describes.

### Alternative 5: Keep `update` at top level

- Description: Accept the three-way collision and disambiguate in help text.
- Pros: No rename of the most-typed command.
- Cons: Help text cannot fix a word meaning three things; the user has to read
  it at the moment they were confident they did not need to.
- Reason for deferral: Lower stakes than §1–§4. If §5 is contentious it can be
  split into its own ADR without weakening the rest.

## Implementation Notes

Ordered so that each step is useful alone and nothing is a prerequisite for a
decision that has not been made.

1. **Documentation first, no code.** Reconcile `architecture.md`,
   `what-is-lola.md` and `cli-reference/index.md` on `cache`, relabel the
   duplicated `lola install` arrow in the `architecture.md` diagram, and state
   the market-install shortcut explicitly. This is the part that fixes today's
   confusion, and it is reversible.
2. **Make `install` accept sources** (§3). Behavioural, additive, and the change
   that makes the rest read as tidying rather than churn. Check #217 against it
   first — "install only works the first time" may be a symptom of the same
   asymmetry.
3. **Add the `cache` spelling** (§4) with `mod` aliased. Update the CLI
   reference in the same release or it teaches the wrong canonical form.
4. **Split `mod init` to `lola init`** (§4).
5. **Rename `update` to `render`** (§5), last, because it is the weakest-
   evidenced and the easiest to drop.
6. **Retire Grammar C** (§1) whenever `search` is next touched.

Depends on CLI Verb Conventions for the alias mechanism: every rename here is
additive only because that ADR's alias regime exists. If it is rejected, steps
3–5 are breaking changes and must be reconsidered.

The verb tables in Context were produced on CentOS Stream 10 with dnf 4.20.0,
npm 11.9.0, pip 23.3.2, podman 6.1.0 and gh 2.97.0.

## References

- Issue #48 — mental model and terminology, including registry versus cache
- Issue #234 — one-command install
- Issue #217 — install only works the first time
- Issue #137 — `list` and `remove` aliases (answered by CLI Verb Conventions)
- [ADR: Extension Architecture](extension-architecture.md) — the five
  extension kinds that inherit §1
- [ADR: CLI Verb Conventions](cli-verb-conventions.md) — verb spellings and the
  alias regime this ADR depends on; §4 defers the model question answered here
- [Design: CLI Object Model](../dev-guide/design/cli-object-model.md)
- [`npm cache`](https://docs.npmjs.com/cli/commands/npm-cache) and
  [`pip cache`](https://pip.pypa.io/en/stable/cli/pip_cache/) — the two
  managers whose local tier matches Lola's
