# ADR: Assistant File Ownership

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

Lola generates assistant files on install. Two reports say it generates some of
them in files it does not own.

Issue #158 describes `lola install` inlining a module's entire `AGENTS.md` into
the user's own `CLAUDE.md`, `AGENTS.md` or `GEMINI.md`. These are files the user
maintains by hand and every assistant reloads on every turn. At user scope
`ClaudeCodeTarget.get_instructions_path` resolves to `~/.claude/CLAUDE.md`, so
material installed for one project is loaded in every unrelated one.

Issue #148 describes the same behaviour from a maintainer's position. The
maintainer checks `AGENTS.md` into git and uses `lola sync` to recommend modules
to contributors. Injected content makes the tracked file change whenever a skill
changes or a contributor pins a different version, and contributors who do not
use Lola get a file describing modules they do not have.

The current behaviour is not unmarked. `ManagedInstructionsTarget` wraps
everything it adds in HTML comment delimiters, one pair around the whole section
and one pair per module, and `remove_instructions` deletes a module's block
cleanly. Removal works. What the markers do not change is that the content
itself is copied into a file the user owns, so the file still changes size and
still churns in version control.

### The content is redundant

Both reports are about where the content goes. The prior question is whether it
needs to go anywhere.

Every target Lola supports, except one, discovers skills on its own and reads
each skill's `description` frontmatter to decide when to load it. Verified
against each host's current documentation:

