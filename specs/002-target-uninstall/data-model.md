# Data Model: Target Uninstall Functions

**Feature**: 002-target-uninstall
**Date**: 2025-12-18

## Entity Modifications

### AssistantTarget ABC (Extended)

The abstract base class gains two new abstract methods.

```
AssistantTarget (ABC)
├── Existing Methods
│   ├── remove_skill(dest_path: Path, skill_name: str) -> bool
│   ├── remove_instructions(dest_path: Path, module_name: str) -> bool
│   └── remove_mcps(dest_path: Path, module_name: str) -> bool
│
└── New Methods (FR-001, FR-002)
    ├── remove_command(dest_dir: Path, cmd_name: str, module_name: str) -> bool
    └── remove_agent(dest_dir: Path, agent_name: str, module_name: str) -> bool
```

### BaseAssistantTarget (Extended)

Default implementations for the new methods.

```
BaseAssistantTarget(AssistantTarget)
├── Existing Defaults
│   ├── remove_skill() -> delete skill directory
│   ├── remove_instructions() -> return False (override in mixin)
│   └── remove_mcps() -> return False (override in mixin)
│
└── New Defaults (FR-003, FR-004)
    ├── remove_command() -> delete file at get_command_filename() path
    └── remove_agent() -> delete file at get_agent_filename() path
```

## Method Specifications

### remove_command()

**Purpose**: Remove a command file for this assistant.

**Signature**:
```python
@abstractmethod
def remove_command(
    self,
    dest_dir: Path,
    cmd_name: str,
    module_name: str,
) -> bool:
    """Remove a command file for this assistant.

    Args:
        dest_dir: Directory containing commands (e.g., .claude/commands/)
        cmd_name: Unprefixed command name (e.g., "review-pr")
        module_name: Module name for filename construction

    Returns:
        True if removed or didn't exist (idempotent), False on error
    """
```

**Default Implementation**:
```python
def remove_command(
    self,
    dest_dir: Path,
    cmd_name: str,
    module_name: str,
) -> bool:
    filename = self.get_command_filename(module_name, cmd_name)
    cmd_file = dest_dir / filename
    if cmd_file.exists():
        cmd_file.unlink()
    return True  # Idempotent: success even if file didn't exist
```

### remove_agent()

**Purpose**: Remove an agent file for this assistant.

**Signature**:
```python
@abstractmethod
def remove_agent(
    self,
    dest_dir: Path,
    agent_name: str,
    module_name: str,
) -> bool:
    """Remove an agent file for this assistant.

    Args:
        dest_dir: Directory containing agents (e.g., .claude/agents/)
        agent_name: Unprefixed agent name (e.g., "code-reviewer")
        module_name: Module name for filename construction

    Returns:
        True if removed or didn't exist (idempotent), False on error
    """
```

**Default Implementation**:
```python
def remove_agent(
    self,
    dest_dir: Path,
    agent_name: str,
    module_name: str,
) -> bool:
    filename = self.get_agent_filename(module_name, agent_name)
    agent_file = dest_dir / filename
    if agent_file.exists():
        agent_file.unlink()
    return True  # Idempotent: success even if file didn't exist
```

## Orchestration Function

### uninstall_from_assistant()

**Purpose**: Orchestrate complete uninstall of a module from an assistant.

**Location**: `src/lola/targets/install.py`

**Signature**:
```python
def uninstall_from_assistant(
    installation: Installation,
    target: AssistantTarget,
    verbose: bool = False,
) -> int:
    """Uninstall a module from a specific assistant.

    Args:
        installation: The Installation record to uninstall
        target: The AssistantTarget to uninstall from
        verbose: Whether to print detailed output

    Returns:
        Count of items removed
    """
```

**Responsibilities**:
1. Remove skills via `target.remove_skill()`
2. Remove commands via `target.remove_command()` (NEW)
3. Remove agents via `target.remove_agent()` (NEW)
4. Remove MCPs via `target.remove_mcps()`
5. Remove instructions via `target.remove_instructions()`
6. Return total count of removed items

## Validation Rules

| Rule | Enforcement |
|------|-------------|
| dest_dir must be a valid Path | Type hint; pathlib handles |
| cmd_name/agent_name must not be empty | Caller responsibility |
| module_name must not be empty | Caller responsibility |
| Removal must be idempotent | Return True if file doesn't exist |

## State Transitions

No state changes - this feature operates on filesystem only. The `Installation` record in the registry is updated by the CLI after successful uninstall (existing behavior, unchanged).

```
Before Uninstall:
  .claude/commands/my-module.review-pr.md  [EXISTS]
  .claude/agents/my-module.code-reviewer.md [EXISTS]

After remove_command("review-pr", "my-module"):
  .claude/commands/my-module.review-pr.md  [DELETED]

After remove_agent("code-reviewer", "my-module"):
  .claude/agents/my-module.code-reviewer.md [DELETED]
```
