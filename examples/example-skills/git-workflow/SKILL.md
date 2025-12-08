---
name: git-workflow
description: Git workflow best practices including branching strategies, commit messages, and pull requests. Use when creating branches, writing commits, making PRs, or resolving merge conflicts.
---

# Git Workflow Skill

Provides guidance on Git workflow best practices.

## Capabilities

- Suggests appropriate branch names based on ticket/issue types
- Helps format commit messages following conventional commits
- Guides through the PR creation process
- Provides merge conflict resolution strategies

## Branch Naming

Use descriptive branch names with prefixes:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/changes

Example: `feature/add-user-authentication`

## Commit Messages

Follow conventional commits format:
```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Pull Request Guidelines

1. Use a clear, descriptive title
2. Reference related issues
3. Provide context in the description
4. Request appropriate reviewers
5. Ensure CI passes before requesting review
