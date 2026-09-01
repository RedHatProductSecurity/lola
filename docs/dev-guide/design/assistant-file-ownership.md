# Assistant File Ownership

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

Implementation detail for [ADR: Assistant File
Ownership](../../adr/assistant-file-ownership.md). The ADR owns the
decision; this document owns the module format, the per-target layout, the
reference syntax, and the migration.

## Current behaviour

`src/lola/targets/base.py` provides two mixins that write into markdown files:

- `ManagedSectionTarget` — skills are rendered into a managed section of
  `MANAGED_FILE`. Only `gemini-cli` uses it, with `MANAGED_FILE = "GEMINI.md"`.
- `ManagedInstructionsTarget` — module instructions are rendered into a managed
  section of `INSTRUCTIONS_FILE`. Used by `claude-code` (`CLAUDE.md`),
  `opencode` (`AGENTS.md`) and `copilot-*` (`.github/copilot-instructions.md`).

Both wrap what they write:

```html
<!-- lola:instructions:start -->
<!-- lola:module:example:start -->
...module content, inlined verbatim...
<!-- lola:module:example:end -->
<!-- lola:instructions:end -->
```

`generate_instructions` resolves the module's content and inlines it.
`remove_instructions` finds the module's markers and removes that block,
dropping the whole section when the last module goes. The markers are reliable;
the problem is what sits between them.

`cursor` uses neither mixin. `CursorTarget.generate_instructions` writes
`.cursor/rules/<module>-instructions.mdc` with `alwaysApply: true`, and
`remove_instructions` unlinks it.

`openclaw` uses neither mixin and does not override the base implementations.
`BaseAssistantTarget.generate_instructions` returns `False`, so the
`.openclaw/instructions.md` path declared at `openclaw.py:50` is never written.
It delivers no instructions today.

## Module format

The module's instructions file is `module/INSTRUCTIONS.md`. `models.py` changes
`INSTRUCTIONS_FILE` to match. `OpenCodeTarget.INSTRUCTIONS_FILE` is a different
concept — OpenCode's own `AGENTS.md`, a destination rather than a source — and
does not change.

Detection gains a second flag so the two cases can be told apart:

| `INSTRUCTIONS.md` | `AGENTS.md` | `has_instructions` | `has_legacy_instructions` |
|-------------------|-------------|--------------------|---------------------------|
| present, non-empty | either      | `True`             | `False`                   |
| absent             | present, non-empty | `False`     | `True`                    |
| absent             | absent      | `False`            | `False`                   |

`has_legacy_instructions` drives the warning and nothing else. It never causes
content to be written.

`lola mod init` scaffolds `INSTRUCTIONS.md` instead of `AGENTS.md`, and the
legacy-structure remediation text in `src/lola/exceptions.py` names the new
file.

### Legacy warning

Emitted at `lola mod add` and again at `lola install`, because the person who
registers a module is often not the person who can fix it:

```text
warning: git-module ships AGENTS.md but no INSTRUCTIONS.md.
         Lola no longer reads AGENTS.md; its instructions were NOT installed.

         If you maintain this module, rename
           module/AGENTS.md -> module/INSTRUCTIONS.md
         If not, open an issue upstream.

         Skills, commands and agents were installed normally.
```

There is no flag to inject the legacy file anyway.

## Target layout after this change

| Target           | Owned instructions path                       | Reference into a user file          |
|------------------|-----------------------------------------------|-------------------------------------|
| `cursor`         | `.cursor/rules/<module>-instructions.mdc`     | none needed                         |
| `copilot-cli`    | `.github/instructions/<module>.instructions.md` | none needed                       |
| `copilot-vscode` | inherited from `copilot-cli`                  | none needed                         |
| `opencode`       | `.opencode/lola/<module>.md`                  | glob in `opencode.json`             |
| `openclaw`       | `.openclaw/lola/<module>.md`                  | none needed                         |
| `claude-code`    | `.claude/lola/<module>.md`                    | `@.claude/lola/<module>.md` in `CLAUDE.md` |
| `gemini-cli`     | not applicable                                | managed section retained            |

Per-module files are the unit that is created and deleted, so uninstalling one
module never rewrites another's content. There is no generated `index.md`.

At `--scope user` the same layout applies under the user's assistant directory,
with two exceptions covered below.

## Reference syntax

Each row is verified against the host's current documentation.

**`cursor`** resolves `.mdc` rules with `alwaysApply: true` without any
reference. Unchanged from today.

**`copilot-*`** resolves `.github/instructions/**/*.instructions.md` when the
file's `applyTo` frontmatter matches. Lola writes `applyTo: "**"` so module
instructions are always on:

```markdown
---
applyTo: "**"
---
```

