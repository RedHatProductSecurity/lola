# Git Module Example

This is an example Lola module demonstrating the standard module structure with skills, commands, and agents.

## Module Structure

```
git-module/
  module/
    AGENTS.md              # Module description (used by some assistants)
    skills/
      git-cheatsheet/
        SKILL.md           # Git command reference
        git-hooks.md       # Supporting documentation
    commands/
      quick-commit.md      # /quick-commit slash command
      review-pr.md         # /review-pr slash command
    agents/
      git-doctor.md        # git-doctor subagent
```

## What's Included

### Skill: git-cheatsheet

A comprehensive Git command reference covering:

- Repository setup and cloning
- Staging and committing
- Branching and switching
- Diffing changes and commits
- Discarding and restoring changes
- History editing and rebasing
- Remote operations (push, pull, fetch)
- Git configuration

**Usage**: The AI loads this skill when working with git commands, version control, or repository management.

### Command: /quick-commit

Auto-generates conventional commit messages for staged changes.

**Usage**: `/quick-commit [type] [scope]`

The command:
1. Analyzes staged changes with `git diff --staged`
2. Determines the appropriate commit type (feat, fix, docs, etc.)
3. Generates a conventional commit message
4. Asks for confirmation before committing

### Command: /review-pr

Provides structured code review for pull requests with test coverage analysis.

**Usage**: `/review-pr <pr-number>`

The command:
1. Fetches PR details using `gh pr view`
2. Checks out the PR locally
3. Analyzes for code quality, bugs, security, and performance
4. Verifies test coverage for new features
5. Runs the test suite
6. Outputs a structured review with verdict

### Agent: git-doctor

A git troubleshooting specialist for diagnosing and fixing common git problems.

**Handles**:
- Detached HEAD states
- Lost or corrupted commits
- Merge conflicts and failed rebases
- Undo operations (commits, changes, resets)
- Branch problems
- Remote and push issues
- Repository recovery

## Installation

Register and install the module:

```bash
# Register the module
lola mod add ./examples/git-module/module

# Install to your project
lola install git-module -a claude-code
```

## Creating Your Own Module

Use this example as a template. Key points:

1. **Skills** go in `skills/<skill-name>/SKILL.md` with YAML frontmatter containing a `description` field
2. **Commands** go in `commands/<command-name>.md` with `description` and optional `argument-hint` frontmatter
3. **Agents** go in `agents/<agent-name>.md` with a `description` in frontmatter
4. **AGENTS.md** at the root provides module-level documentation

See the [Lola documentation](../../README.md) for more details on module creation.