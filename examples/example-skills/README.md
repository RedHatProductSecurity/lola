# Example Skills Module

This is an example module demonstrating the lola package manager structure.

## Module Structure

```
example-skills/
├── .lola/
│   └── module.yml        # Module manifest
├── git-workflow/
│   └── SKILL.md         # Git workflow skill
├── code-review/
│   └── SKILL.md         # Code review skill
└── README.md            # This file
```

## Installation

```bash
# Add this module to your lola registry
lola mod add ./examples/example-skills

# Install to Claude Code (user scope)
lola install example-skills -a claude-code -s user

# Install to Cursor (project scope)
lola install example-skills -a cursor -s project ./my-project
```

## Skills Included

### git-workflow
Helps with Git workflow best practices including branching, commit messages, and PRs.

### code-review
Provides a framework for conducting thorough code reviews.
