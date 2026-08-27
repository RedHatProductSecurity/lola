# Plugin Installation

Lola can install modules as native plugins using the `--plugin` flag. Instead
of installing skills, agents, commands, and MCPs as individual files scattered
across assistant-specific directories, `--plugin` bundles everything into a
single self-contained plugin directory with a `plugin.json` manifest.

## When to Use `--plugin`

Use `--plugin` when the target assistant supports plugins and you want all
module components to be managed as a single unit. This makes it easier to
install, update, and remove the module as a whole — and allows the assistant
to recognize it as a plugin rather than loose files.

## Existing `plugin.json`

If the module already includes a `plugin.json` file, Lola uses it as-is during
plugin installation. This preserves any metadata the pack author has set (name,
version, description, extensions, etc.).

If no `plugin.json` is present, Lola generates a manifest based on the target
implementation per the [Open Plugin Spec](https://agent-plugins.org/).

## Supported Clients

| Client | Project-level | User-level | Notes |
|--------|:---:|:---:|-------|
| Claude Code | Yes | Yes | Uses Claude's own `.claude-plugin/` format |
| Cursor | No | Yes | Uses the [Agent Plugins](https://agent-plugins.org/) global spec |
| Copilot CLI | — | — | Not yet supported |
| Copilot VS Code | — | — | Not yet supported |
| OpenCode | — | — | Does not support plugins |
| Gemini CLI | — | — | Shut down; replaced by Antigravity (not yet supported by Lola) |
| OpenClaw | — | — | Not yet supported |

### Claude Code

Claude Code supports plugins at both project and user scope. Plugins are placed
inside the `.claude/skills/` directory — Claude Code treats any folder under
`skills/` that contains a `.claude-plugin/plugin.json` as a plugin (not a plain
skill). This is Claude Code's own format, not the global Agent Plugins spec.
Claude Code does not support the global spec's `plugin.json` at root for
skills-directory plugins.

```bash
# Project-level (default)
lola install my-module --plugin -a claude-code

# User-level
lola install my-module --plugin -a claude-code -s user
```

### Cursor

Cursor supports user-level plugins only — there is no documented project-level
plugin auto-discovery path. Cursor supports both its own plugin format
(`.cursor-plugin/plugin.json`) and the [Agent Plugins](https://agent-plugins.org/)
open standard. Lola uses the global spec format for portability.

```bash
lola install my-module --plugin -a cursor -s user
```

### Copilot (CLI and VS Code)

Copilot does not have a drop-in directory for plugins. The
`~/.copilot/installed-plugins/` directory is managed by Copilot's own
`copilot plugin install` command and is not intended for external tools.
Available alternatives:

- **Copilot CLI**: `copilot plugin install /path/to/plugin`
- **Copilot VS Code**: `chat.pluginLocations` setting in `.vscode/settings.json`
- **Local marketplace**: `copilot marketplace add /local/path`

Lola does not currently support `--plugin` for Copilot targets.

### OpenCode

OpenCode's "plugins" are JS/TS code modules for TUI/runtime extensions (event
hooks, custom tools). They do not bundle skills, agents, or MCP configs. Lola
does not support `--plugin` for OpenCode.

## Uninstalling Plugins

Use `--plugin` when uninstalling a module that was installed as a plugin:

```bash
lola uninstall my-module --plugin -a claude-code
```

Lola tracks whether a module was installed as a plugin or as individual files.
Attempting to uninstall a plugin without `--plugin` (or vice versa) will show
an error:

```
my-module was installed as a plugin for claude-code, use --plugin to uninstall
```

## Error Handling

When using `--plugin` with an unsupported client or scope:

- **Explicit `-a`**: exits with an error message (`--plugin is not supported
  with opencode` or `project-level plugin is not supported for cursor`)
- **All-agents mode** (no `-a`): unsupported clients are skipped silently,
  supported ones are installed as plugins

## Troubleshooting

### Claude Code plugin shows as "(suppressed)"

Claude Code project-level plugins require workspace trust. The trust dialog
should appear when you open a project with a plugin, but a
[known bug](https://github.com/anthropics/claude-code/issues/72896) prevents
it: if any parent directory was previously trusted, Claude Code skips the dialog
for child directories. But trust is only applied on exact path match, so the
plugin is blocked with no interactive way to fix it.

To work around this, manually set trust and restart Claude Code:

```bash
# Check current trust status
jq --arg p "$(pwd)" '.projects[$p].hasTrustDialogAccepted' ~/.claude.json

# Set trust
tmp=$(mktemp) && jq --arg p "$(pwd)" \
  '.projects[$p].hasTrustDialogAccepted = true' \
  ~/.claude.json > "$tmp" && mv "$tmp" ~/.claude.json
```
