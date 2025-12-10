---
description: Review a pull request and provide structured feedback
argument-hint: <pr-number>
---

Review pull request #$ARGUMENTS.

## Task

1. Fetch the PR diff and description using git/gh commands
2. Analyze the changes for:
   - Code quality issues
   - Potential bugs
   - Security concerns
   - Performance implications
3. Provide constructive feedback with specific suggestions

## Output Format

Structure your review as:
- **Summary**: 1-2 sentence overview of the changes
- **Key Concerns**: Any issues that need addressing (if any)
- **Suggestions**: Actionable improvements
- **Verdict**: Approve / Request Changes / Comment