| Target           | Skills namespace                                           |
|------------------|------------------------------------------------------------|
| `claude-code`    | `.claude/skills/`                                          |
| `cursor`         | `.cursor/skills/`, `.claude/skills/`, `.agents/skills/`    |
| `opencode`       | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`  |
| `copilot-cli`    | `.github/skills/`, `.claude/skills/`, `~/.copilot/skills/` |
| `copilot-vscode` | inherits `copilot-cli` paths by subclassing                |
| `openclaw`       | `<workspace>/skills/`                                      |
| `gemini-cli`     | none                                                       |

A module-level instructions blob that lists a module's own skills therefore
restates metadata the host already parses, and charges the user's context
budget for it on every turn. `examples/git-module/module/AGENTS.md` is exactly
this: four bullets naming a skill, two commands and an agent, every one of
which every target but `gemini-cli` discovers unaided.

`gemini-cli` is the exception, and not merely for instructions: it has no
skills directory, so `GEMINI.md` is how skills reach Gemini CLI at all.

### `AGENTS.md` is the wrong name for the payload

`lola install` copies the module into the consumer's repository at
`.lola/modules/<name>/`. Copilot reads `AGENTS.md` files stored anywhere in a
repository, taking the nearest one in the directory tree, and OpenCode walks up
from the working directory loading them. So when an agent works on files under
`.lola/modules/<name>/`, that module's `AGENTS.md` becomes its governing
instructions — unmarked, unintended, and outside the reach of
`remove_instructions`. The blast radius is narrow, but it exists whether or not
Lola injects anything.

The name also makes intent unreadable. `Module.has_instructions` is derived from
whether `AGENTS.md` exists and is non-empty, so an author who writes one for
human contributors gets it injected into every consumer's context file as a side
effect. Presence is being read as intent.

The codebase already carries the confusion, twice, for opposite things:
`models.py` defines `INSTRUCTIONS_FILE = "AGENTS.md"` as a **source** Lola
reads, and `OpenCodeTarget` defines `INSTRUCTIONS_FILE = "AGENTS.md"` as a
**destination** Lola writes.

### The targets do not agree with each other today

| Target        | Skills                      | Instructions                                        |
|---------------|-----------------------------|-----------------------------------------------------|
| `cursor`      | `.cursor/skills/`           | `.cursor/rules/<module>-instructions.mdc`           |
| `claude-code` | `.claude/skills/`           | `CLAUDE.md`, or `~/.claude/CLAUDE.md` at user scope |
| `opencode`    | `.opencode/` directories    | `AGENTS.md`                                         |
| `gemini-cli`  | `GEMINI.md` managed section | `GEMINI.md`                                         |

The Cursor target already works the way this ADR proposes.
`CursorTarget.generate_instructions` writes one `.mdc` file per module with
`alwaysApply: true`, in a directory Lola owns, and `remove_instructions` deletes
that file. Nothing of the user's is touched.

## Decision

**Lola writes generated content only into paths it owns. Module instructions are
opt-in, and reach each assistant through that assistant's own documented
always-on mechanism.**

Skills, commands, agents and MCP servers are unaffected. They already land in
namespaces their hosts discover.

### 1. The module's instructions file is renamed

`module/AGENTS.md` becomes `module/INSTRUCTIONS.md`.

`AGENTS.md` is an ecosystem convention with an established meaning — a file
hosts themselves read. `INSTRUCTIONS.md` carries no prior meaning, so nobody
creates one by accident: presence *is* intent, and no manifest flag is needed to
express it. After the rename a module's `AGENTS.md` means what the ecosystem
says it means — instructions for agents working *on the module* — and a module
shipping both files is correct.

Only the module-side constant changes. `OpenCodeTarget.INSTRUCTIONS_FILE` refers
to OpenCode's own `AGENTS.md` and stays as it is.

### 2. A legacy `AGENTS.md` is not injected

A module with `AGENTS.md` and no `INSTRUCTIONS.md` warns at `lola mod add` and
at `lola install`, names the rename as the fix, and installs its skills,
commands and agents normally. Its instructions are not installed.

There is no override flag. The fix is renaming one file; an override would be a
permanent feature preserving a transitional ambiguity.

### 3. Each target uses its own always-on mechanism

| Target           | `INSTRUCTIONS.md` destination                                    | User file |
|------------------|------------------------------------------------------------------|-----------|
| `cursor`         | `.cursor/rules/<module>-instructions.mdc`, `alwaysApply: true`   | no        |
| `copilot-cli`    | `.github/instructions/<module>.instructions.md`, `applyTo: "**"` | no        |
| `copilot-vscode` | inherited from `copilot-cli`                                     | no        |
| `opencode`       | `.opencode/lola/<module>.md` + glob in `opencode.json`           | no        |
| `openclaw`       | `.openclaw/lola/<module>.md`                                     | no        |
| `claude-code`    | `.claude/lola/<module>.md` + `@` line in `CLAUDE.md`             | one line  |
| `gemini-cli`     | managed section in `GEMINI.md`                                   | yes       |

`cursor` already behaves this way and does not change. The `opencode.json` write
follows the precedent `MCPSupportMixin` sets for `.vscode/mcp.json` and the
other MCP configs: machine-owned configuration, not prose. Because it is a glob,
it is written once and not rewritten as modules come and go.

A target that cannot deliver instructions reports that at install time. No
target writes an owned file that nothing will read.

### 4. `claude-code` gets a pointer, not an index

The reference is one `@` line per instructions-shipping module, inside the
existing markers:

```markdown
<!-- lola:instructions:start -->
@.claude/lola/git-module.md
<!-- lola:instructions:end -->
```

There is no generated `index.md`. #148 is about content churn — the tracked file
changing when a skill or a version changes — and direct lines already prevent
that, because a line changes only when the set of instructions-shipping modules
changes. An index would additionally absorb set churn, which is rare now that
instructions are opt-in, at the cost of a generated file, a resolution hop, and
a `CLAUDE.md` that no longer shows what it loads.

### 5. Scope rules

`claude-code` instructions are **project scope only**. At `--scope user` the
pointer would have to go in `~/.claude/CLAUDE.md`, which Lola does not write,
and writing the owned file without the pointer would leave content nothing
reads. Lola writes nothing and says why. Skills installed at user scope are
still found, because Claude Code reads `~/.claude/skills/` without being told.

`gemini-cli` is a **named exception**. `GEMINI.md` is its only delivery vector
for skills, not merely for instructions, so `--scope user` on `gemini-cli`
necessarily writes a user-authored file. Dropping user-scope Gemini support
would be a regression for existing users, so the exception is recorded here and
in the target's module docstring, and revisited if Gemini CLI grows a skills
directory.

Every other target writes only inside its own directories at user scope.

### 6. No configuration is added

`--append-context` is deleted rather than aliased. No `instructions.mode` or
`instructions.targets` setting is introduced. With nothing written to a
user-authored file unless a module declares instructions, and only two targets
touching one at all, there is no knob worth offering.

## Rationale

- **The cheapest fix for redundant content is not to generate it.** The prior
  design answered "where should this content go" with indirection for every
  target. Verifying the hosts first showed the content is unnecessary on six of
  seven, which removes the question rather than answering it.
- **A package manager owns its own namespace.** DNF does not append to
  `/etc/profile`; it installs into paths it can list, verify and remove.
- **The pattern is already in the codebase.** Cursor's `.mdc` approach is not a
  new design to be proven; it is in use today, and neither report names it.
- **Opt-in by naming beats opt-in by flag.** A file nobody creates by accident
  encodes intent without new configuration to document, discover or maintain.
- **Global scope is the sharpest edge.** A project-scoped write shows up in `git
  status`. Writing `~/.claude/CLAUDE.md` does not, and it affects work that has
  nothing to do with the module.
- **This is the same principle as extension sandboxing.** Host-mediated
  effects say an extension does not choose what gets written or where. Owning
  the namespace says the same thing about the host's own output.

## Consequences

### Positive Consequences

- A tracked `AGENTS.md` or `CLAUDE.md` stops changing when module versions
  change, so `lola sync` becomes usable in a shared repository
- Most modules stop consuming context on every turn for content their host
  already derives from skill frontmatter
- Uninstall becomes a file deletion for every target except `gemini-cli`, rather
  than a text edit that has to find and preserve surrounding content
- A module's `AGENTS.md` stops being ambient instructions inside
  `.lola/modules/`
- User scope stops leaking one project's context into every other project
- No new configuration surface is created

### Negative Consequences

- Breaking change for module authors: every module shipping `AGENTS.md` must
  rename it, and until it does, its instructions are silently not delivered —
  mitigated by a warning at both `mod add` and `install`, but it is still a
  behaviour change users did not ask for
- Behaviour change for existing installs: content currently inside a managed
  block has to be removed from files the user owns
- One more layer of indirection for a `claude-code` reader, who must follow the
  pointer to see what a module contributes
- `gemini-cli` remains inconsistent with the others, and is now the only target
  where a user-authored file is written at all
- Five delivery mechanisms to maintain and test instead of one, because each
  follows its host rather than a Lola convention

## Alternatives Considered

### Alternative 1: Keep inlining, add an opt-out flag

- Description: Leave the default and let anyone affected pass a flag.
- Pros: No migration, no behaviour change, smallest diff.
- Cons: Both reporters hit the problem before they knew a flag existed. A
  default that requires a flag to be safe is not a safe default.
- Reason for rejection: It addresses the complaint without addressing the cause.

### Alternative 2: Owned file plus pointer for every target

- Description: The previous form of this ADR. Every target gets
  `<owned>/lola/<module>.md` and a generated `index.md`, with a one-line pointer
  written into whichever user file the host reads.
- Pros: One mechanism, uniform across targets, no per-host special cases.
- Cons: Generalises a problem only `claude-code` and `gemini-cli` actually have,
  and still delivers content six of seven hosts do not need — paying the
  indirection cost to solve a problem created by generating the content at all.
- Reason for rejection: Superseded by verifying host capabilities first.

### Alternative 3: Write to a single shared `lola.md` per project

- Description: One Lola-owned file for all modules, as #148 suggests.
- Pros: Very simple; one pointer, one file.
- Cons: Uninstalling one module means editing a file that holds several, which
  reintroduces the text-surgery problem inside Lola's own namespace.
- Reason for rejection: Per-module files remain the unit that gets created and
  deleted.

### Alternative 4: Never write user-authored files at all, including a pointer

- Description: Lola writes only its own directories and documents that the user
  must add the reference by hand.
- Pros: The strongest possible ownership boundary.
- Cons: Nothing works until a manual step is completed, and the failure is
  silent — the assistant simply behaves as though no module were installed.
- Reason for rejection: A package manager whose output does nothing until the
  user edits a file by hand is not finished. The decision above gets most of the
  benefit anyway: five of seven targets need no user-file write.

### Alternative 5: Drop instructions support entirely

- Description: Remove the concept. Modules ship skills, commands, agents and
  MCP servers only.
- Pros: Deletes the problem outright, and the most code.
- Cons: Always-on rules are a real category that skills cannot express — a skill
  loads when its description matches, whereas "line limit is 80 characters" must
  always apply. `cursor` supports this correctly today, so removal is a
  regression there.
- Reason for rejection: The category is legitimate; only its default was wrong.

## Implementation Notes

The migration is one-way removal. There is no new mechanism to migrate into, so
the previous four-phase dual-write sequence does not apply.

Removal runs during `lola install` and `lola update`, against the project being
operated on. This is Lola deleting content Lola wrote, delimited by markers Lola
placed, and it is reversible through version control like any other write. For
each module block inside a `lola:instructions` section:

| Condition                              | Action                   |
|----------------------------------------|--------------------------|
| Block matches what Lola would generate | Remove                   |
| Block differs from generated content   | Keep, report hand-edited |
| Module source unavailable to compare   | Keep, report             |
| Module content present, markers absent | Leave file, report       |
| Last block removed                     | Remove enclosing section |

Reading a legacy `AGENTS.md` in order to compare against it is permitted; Lola
declines to inject it, not to look at it.

Where markers were removed by hand, the content is indistinguishable from the
user's own writing. Lola leaves the file untouched and reports the file and
module, rather than guessing which lines were once its own. Deleting unmarked
lines risks destroying the user's work; leaving a duplicate is visible and
recoverable.

`--append-context` is recorded in installation records as well as accepted on
the command line, so removing it means handling stored state, not only a CLI
argument.

Three facts are confirmed before the code depending on them is written. None
changes this decision.

1. `BaseAssistantTarget.generate_instructions` returns `False` by default and
   `openclaw` does not override it, so `openclaw` delivers no instructions today
   and its declared `.openclaw/instructions.md` path is unused. It gains
   delivery it never had.
2. Whether Copilot in VS Code loads skills is confirmed for `copilot-cli` but
   not for `copilot-vscode`. Since the latter subclasses the former, both write
   identical paths either way; only the documented exception list changes.
3. Whether `~/GEMINI.md` is the correct user-scope path. Gemini CLI's documented
   global context file is under `~/.gemini/`.

## References

- Issue #158 — excessive material written into `AGENTS.md` and friends
- Issue #148 — `lola sync` opt-out of changes to `AGENTS.md`
- [ADR: Extension Architecture](extension-architecture.md) — target
  extension kind
- ADR: Extension Sandboxing, proposed separately — the same ownership
  principle applied to extension effects
- [Design: Assistant File
  Ownership](../dev-guide/design/assistant-file-ownership.md) — layout,
  reference syntax and migration detail
- `src/lola/targets/base.py` — `ManagedInstructionsTarget`,
  `ManagedSectionTarget`, `MCPSupportMixin`
- `src/lola/targets/cursor.py` — the owned-file pattern this ADR generalises
- [Cursor agent skills](https://cursor.com/docs/context/skills)
- [OpenCode rules](https://opencode.ai/docs/rules/) and
  [skills](https://opencode.ai/docs/skills/)
- [Copilot custom instructions support][copilot-instructions]
- [Copilot CLI agent skills][copilot-cli-skills]
- [Gemini CLI context files][gemini-context]

[copilot-instructions]: https://docs.github.com/en/copilot/reference/custom-instructions-support
[copilot-cli-skills]: https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
[gemini-context]: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md