**`opencode`** does not parse file references inside `AGENTS.md` — upstream is
explicit about this. It does read an `instructions` array in `opencode.json`,
which accepts globs, so Lola adds one entry:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [".opencode/lola/*.md"]
}
```

Because it is a glob rather than a list of files, the entry is written once and
never rewritten as modules come and go. The write merges into any existing
config, following the pattern `MCPSupportMixin` already uses for the other
targets' JSON configs, and is idempotent across repeated installs.

**`claude-code`** resolves `@path` imports inside `CLAUDE.md`. This repository
relies on it: `CLAUDE.md` begins with `@AGENTS.md`. One line per
instructions-shipping module goes inside the existing markers:

```markdown
<!-- lola:instructions:start -->
@.claude/lola/git-module.md
@.claude/lola/deploy-module.md
<!-- lola:instructions:end -->
```

**`gemini-cli`** keeps its managed section. Gemini CLI does resolve `@file.md`
imports inside `GEMINI.md`, so a reference would work for instructions — but
`GEMINI.md` is also the only way skills reach Gemini CLI at all, so the managed
section stays regardless. Splitting instructions out to a reference while skills
remain inlined would add a mechanism without removing a write.

**`openclaw`** auto-discovers under its workspace and needs no reference.

Record the finding in each target's module docstring so the next reader does not
re-derive it.

## Scope rules

Two targets cannot deliver instructions at `--scope user` without writing a file
the user authored.

**`claude-code` is project scope only for instructions.** The pointer would have
to go in `~/.claude/CLAUDE.md`. Writing the owned file without the pointer would
leave content nothing reads, so Lola writes neither and reports why. Skills at
user scope are unaffected — Claude Code reads `~/.claude/skills/` unprompted.

**`gemini-cli` is the documented exception.** `~/GEMINI.md` is its only vector
for skills as well as instructions, so user scope necessarily writes it. This is
recorded in `GeminiTarget`'s docstring.

Whether the correct path is `~/GEMINI.md` or `~/.gemini/GEMINI.md` is confirmed
against upstream before the surrounding code is changed; Gemini CLI's documented
global context file is under `~/.gemini/`.

Every other target writes only inside its own directories at user scope.

## Migration

One-way removal. There is no new mechanism to migrate into, so nothing is
dual-written and there is no flag day.

Removal runs during `lola install` and `lola update`, against the project being
operated on, via a shared `strip_legacy_managed_section()` in `base.py`. Each
target that previously wrote a managed section calls it; the parsing is
non-trivial and must not be duplicated four times.

For each module block inside a `lola:instructions` section:

| Condition                              | Action                   |
|----------------------------------------|--------------------------|
| Block matches what Lola would generate | Remove                   |
| Block differs from generated content   | Keep, report hand-edited |
| Module source unavailable to compare   | Keep, report             |
| Module content present, markers absent | Leave file, report       |
| Last block removed                     | Remove enclosing section |

Reading a legacy `AGENTS.md` in order to compare against it is permitted. Lola
declines to inject it, not to look at it.

Every file changed and every difference kept is reported:

```text
Removed stale instructions block from CLAUDE.md
  - git-module (matched generated content)
Kept in AGENTS.md (hand-edited, remove manually):
  - deploy-module
Found undelimited module content, not touched:
  - GEMINI.md: legacy-module
```

### What migration will not do

If the markers around a block were removed by hand, the content is
indistinguishable from the user's own writing. Lola does not guess. It leaves
the file untouched and reports that it found module content it cannot delimit,
naming the file and the module.

This is the only correct behaviour available: deleting unmarked lines risks
destroying the user's work, and leaving a duplicate is visible and recoverable.

### `--append-context`

Deleted rather than aliased. It is accepted on the command line *and* persisted
in installation records, so removal covers stored state as well as the flag:
existing records carrying it are ignored rather than replayed.

## Code shape

`ManagedInstructionsTarget` is retained unchanged and ends with exactly one
consumer, `gemini-cli`. `claude-code`, `opencode` and `copilot-*` stop mixing it
in and implement `generate_instructions`/`remove_instructions` directly, as
`cursor` already does. `CopilotVSCodeTarget` subclasses `CopilotCliTarget` and
inherits both.

Cleaning up previous installations is a separate concern from a target's own
uninstall path, which is why `strip_legacy_managed_section()` is a shared
function rather than a retained mixin method. Without it, marker-handling
knowledge disappears along with the mixin and existing installations can never
be cleaned up.

## Testing

- A module with no `INSTRUCTIONS.md` writes no owned file, no reference, and
  touches no user file, on every target
- A module with a legacy `AGENTS.md` only warns, injects nothing, and still
  installs skills, commands and agents
- A module with both files uses `INSTRUCTIONS.md` and warns about nothing
- `remove_instructions` leaves a user file byte-identical to its pre-install
  state, for every target, including when the user edited around the block
- Installing two modules and uninstalling one leaves the other's owned file
  untouched and its reference line unchanged
- `opencode.json` gains exactly one glob entry, idempotent across repeated
  installs, and merges into an existing config without disturbing other keys
- Migration on a file with a hand-edited module block keeps the user's version
  and reports it
- Migration on a file with removed markers changes nothing and reports it
- `claude-code --scope user` writes nothing outside `~/.claude/` and reports
  that instructions are project scope only
- `--scope user` writes nothing under `$HOME` outside the assistant's own
  directory, `gemini-cli` excepted
- Round-trip: install, migrate, uninstall, and confirm no Lola-owned file or
  reference remains
- E2E BDD coverage for the legacy warning, per the new-CLI-behaviour rule
