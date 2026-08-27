# Lola - AI Context Package Manager

**Write Agent Skills and Contexts once, use everywhere.**

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/13138/badge)](https://www.bestpractices.dev/projects/13138)
[![Matrix](https://img.shields.io/badge/chat-Matrix-blue?logo=matrix)](https://matrix.to/#/#lola-ai:matrix.org)

Lola is a universal AI Package Manager. If an agent's skills were an RPM, Lola is the DNF for it. Write your [skills and context modules](https://lobstertrap.org/lola/concepts/skills-and-modules/) once as portable packages, then install them to any AI assistant or agent with a single command.

[![asciicast](https://asciinema.org/a/1035360.svg)](https://asciinema.org/a/1035360)

## Supported AI Assistants

| Assistant         | Skills | Commands | Agents |
| ----------------- | ------ | -------- | ------ |
| Claude Code       | Yes    | Yes      | Yes    |
| Copilot CLI       | Yes    | Yes      | Yes    |
| Copilot (VS Code) | Yes    | Yes¹     | Yes    |
| Cursor            | Yes    | Yes      | Yes    |
| Gemini CLI        | Yes    | Yes      | N/A    |
| OpenCode          | Yes    | Yes      | Yes    |

¹ Project scope only — VS Code has no user-scope location for slash commands.

GitHub Copilot has two targets that share the same `.github/` (project) and
`~/.copilot/` (user) files but differ in MCP handling:

- `copilot-cli` - writes MCP servers using the `mcpServers` key
  (`~/.copilot/mcp-config.json` for user scope).
- `copilot-vscode` - writes MCP servers to `.vscode/mcp.json` using VS
  Code's `servers` key. VS Code has no user-scope location for slash commands
  or MCP, so those are skipped (with a warning) when installing at user scope.

When no assistant is selected explicitly, `copilot-vscode` is preferred over
`copilot-cli` to avoid writing the same project files twice.

## Installation

```bash
# Recommended: install from PyPI
uv tool install lola-ai

# Or with pip
pip install lola-ai
```

> **Want the latest dev version?**
> `uv tool install git+https://github.com/LobsterTrap/lola`

## Quick Start

```bash
# Set up the official marketplace
lola market add general https://raw.githubusercontent.com/RedHatProductSecurity/lola-market/main/general-market.yml

# Add a module
lola mod add https://github.com/user/my-skills.git

# Install to all detected assistants
lola install my-skills

# Or install to a specific assistant
lola install my-skills -a claude-code
```

## Declarative Installation

Create a `.lola-req` in your project:

```
python-tools>=1.0.0
https://github.com/user/module.git@main
https://github.com/quay/ai-helpers.git@main#subdirectory=plugins/dev
https://github.com/user/repo.git#assistant=claude-code,cursor
```

URL fragments support:
- `subdirectory=path/to/module` - Install from a subdirectory in the repository
- `assistant=name1,name2` - Install to specific assistants

```bash
lola sync
```

## Documentation

Full documentation is available at **[lobstertrap.org/lola](https://lobstertrap.org/lola/)**.

### Official Lola Marketplace

We maintain an official, community-driven marketplace with curated modules at [github.com/RedHatProductSecurity/lola-market](https://github.com/RedHatProductSecurity/lola-market).

**Quick setup:**
```bash
lola market add general https://raw.githubusercontent.com/RedHatProductSecurity/lola-market/main/general-market.yml
```

This gives you instant access to community modules like workflow automation, code quality tools, and more. **We highly encourage you to:**
- Use modules from the official marketplace
- Contribute your own modules
- Share feedback and improvements

All contributions are welcome! See the [marketplace contributing guide](https://github.com/RedHatProductSecurity/lola-market/blob/main/CONTRIBUTING.md).

### Register a marketplace

```bash
# Add a marketplace from a URL
lola market add general https://raw.githubusercontent.com/RedHatProductSecurity/lola-market/main/general-market.yml

# List registered marketplaces
lola market ls
```

### Search and install from marketplace

```bash
# Search across all enabled marketplaces
lola mod search authentication

# Install directly from marketplace (auto-adds and installs)
lola install git-workflow -a claude-code
```

When a module exists in multiple marketplaces, Lola prompts you to select which one to use.

### Manage marketplaces

```bash
# Update marketplace cache
lola market update general

# Update all marketplaces
lola market update

# Disable a marketplace (keeps it registered but excludes from search)
lola market set --disable general

# Re-enable a marketplace
lola market set --enable general

# Remove a marketplace
lola market rm general
```

### Marketplace YAML format

Create your own marketplace by hosting a YAML file with this structure:

```yaml
name: My Marketplace
description: Curated collection of AI skills
version: 1.0.0
modules:
  - name: git-workflow
    description: Git workflow automation skills
    version: 1.0.0
    repository: https://github.com/user/git-workflow.git
    tags: [git, workflow]

  - name: code-review
    description: Code review assistant skills
    version: 1.2.0
    repository: https://github.com/user/code-review.git
    tags: [review, quality]
```

**Fields:**
- `name`: Marketplace display name
- `description`: What this marketplace provides
- `version`: Marketplace schema version
- `modules`: List of available modules
  - `name`: Module name (must match repository directory name)
  - `description`: Brief description shown in search results
  - `version`: Module version
  - `repository`: Git URL, zip/tar URL, or local path
  - `tags` (optional): Keywords for search

## CLI Reference

### Module Management (`lola mod`)

| Command | Description |
|---------|-------------|
| `lola mod add <source>` | Add a module from git, folder, zip, or tar |
| `lola mod ls` | List registered modules |
| `lola mod info <name>` | Show module details |
| `lola mod search <query>` | Search for modules across enabled marketplaces |
| `lola mod init [name]` | Initialize an Agent Plugins package |
| `lola mod init [name] --format lola` | Initialize a legacy Lola module |
| `lola mod init [name] -c` | Initialize with a command template |
| `lola mod update [name]` | Update module(s) from source |
| `lola mod rm <name>` | Remove a module |

### Marketplace Management (`lola market`)

| Command | Description |
|---------|-------------|
| `lola market add <name> <url>` | Register a marketplace from URL or local path |
| `lola market ls` | List all registered marketplaces |
| `lola market update [name]` | Update marketplace cache (or all if no name) |
| `lola market set --enable <name>` | Enable a marketplace for search and install |
| `lola market set --disable <name>` | Disable a marketplace (keeps it registered) |
| `lola market rm <name>` | Remove a marketplace |

### Installation

| Command | Description |
|---------|-------------|
| `lola install <module>` | Install skills and commands to all assistants |
| `lola install <module> -a <assistant>` | Install to specific assistant |
| `lola install <module> <path>` | Install to a specific project directory |
| `lola install <module> --scope user` | Install globally to user configuration directories |
| `lola uninstall <module>` | Uninstall skills and commands |
| `lola uninstall <module> --scope user` | Uninstall from user configuration directories |
| `lola installed` | List all installations |
| `lola update` | Regenerate assistant files |

#### Installation Scopes

Lola supports two installation scopes:

- **Project scope** (default): Installs to project directories (`.claude/`, `.cursor/`, `.opencode/`, etc.)
- **User scope**: Installs globally to user configuration directories

**User scope locations:**
- **Linux/Unix**: `~/.config/opencode/`, `~/.claude/`, `~/.cursor/`
- **macOS**: `~/.config/opencode/`, `~/.claude/`, `~/.cursor/`
- **Windows**: `~/.config/opencode/`, `~/.claude/`, `~/.cursor/`

Examples:
```bash
# Install to current project (default)
lola install my-module

# Install globally for your user  
lola install my-module --scope user

# Install to specific project
lola install my-module /path/to/project
```

## Creating a Module

### 1. Initialize

```bash
lola mod init my-skills
cd my-skills
```

This creates an Agent Plugins 1.0 package:

```text
my-skills/
  plugin.json          # Package manifest
  skills/
    example-skill/
      SKILL.md         # Initial skill (unless --no-skill)
  mcp.json             # MCP servers (unless --no-mcps)
  dev.getlola/         # Lola extension namespace
    commands/
      example-command.md # (unless --no-command)
    agents/
      example-agent.md   # (unless --no-agent)
    AGENTS.md            # (unless --no-instructions)
```

Use `--format lola` for the legacy `module/` layout.

### 2. Edit the skill

Edit `skills/example-skill/SKILL.md`:

```markdown
---
name: my-skills
description: Description shown in skill listings
---

# My Skill

Instructions for the AI assistant...
```

### 3. Add supporting files to skills

You can add additional files to any skill directory (scripts, templates, examples, etc.). Reference them using relative paths in your `SKILL.md`:

```markdown
# My Skill

Use the helper script: `./scripts/helper.sh`

Load the template from: `./templates/example.md`
```

**Path handling:** Use relative paths like `./file` or `./scripts/helper.sh` to reference files in the same skill directory. Each assistant handles these differently:

| Assistant | Skill Location | Supporting Files | Path Behavior |
|-----------|---------------|------------------|---------------|
| Claude Code | `.claude/skills/<skill>/SKILL.md` | Copied with skill | Paths work as-is |
| Cursor | `.cursor/rules/<skill>.mdc` | Stay in `.lola/modules/` | Paths rewritten automatically |
| Gemini | `GEMINI.md` (references only) | Stay in `.lola/modules/` | Paths work (SKILL.md read from source) |
| OpenCode | `AGENTS.md` (references only) | Stay in `.lola/modules/` | Paths work (SKILL.md read from source) |

- **Claude Code** copies the entire skill directory, so relative paths like `./scripts/helper.sh` work because the files are alongside `SKILL.md`
- **Cursor** only copies the skill content to an `.mdc` file, so Lola rewrites `./` paths to point back to `.lola/modules/<module>/skills/<skill>/`
- **Gemini/OpenCode** don't copy skills—they add entries to `GEMINI.md`/`AGENTS.md` that tell the AI to read the original `SKILL.md` from `.lola/modules/`, so relative paths work from that location

Example skill structure:

```
my-skills/
  skills/
    example-skill/
      SKILL.md
      scripts/
        helper.sh
      templates/
        example.md
```

### 4. Add more skills

Create additional skill directories under `skills/`, each with a `SKILL.md`:

```
my-skills/
  skills/
    example-skill/
      SKILL.md
    git-workflow/
      SKILL.md
    code-review/
      SKILL.md
```

### 5. Add slash commands

Create a `commands/` directory with markdown files:

```
my-skills/
  skills/
    example-skill/
      SKILL.md
  commands/
    review-pr.md
    quick-commit.md
```

Command files use YAML frontmatter:

```markdown
---
description: Review a pull request
argument-hint: <pr-number>
---

Review PR #$ARGUMENTS and provide feedback.
```

> **Note:** Modules use auto-discovery. Skills, commands, and agents are automatically detected from the directory structure. No manifest file is required.

### 6. Add to registry and install

```bash
lola mod add ./my-skills
lola install my-skills
```

## Module Structure

```
my-module/
  skills/            # Skills directory
    skill-name/
      SKILL.md       # Required: skill definition
      scripts/       # Optional: supporting files
      templates/     # Optional: templates
  commands/          # Optional: slash commands
    review-pr.md
    quick-commit.md
  agents/            # Optional: subagents
    my-agent.md
```

> **Note:** Modules use auto-discovery. Skills are discovered from `skills/<name>/SKILL.md`, commands from `commands/*.md`, and agents from `agents/*.md`. No manifest file is required.

### SKILL.md

```markdown
---
name: skill-name
description: When to use this skill
---

# Skill Title

Your instructions, workflows, and guidance for the AI assistant.

Reference supporting files using relative paths:
- `./scripts/helper.sh` - files in the same skill directory
- `./templates/example.md` - subdirectories are supported
```

**Supporting files:** You can include scripts, templates, examples, or any other files in your skill directory. Use relative paths like `./file` or `./scripts/helper.sh` in your `SKILL.md` to reference them. These paths are automatically rewritten for different assistant types during installation.

### Command Files

```markdown
---
description: What this command does
argument-hint: <required> [optional]
---

Your prompt template here. Use $ARGUMENTS for all args or $1, $2 for positional.
```

**Argument variables:**
- `$ARGUMENTS` - All arguments as a single string
- `$1`, `$2`, `$3`... - Positional arguments

Commands are automatically converted to each assistant's format:
- Claude/Cursor: Markdown with frontmatter (pass-through)
- Gemini: TOML with `{{args}}` substitution

## How It Works

1. **Marketplaces**: Register catalogs at `~/.lola/market/` with cached data at `~/.lola/market/cache/`
2. **Discovery**: Search across enabled marketplace caches to find modules
3. **Registry**: Modules are stored in `~/.lola/modules/`
4. **Installation**: Skills and commands are converted to each assistant's native format
5. **Prefixing**: Skills and commands are prefixed with module name to avoid conflicts (e.g., `mymodule-skill`)
6. **Scopes**: 
   - **Project scope** (default): Copies modules to `.lola/modules/` within the project
   - **User scope**: Installs globally to platform-appropriate user config directories
7. **Updates**: `lola mod update` re-fetches from original source; `lola update` regenerates files; `lola market update` refreshes marketplace caches

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct v2.1](CODE_OF_CONDUCT.md).

## Security

For reporting vulnerabilities, see [SECURITY.md](SECURITY.md).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Governance

Lola is governed by its maintainers. See [GOVERNANCE.md](GOVERNANCE.md) for the project's roles, decision-making process, and release cadence.

## Community

Join the community on Matrix: [#lola-ai:matrix.org](https://matrix.to/#/#lola-ai:matrix.org)

## License

[Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)

## Authors

- Igor Brandao
- Katie Mulliken
