---
description: Review a pull request and provide structured feedback
argument-hint: <pr-number>
---

Review pull request #$ARGUMENTS.

## Task

1. Fetch the PR details using `gh pr view $ARGUMENTS` to understand the changes
2. Check out the PR locally using `gh pr checkout $ARGUMENTS`
3. Analyze the diff for:
   - Code quality issues
   - Potential bugs
   - Security concerns
   - Performance implications
4. Check test coverage:
   - Identify new features, endpoints, or significant functionality added
   - Check if corresponding tests were added or updated
   - Flag any new features lacking test coverage as a concern
5. Run the test suite to verify tests pass:
   - Determine the project's test runner (pytest, jest, go test, etc.)
   - Run tests related to the changed files if possible, otherwise run the full suite
   - Report any test failures
6. Provide constructive feedback with specific suggestions
7. Return to the original branch when done (note the branch name before checkout)

## Output Format

Structure your review as:
- **Summary**: 1-2 sentence overview of the changes
- **Test Coverage**: List new features and whether tests exist for each
- **Test Results**: Pass/Fail status and any failure details
- **Key Concerns**: Any issues that need addressing (if any)
- **Suggestions**: Actionable improvements
- **Verdict**: Approve / Request Changes / Comment

## Important

If new functionality is added without corresponding tests, this should be flagged as a key concern and influence the verdict toward "Request Changes" unless there's a valid reason (e.g., trivial changes, config-only updates).
