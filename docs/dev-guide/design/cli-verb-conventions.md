# CLI Verb Conventions

----
> 🦾 Written with LLM assistance [claude-opus-5]
> 💪 Reviewed by a human before submission
----

Implementation detail for [ADR-0010](../../adr/0010-cli-verb-conventions.md).
The ADR owns the rule; this document owns the command map, the two Cobra gaps
that have to be closed by hand, and the alias configuration format.

The support figures quoted here were produced by running each verb with `--help`
against dnf 4.20.0, npm 11.9.0, pip 23.3.2, cargo 1.96.1 and gem 3.6.9, and by
`go help <verb>` for Go 1.26. They describe those versions, not the formats in
the abstract.

## Command map

Canonical names are what help, errors and documentation use. Aliases are
accepted silently.

| Command                | Canonical          | Accepted aliases                                |
|------------------------|--------------------|-------------------------------------------------|
| Install into a project | `lola install`     | `add`                                           |
| Remove from a project  | `lola uninstall`   | `remove`, `rm`, `erase`, `delete`, `del`        |
| List installations     | `lola list`        | `ls`                                            |
| Search                 | `lola search`      | `find`                                          |
| Register a module      | `lola mod add`     | `get`                                           |
| Drop a module          | `lola mod rm`      | `remove`, `uninstall`, `erase`, `delete`, `del` |
| List modules           | `lola mod list`    | `ls`                                            |
| Describe a module      | `lola mod info`    | `show`, `view`                                  |
| Register a marketplace | `lola market add`  | —                                               |
| Drop a marketplace     | `lola market rm`   | `remove`, `delete`, `del`                       |
| List marketplaces      | `lola market list` | `ls`                                            |

`lola list` already uses the canonical spelling. `lola market ls` and `lola mod
ls` move to `list` with `ls` accepted, which is the only user-visible rename in
the set, and the old spelling keeps working.

Nothing in this table touches `lola update`, `lola mod update`, `lola market
update` or `lola sync`. Per the ADR, `update` is not aliased in either
direction.

### Why these canonical names

| Verb        | Managers accepting it      | Chosen as             |
|-------------|----------------------------|-----------------------|
| `list`      | dnf, npm, pip, gem, go (5) | canonical             |
| `ls`        | dnf, npm (2)               | alias                 |
| `info`      | dnf, npm, cargo, gem (4)   | canonical             |
| `show`      | npm, pip (2)               | alias                 |
| `view`      | npm (1)                    | alias                 |
| `uninstall` | npm, pip, cargo, gem (4)   | canonical             |
| `remove`    | dnf, npm, cargo (3)        | alias                 |
| `erase`     | dnf (1)                    | alias                 |
| `install`   | all (5)                    | canonical, no contest |
| `search`    | all (5)                    | canonical, no contest |

`add` is accepted as an alias for `install` because npm and cargo use it that
way. It stays an alias rather than becoming canonical: `lola mod add` already
means "register in the registry", so promoting `add` at top level would put two
meanings on one word inside Lola.

## The two Cobra gaps

Cobra's `Aliases` field routes an alias to its command and stops there. Two
things it does not do, both of which decide whether an alias is worth having.

**Completion.** Cobra completes canonical subcommand names only, so `lola
unins<TAB>` completes and `lola remo<TAB>` does not. Set the root's
`ValidArgsFunction` to a completer that appends aliases to the canonical set.
Cobra calls the root's `ValidArgsFunction` after its own subcommand-name pass
provided the root declares no `ValidArgs`, so the two do not fight.

**Help.** Aliases do not appear in generated usage. Walk the command tree at
startup and fold each command's aliases into its usage line, so `lola --help`
shows the accepted spellings rather than hiding them.

A third detail applies if #157 lands and a group like `lola mod` gains a default
action. Leave that command's `Args` unset. Cobra's `legacyArgs` rejects an
unknown first argument on a command that has subcommands, which is what makes
`lola mod bogsu` an error instead of a silent listing. Setting `Args` to
something permissive turns every typo into a successful no-op.

## Removal routing

`remove` and its aliases route to `uninstall`, per the ADR. Uninstalling
something that is still registered prints one line naming the other command:

```text
uninstalled example from ./my-project
  still in your registry: lola mod rm example
```

Not a warning and not a prompt. The user did what they asked for; the note only
exists because a dnf user's `remove` removes the package from the system, and
Lola's equivalent leaves a copy behind.

Genuinely ambiguous invocations, where the argument names something Lola cannot
resolve to one operation, print both candidates and exit non-zero:

```text
error: lola remove is ambiguous for "example".
  lola uninstall example   remove from this project
  lola mod rm example      remove from your registry
```

One structure should drive both this error and the command's `--help` example
block, so the two cannot drift. One worked implementation is `argGuide` in
[kref](https://github.com/trevor-vaughan/kref): a value carrying the missing
noun, the discovery command, the canonical usage and the worked examples. It
feeds the arg-count validator and the help renderer from the same source.

That coupling is also the cheapest answer to issue #56: a model that invokes
`lola remove` with no usable argument is told which command to run to discover
one, without a separate machine-readable help mode.

## User aliases

`lola alias set|list|delete|import`, modelled on `gh alias`. Stored in the user
config, not the project, since an alias is a property of the person typing.

```yaml
aliases:
  i: install
  co: "mod add"
  nuke: "uninstall --purge"
```

Resolution order, checked in this sequence:

1. Built-in command name
2. Built-in alias from the command map above
3. User alias
4. Unknown command error

**A user alias that collides with 1 or 2 is refused at `set` time**, with the
conflict named. This is stricter than `gh`, whose `--clobber` covers only
alias-on-alias collisions. The reason is reproducibility: if `lola install`
could mean something local, no bug report can be trusted.

`import` reads the same YAML shape, which lets a preset be distributed as a
file. That is the mechanism by which an opinionated "apt profile" or "npm
profile" could exist without any of it being compiled in.

Expansion is textual and single-pass. A user alias may not expand to another
user alias, because chains make an unknown-command error impossible to explain.

## Extensions

ADR-0003 defines five extension kinds — `target`, `repo`, `runtime`, `source`
and `scan` — and none of them contributes a CLI command. Extensions cannot add
verbs today, so nothing here applies to them yet.

Recording one rule now, because it is cheaper than retrofitting it: if a future
kind does contribute commands, the names in the command map are reserved
vocabulary. An extension may not claim a canonical name or an alias from that
table, even one whose built-in is not currently registered.

## Testing

- Every alias in the command map routes to its canonical command, asserted from
  the map rather than from a duplicated list, so a new alias cannot ship
  untested
- Shell completion offers aliases: `remo<TAB>` yields `remove`
- `--help` output contains every accepted spelling for each command
- `lola mod bogsu` exits non-zero and does not list, including after a default
  action is added
- Uninstalling a still-registered module prints the registry note; uninstalling
  an unregistered one does not
- An ambiguous `remove` exits non-zero and names both candidates
- `lola alias set install ...` is refused, naming the built-in
- `lola alias set rm ...` is refused, naming the built-in alias
- A user alias expanding to another user alias is refused
- `lola alias import` round-trips a file produced by `lola alias list`
- Documentation uses canonical names: no `ls` or `remove` in the CLI reference
  except where the alias itself is being documented
