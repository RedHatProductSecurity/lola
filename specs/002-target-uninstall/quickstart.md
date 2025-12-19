# Quickstart: Target Uninstall Functions

**Feature**: 002-target-uninstall
**Date**: 2025-12-18

## Overview

This feature adds `remove_command()` and `remove_agent()` methods to the target system, enabling consistent uninstall behavior across all AI assistant targets.

## User-Facing Behavior

**No changes for users.** The `lola uninstall` command works exactly the same:

```bash
# Uninstall a module from all targets
lola uninstall my-module

# Uninstall from specific target
lola uninstall my-module -a claude-code

# Force uninstall without confirmation
lola uninstall my-module -f
```

## Developer Usage

### Implementing a New Target

When creating a new `AssistantTarget`, you can now rely on default removal behavior:

```python
from lola.targets.base import BaseAssistantTarget

class MyNewTarget(BaseAssistantTarget):
    name = "my-target"
    supports_agents = True
    uses_managed_section = False

    def get_skill_path(self, project_path: str) -> Path:
        return Path(project_path) / ".my-target" / "skills"

    def get_command_path(self, project_path: str) -> Path:
        return Path(project_path) / ".my-target" / "commands"

    def get_agent_path(self, project_path: str) -> Path:
        return Path(project_path) / ".my-target" / "agents"

    # ... other required methods ...

    # remove_command() and remove_agent() are inherited from BaseAssistantTarget!
    # They use get_command_filename() and get_agent_filename() automatically.
```

### Custom Removal Logic

If your target needs custom removal (e.g., managed sections):

```python
class MyManagedTarget(BaseAssistantTarget):
    # ...

    def remove_command(
        self,
        dest_dir: Path,
        cmd_name: str,
        module_name: str,
    ) -> bool:
        """Custom removal for managed section commands."""
        # Your custom logic here
        managed_file = dest_dir / "commands.md"
        # ... remove from managed section ...
        return True
```

### Using the Orchestration Function

The new `uninstall_from_assistant()` function handles all removal:

```python
from lola.targets.install import uninstall_from_assistant, get_target

# Get the target and installation
target = get_target("claude-code")
installation = registry.find("my-module")[0]

# Uninstall everything
removed_count = uninstall_from_assistant(
    installation=installation,
    target=target,
    verbose=True,
)
print(f"Removed {removed_count} items")
```

## Testing

### Test remove_command()

```python
def test_remove_command_deletes_file(tmp_path):
    """Test that remove_command deletes the command file."""
    target = ClaudeCodeTarget()
    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)

    # Create a command file
    cmd_file = commands_dir / "my-module.review-pr.md"
    cmd_file.write_text("# Review PR Command")

    # Remove it
    result = target.remove_command(commands_dir, "review-pr", "my-module")

    assert result is True
    assert not cmd_file.exists()


def test_remove_command_idempotent(tmp_path):
    """Test that remove_command succeeds even if file doesn't exist."""
    target = ClaudeCodeTarget()
    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)

    # Remove non-existent file
    result = target.remove_command(commands_dir, "nonexistent", "my-module")

    assert result is True  # Idempotent - no error
```

### Test remove_agent()

```python
def test_remove_agent_deletes_file(tmp_path):
    """Test that remove_agent deletes the agent file."""
    target = ClaudeCodeTarget()
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    # Create an agent file
    agent_file = agents_dir / "my-module.code-reviewer.md"
    agent_file.write_text("# Code Reviewer Agent")

    # Remove it
    result = target.remove_agent(agents_dir, "code-reviewer", "my-module")

    assert result is True
    assert not agent_file.exists()


def test_remove_agent_no_support(tmp_path):
    """Test that remove_agent returns True for targets without agent support."""
    target = CursorTarget()  # Cursor doesn't support agents
    agents_dir = tmp_path / ".cursor" / "agents"

    result = target.remove_agent(agents_dir, "any-agent", "my-module")

    assert result is True  # No-op for unsupported targets
```

## Migration Notes

### Existing Tests

Update any tests that verify uninstall behavior to account for the new delegation:

```python
# Before: Testing inline file deletion
assert not (commands_dir / "my-module.cmd.md").exists()

# After: Same assertion, but now testing target.remove_command()
assert not (commands_dir / "my-module.cmd.md").exists()
```

### Existing Targets

No changes needed for existing targets (claude-code, cursor, gemini-cli, opencode). They inherit the default implementations from `BaseAssistantTarget`.

## Verification Checklist

After implementation, verify:

- [ ] `lola uninstall my-module` removes all commands
- [ ] `lola uninstall my-module` removes all agents
- [ ] `lola uninstall my-module -v` shows removal progress
- [ ] Uninstalling twice succeeds (idempotent)
- [ ] All existing tests pass
- [ ] New tests cover remove_command() and remove_agent()
