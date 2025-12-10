---
description: Create a conventional commit with an auto-generated message
argument-hint: [type]
---

Create a git commit for the current staged changes.

## Instructions

1. Run `git diff --staged` to see what will be committed
2. Analyze the changes and determine the appropriate commit type:
   - feat: A new feature
   - fix: A bug fix
   - docs: Documentation only changes
   - style: Code style changes (formatting, etc.)
   - refactor: Code change that neither fixes a bug nor adds a feature
   - test: Adding or updating tests
   - chore: Maintenance tasks

3. If $ARGUMENTS is provided, use it as the commit type. Otherwise, infer it.

4. Generate a concise commit message following the Conventional Commits format:
   ```
   <type>: <description>
   ```

5. Run the commit with the generated message
