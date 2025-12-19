---
description: Create a conventional commit with an auto-generated message
argument-hint: "[type] [scope]"
---

Create a git commit for the current staged changes.

## User-provided arguments

> $ARGUMENTS

## Instructions

1. Run `git diff --staged` to see what will be committed
2. If there are no staged changes, inform the user and stop
3. Analyze the changes and determine the appropriate commit type:
   - feat: A new feature
   - fix: A bug fix
   - docs: Documentation only changes
   - style: Code style changes (formatting, etc.)
   - refactor: Code change that neither fixes a bug nor adds a feature
   - test: Adding or updating tests
   - chore: Maintenance tasks

4. Check the user-provided arguments above:
   - If a type was provided (e.g., "feat", "fix"), use it
   - If a scope was also provided (e.g., "feat api"), use both
   - If empty or not provided, infer the type from the changes

5. Generate a concise commit message following the Conventional Commits format:
   ```
   <type>(<scope>): <description>
   ```
   Omit the scope if not applicable.

6. Show the proposed commit message and ask for confirmation before committing
7. Run the commit with the approved message
