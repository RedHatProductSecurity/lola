# ADR: CLI Verb Conventions

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

Lola's users arrive from other package managers and type what those managers
taught them. Issue #137 asks for `list` and `remove` alongside `ls` and `rm`.
Issue #157 asks for `ls` to be the default under `lola mod`. Both are the same
request: the command someone already knows should work.

Whether that request is worth honouring can be settled with evidence rather than
taste. Running each verb with `--help` against dnf 4.20.0, npm 11.9.0,
pip 23.3.2, cargo 1.96.1 and gem 3.6.9:

|       | `install` | `uninstall` | `remove` | `rm` | `erase` | `add` |
|-------|-----------|-------------|----------|------|---------|-------|
| dnf   | yes       | **no**      | yes      | yes  | yes     | no    |
| npm   | yes       | yes         | yes      | yes  | no      | yes   |
| pip   | yes       | yes         | **no**   | no   | no      | no    |
| cargo | yes       | yes         | yes      | yes  | no      | yes   |
| gem   | yes       | yes         | **no**   | no   | no      | no    |

|       | `list` | `ls` | `info` | `show` | `search` | `update` | `upgrade` |
|-------|--------|------|--------|--------|----------|----------|-----------|
| dnf   | yes    | yes  | yes    | no     | yes      | yes      | yes       |
| npm   | yes    | yes  | yes    | yes    | yes      | yes      | yes       |
| pip   | yes    | no   | **no** | yes    | yes      | no       | no        |
| cargo | **no** | no   | yes    | no     | yes      | yes      | no        |
| gem   | yes    | no   | yes    | no     | yes      | yes      | no        |

`install` and `search` are the only verbs all five agree on. Every other
operation is spelled differently depending on where the user came from, so any
single choice is wrong for a large share of them.

Lola sits on that fault line. It uses `uninstall`, which is the one removal verb
dnf does not have, while `dev-guide/architecture.md` opens by comparing Lola to
DNF.

The spellings also disagree inside Lola. `lola market ls` and `lola mod ls` use
the short form; `lola list` uses the long one. Same operation, two spellings,
depending on depth.

## Decision

### 1. The command set stays small; the accepted names do not

Surface is managed by keeping few *operations*, not few *names*. An alias adds a
spelling, not a concept, and costs the reader nothing because they never see the
ones they did not type. npm accepts six spellings across two operations and is
not considered confusing for it.

Where the number of commands does grow, it is managed with Cobra command groups
rather than by refusing useful commands.

### 2. Canonical names follow the evidence

Where managers disagree, the canonical name is the one with the widest support
in the table above, and the others become aliases:

| Operation | Canonical   | Aliases                                  |
|-----------|-------------|------------------------------------------|
| Install   | `install`   | `add`                                    |
| Remove    | `uninstall` | `remove`, `rm`, `erase`, `delete`, `del` |
| List      | `list`      | `ls`                                     |
| Describe  | `info`      | `show`, `view`                           |
| Search    | `search`    | `find`                                   |

`list` beats `ls` four managers to two, and `info` beats `show` four to two, so
Lola's top-level `lola list` is right and `lola market ls` / `lola mod ls` are
the ones that move. Both spellings keep working everywhere.

### 3. `update` is excluded from cross-manager aliasing

It is the one verb where the managers actively disagree on meaning rather than
spelling. In dnf, `update` and `upgrade` are the same command. In apt they are
not: one refreshes the index, the other installs. Aliasing across that
disagreement makes Lola's behaviour depend on which manager the user learned,
which is the opposite of the goal.

So `update` and `upgrade` are not aliased to each other, and neither is aliased
to anything else. Each `update` in Lola documents precisely what it updates.

This leaves a known divergence rather than fixing it: `lola update` regenerates
assistant files, which resembles nothing in the other five managers. Renaming it
is out of scope here and worth its own decision.

### 4. Ambiguous verbs are answered, not guessed

Lola has two removal concepts where dnf has one: a module can leave a project
(`lola uninstall`) or leave the local registry (`lola mod rm`).

`remove` and its aliases map to `uninstall`, because in every manager surveyed
"remove" means removing from the thing you are operating on, and for Lola that
is the project. The registry is closer to a cache, which no manager empties with
`remove`.

When the module remains in the registry afterwards, Lola says so and names the
command that would remove it there. Where an invocation is genuinely ambiguous,
the error names both options rather than picking one silently.

### 5. Aliases must be discoverable

Cobra registers aliases but does not complete them, and does not show them in
help. Both gaps are closed: shell completion offers aliases alongside canonical
names, and help lists them. An alias a user cannot discover only helps the user
who already guessed it.

### 6. User aliases are configurable, in addition to the defaults

