# Creating Modules

A Lola module can be an [Agent Plugins 1.0](https://agent-plugins.org/specification)
package, a single [Agent Skill](https://agentskills.io/specification), or a
legacy [AI Context Module](../concepts/skills-and-modules.md).

An Agent Plugins package is the default `lola mod init` layout: a
`plugin.json` manifest with portable `skills/` and `mcp.json` at the root,
plus Lola's commands, agents, and instructions under the `dev.getlola`
extension namespace. An Agent Skill is a standalone `SKILL.md` with optional
supporting files. An AI Context Module is Lola's legacy layout - it wraps one
or more skills alongside `AGENTS.md`, `commands/`, and `mcps.json` inside a
`module/` directory, and now requires `lola mod init --format lola`.

## Initialize a Module

```bash
lola mod init my-plugin
```

By default this emits an Agent Plugins 1.0 package:

```text
my-plugin/
  plugin.json
  skills/
    example-skill/
      SKILL.md
  mcp.json
  dev.getlola/
    commands/
      example-command.md
    agents/
      example-agent.md
    AGENTS.md
```

The `name` in `plugin.json` is the module identity used by Lola when the
package is registered. Portable skills and MCP servers stay at the package
root. Lola-specific commands, agents, and instructions live in Lola's
`dev.getlola` extension namespace.

## Initialize a Legacy AI Context Module

```bash
lola mod init my-module --format lola
```

This creates Lola's legacy AI Context Module structure:

```
my-module/
  module/
    AGENTS.md           # AI main spec
    skills/
      example-skill/
        SKILL.md        # Skill following agentskills.io
    commands/
      example-command.md
    agents/
      example-agent.md
    mcps.json           # MCP settings
```

## Edit the skill

Edit your skill's `SKILL.md` following the [AgentSkills.io](https://agentskills.io/specification) standard:

```markdown
---
name: my-skill
description: When to use this skill
---

# My Skill

Instructions for the AI assistant...
```

## Add supporting files

Each skill can have its own `scripts/`, `reference/`, and `assets/` directories:

```
my-skill/
  SKILL.md
  scripts/           # Executable scripts
  reference/         # Documentation
  assets/            # Other supporting files
```

Reference them with relative paths in your `SKILL.md`:

```markdown
Use the helper script: `./scripts/helper.sh`
```

## Add an AGENTS.md

The `AGENTS.md` provides module-level context that applies across all skills in the module. This is what elevates a collection of skills into an AI Context Module.

## Add slash commands

Slash commands are custom commands that can be invoked with `/command-name` in AI assistants. Claude Code, Cursor, and Gemini CLI all support them. Create markdown files in `commands/`:

```markdown
---
description: Review a pull request
argument-hint: <pr-number>
---

Review PR #$ARGUMENTS and provide feedback.
```

Use `$ARGUMENTS` for all args or `$1`, `$2` for positional. Lola automatically converts commands to each assistant's native format (markdown for Claude Code and Cursor, TOML for Gemini CLI).

## Register and install

```bash
lola mod add ./my-module
lola install my-module
```

See [Skill Format](skill-format.md) for details on the SKILL.md specification.