Lola gains `lola alias set|list|delete|import`, modelled on `gh`. Two rules:

- **A user alias cannot shadow a built-in command.** Otherwise `lola install`
  means different things on different machines and no bug report reproduces.
- **The conventional verbs in §2 live in the binary, not in seeded
  configuration.** A user who clears their config keeps `remove`. The config is
  additive only.

## Rationale

- **The question is empirical.** Five managers, one agreed removal verb between
  them: none. Any single spelling is wrong for a large share of users, so this
  is not a matter of preference.
- **Lola's own analogy picks the losing verb.** The architecture doc leads with
  DNF, and dnf is the one manager without `uninstall`.
- **Aliases are read-cheap.** A user never sees the spellings they did not type.
  The cost lands on maintainers, in help text and completion, and both are
  mechanical.
- **Spelling and meaning are different problems.** Aliasing is safe where
  vocabularies differ and dangerous where they collide. `update` is the only
  verb in the table that collides.
- **Two removal concepts is a model question, not a CLI question.** The CLI can
  route the common case and name the other, but the underlying split is the same
  one #48 raises about registry and cache.

## Consequences

### Positive Consequences

- Someone arriving from dnf, apt, npm, pip, cargo or gem can type their own
  removal verb and have it work
- `lola list` and `lola mod list` stop disagreeing about the same operation
- #137 and #157 are both answered by one rule rather than two patches
- Aliases become discoverable through completion and help, which is what makes
  them worth having

### Negative Consequences

- Every accepted alias is API. Removing `del` later breaks whoever used it, so
  the set should be argued once rather than grown casually
- Five spellings of one operation makes documentation choose a voice; docs
  should use canonical names throughout or they teach the aliases by accident
- `lola update` keeps a meaning no other manager would predict, and this ADR
  names that without fixing it
- A user alias system is a support surface: bug reports need to say whether an
  alias was involved
- Completion output grows, and a long completion list is its own kind of noise

## Alternatives Considered

### Alternative 1: Pick one spelling and document it

- Description: Choose `uninstall`, document it, decline aliases.
- Pros: Smallest surface; one name in docs, help and errors.
- Cons: The table shows no spelling covers the audience. Documentation does not
  help someone who typed the wrong verb and got "unknown command".
- Reason for rejection: It answers #137 with "read the manual", which is what
  the issue is about.

### Alternative 2: Ship the aliases as default configuration

- Description: Seed the conventional verbs into the user config at first run.
- Pros: One mechanism instead of two; users can edit the defaults.
- Cons: Behaviour becomes dependent on config state, so a cleared config removes
  verbs the documentation promises, and support cannot assume a baseline.
- Reason for rejection: Defaults that live in mutable state are not defaults.

### Alternative 3: Alias `update` and `upgrade` to each other

- Description: Accept both spellings, as dnf does.
- Pros: Matches dnf and npm; one less thing to remember.
- Cons: apt users mean "refresh the index" by `update`, and Lola would do
  something else. The failure is silent and lands on the user's project.
- Reason for rejection: The two words disagree about meaning, not spelling.

### Alternative 4: Make `remove` an error that names both options

- Description: Refuse to route `remove`, and print the two candidates.
- Pros: Never does the wrong thing; teaches the model.
- Cons: The common case has an obvious answer, and an error for the common case
  is not "just works".
- Reason for deferral: Kept for genuinely ambiguous invocations, not for
  `remove` itself.

## Implementation Notes

Aliases first, since they are self-contained and answer the open issues.

1. Add the §2 alias sets with Cobra `Aliases`, plus completion and help support.
   This is where #137 and #157 close.
2. Reconcile `ls` and `list` across `lola`, `lola market` and `lola mod`, with
   both spellings accepted at every level.
3. Add command groups once the surface justifies it.
4. Add `lola alias` last. It is the only part that needs new configuration, and
   the defaults must ship before a user alias system can be described as
   additive.

Step 2 changes documented command names. The old spellings keep working, so the
change is additive, but the CLI reference and any tutorial content need updating
in the same release or they teach the wrong canonical form.

`lola mod search` is already documented as a deprecated alias for `lola search
--mod`, so a precedent exists for retiring a spelling without breaking it.

## References

- Issue #137 — `list` and `remove` as alternatives for `ls` and `rm`
- Issue #157 — make `ls` the default for `lola mod`
- Issue #56 — LLM-friendly `--help`
- Issue #48 — mental model and terminology, including registry versus cache
- [ADR: Extension Architecture](extension-architecture.md) — extensions
  contribute commands, so the alias rule has to reach them
- [`gh alias`](https://cli.github.com/manual/gh_alias) — the user alias model,
  including `import` from YAML
