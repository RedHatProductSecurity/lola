# Module Instructions Feature Spec

## Overview

Enable modules to include an `AGENTS.md` file that provides module-level context and usage instructions. When a module is installed, this content is automatically inserted into the appropriate assistant instruction file:

| Target | Instruction File |
|--------|------------------|
| claude-code | `CLAUDE.md` |
| cursor | `.cursor/rules/{module}-instructions.mdc` |
| gemini-cli | `GEMINI.md` |
| opencode | `AGENTS.md` |

> **Note**: While Cursor supports `AGENTS.md`, users have reported inconsistent automatic loading. Using `.mdc` rule files with `alwaysApply: true` provides more reliable behavior.

## Problem Statement

Currently, modules can define skills, commands, and agents, but there's no standard way to provide high-level guidance about **when** and **how** to use a module's capabilities together. For example, the git-module wants to communicate:

- "Use the git-cheatsheet skill for routine git operations"
- "Use /quick-commit for committing changes"
- "Delegate to git-doctor for diagnosing issues"

This context helps AI assistants make intelligent decisions about which capabilities to invoke.

## Example

### Module Structure

```
git-module/
  AGENTS.md           # ← NEW: Module-level instructions
  skills/
    git-cheatsheet/
      SKILL.md
  commands/
    quick-commit.md
  agents/
    git-doctor.md
```

### Example AGENTS.md Content

```markdown
# Git Module

This module provides agents, skills, and commands for git workflows and troubleshooting.

## When to Use

- **Routine git operations**: Load the `git-cheatsheet` skill for command syntax
- **Committing changes**: Use `/quick-commit` to auto-generate conventional commit messages
- **PR reviews**: Use `/review-pr <number>` for structured code review with test coverage analysis
- **Git problems**: Delegate to `git-doctor` for diagnosing issues like detached HEAD, lost commits, merge conflicts, or corrupted repos
```

## Design

### 1. Module Discovery

Update `Module.from_path()` in `models.py` to detect and track `AGENTS.md`:

```python
@dataclass
class Module:
    name: str
    path: Path
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    has_instructions: bool = False  # NEW: True if AGENTS.md exists
```

The `AGENTS.md` file is **optional**. Modules remain valid with just skills, commands, or agents.

### 2. Installation Registry

Update `Installation` model to track whether instructions were installed:

```python
@dataclass
class Installation:
    module_name: str
    assistant: str
    scope: str
    project_path: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    has_instructions: bool = False  # NEW
```

### 3. Target Implementation

#### 3.1 AssistantTarget Protocol Extension

Add new methods to the `AssistantTarget` protocol:

```python
class AssistantTarget(Protocol):
    # ... existing methods ...
    
    def get_instructions_path(self, project_path: str) -> Path:
        """Get the instructions file path (CLAUDE.md, GEMINI.md, AGENTS.md)."""
        ...
    
    def generate_instructions(
        self,
        source_path: Path,
        dest_file: Path,
        module_name: str,
    ) -> bool:
        """Generate/update module instructions in the assistant's instruction file."""
        ...
    
    def remove_instructions(
        self,
        dest_file: Path,
        module_name: str,
    ) -> bool:
        """Remove a module's instructions from the instruction file."""
        ...
```

#### 3.2 Managed Section Format

Instructions are inserted into a managed section with clear markers:

```markdown
<!-- lola:instructions:start -->
<!-- lola:module:git-module:start -->
# Git Module

This module provides agents, skills, and commands for git workflows...
<!-- lola:module:git-module:end -->

<!-- lola:module:python-tools:start -->
# Python Tools

This module provides Python development utilities...
<!-- lola:module:python-tools:end -->
<!-- lola:instructions:end -->
```

#### 3.3 Target-Specific Implementation

**Claude Code (CLAUDE.md)**
```python
class ClaudeCodeTarget(BaseAssistantTarget):
    INSTRUCTIONS_FILE = "CLAUDE.md"
    
    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / self.INSTRUCTIONS_FILE
    
    def generate_instructions(self, source_path: Path, dest_file: Path, module_name: str) -> bool:
        # Read AGENTS.md from module
        # Insert into managed section in CLAUDE.md
        ...
```

**Cursor (.cursor/rules/)**

Cursor's `.mdc` rule files with `alwaysApply: true` provide reliable instruction loading, avoiding the inconsistent behavior reported with `AGENTS.md`.

```python
class CursorTarget(BaseAssistantTarget):
    
    def get_instructions_path(self, project_path: str) -> Path:
        return Path(project_path) / ".cursor" / "rules"
    
    def generate_instructions(self, source_path: Path, dest_path: Path, module_name: str) -> bool:
        # Convert AGENTS.md to MDC format with alwaysApply: true
        # Save as .cursor/rules/{module_name}-instructions.mdc
        content = source_path.read_text()
        
        mdc_lines = [
            "---",
            f"description: {module_name} module instructions",
            "globs:",
            "alwaysApply: true",
            "---",
            "",
            content,
        ]
        
        dest_path.mkdir(parents=True, exist_ok=True)
        (dest_path / f"{module_name}-instructions.mdc").write_text("\n".join(mdc_lines))
        return True
    
    def remove_instructions(self, dest_path: Path, module_name: str) -> bool:
        mdc_file = dest_path / f"{module_name}-instructions.mdc"
        if mdc_file.exists():
            mdc_file.unlink()
            return True
        return False
```

**Gemini CLI (GEMINI.md)**
```python
class GeminiTarget(ManagedSectionTarget):
    INSTRUCTIONS_FILE = "GEMINI.md"
    # Reuse existing managed section infrastructure
    # Instructions go into a separate managed section from skills
```

**OpenCode (AGENTS.md)**
```python
class OpenCodeTarget(ManagedSectionTarget):
    INSTRUCTIONS_FILE = "AGENTS.md"
    # Reuse existing managed section infrastructure
    # Instructions go into a separate managed section from skills
```

### 4. Installation Flow

Update `install_to_assistant()` in `targets.py`:

```python
def install_to_assistant(
    module: Module,
    assistant: str,
    scope: str,
    project_path: Optional[str],
    local_modules: Path,
    registry: InstallationRegistry,
    verbose: bool = False,
) -> int:
    target = get_target(assistant)
    local_module_path = copy_module_to_local(module, local_modules)
    
    # Existing installation logic...
    installed_skills, failed_skills = _install_skills(...)
    installed_commands, failed_commands = _install_commands(...)
    installed_agents, failed_agents = _install_agents(...)
    
    # NEW: Install module instructions
    instructions_installed = False
    if module.has_instructions:
        instructions_path = local_module_path / "AGENTS.md"
        dest_file = target.get_instructions_path(project_path)
        instructions_installed = target.generate_instructions(
            instructions_path, dest_file, module.name
        )
    
    # Update registry with instructions status
    registry.add(Installation(
        module_name=module.name,
        assistant=assistant,
        scope=scope,
        project_path=project_path,
        skills=installed_skills,
        commands=installed_commands,
        agents=installed_agents,
        has_instructions=instructions_installed,  # NEW
    ))
```

### 5. Uninstallation Flow

Update uninstall logic to remove module instructions:

```python
def uninstall_from_assistant(
    installation: Installation,
    project_path: str,
) -> bool:
    target = get_target(installation.assistant)
    
    # Existing removal logic...
    
    # NEW: Remove module instructions
    if installation.has_instructions:
        dest_file = target.get_instructions_path(project_path)
        target.remove_instructions(dest_file, installation.module_name)
```

### 6. Update Flow

The `lola update` command regenerates assistant files from source modules. Instructions are regenerated along with skills, commands, and agents.

## Edge Cases

### Multiple Modules with Instructions

When multiple modules have AGENTS.md files, they're all included in the managed section, **sorted alphabetically by module name**:

```markdown
<!-- lola:instructions:start -->
<!-- lola:module:git-module:start -->
# Git Module
...
<!-- lola:module:git-module:end -->

<!-- lola:module:docker-module:start -->
# Docker Module
...
<!-- lola:module:docker-module:end -->
<!-- lola:instructions:end -->
```

### Existing Content in Instruction Files

If CLAUDE.md, GEMINI.md, or AGENTS.md already has content:
- Managed section is appended to the end
- Existing content outside the managed section is preserved
- Never overwrite user content

### Empty or Missing AGENTS.md

- If AGENTS.md doesn't exist: `has_instructions = False`, no instructions generated
- If AGENTS.md is empty: Treated as non-existent (skip)

### Cursor File-Per-Module Approach

Unlike other targets that use managed sections in a single file, Cursor generates one `.mdc` file per module. This means:
- Each module's instructions are in `.cursor/rules/{module}-instructions.mdc`
- Uninstalling a module simply deletes its `.mdc` file
- No need to parse/update managed sections

## CLI Output

Installation output should indicate instructions were installed:

```
$ lola install git-module -a claude-code
✓ Installed git-module
  claude-code (1 skill, 2 commands, 1 agent, instructions)
```

## Configuration (Future)

Allow modules to include a `.lolaignore` file to exclude files from installation:

```gitignore
# .lolaignore (in module root, future enhancement)

# Exclude module instructions from installation
AGENTS.md

# Exclude specific skills
skills/experimental-skill/

# Exclude draft commands
commands/wip-*.md
```

This gives module authors control over what gets installed, useful for:
- Keeping draft/experimental content out of installations
- Platform-specific exclusions
- Development-only files

## Validation

Add validation for AGENTS.md:
- Must be valid markdown
- Warn if file is very large (>10KB)

## Backward Compatibility

- Modules without AGENTS.md continue to work unchanged
- `has_instructions` defaults to `False` for existing registry entries
- Running `lola update` on existing installations will install instructions if the module now has AGENTS.md

## Testing

### Unit Tests

1. `test_module_from_path_with_instructions` - Module discovery finds AGENTS.md
2. `test_module_from_path_without_instructions` - Module without AGENTS.md
3. `test_generate_instructions_claude` - Claude Code target generates CLAUDE.md section
4. `test_generate_instructions_gemini` - Gemini target generates GEMINI.md section
5. `test_generate_instructions_opencode` - OpenCode target generates AGENTS.md section
6. `test_generate_instructions_cursor` - Cursor target generates .mdc file with alwaysApply: true
7. `test_remove_instructions` - Instructions are properly removed
8. `test_multiple_modules_instructions` - Multiple modules' instructions don't conflict
9. `test_preserve_existing_content` - User content outside managed section preserved

### Integration Tests

1. `test_install_uninstall_with_instructions` - Full install/uninstall cycle
2. `test_update_preserves_instructions` - `lola update` regenerates instructions
3. `test_update_installs_instructions` - `lola update` installs instructions if the module now has AGENTS.md

## Implementation Order

1. **Phase 1: Model Changes**
   - Add `has_instructions` to `Module` and `Installation`
   - Update `Module.from_path()` to detect AGENTS.md
   - Update `Installation.to_dict()` and `from_dict()`

2. **Phase 2: Claude Code Target (Hot Path)**
   - Implement `generate_instructions()` for ClaudeCodeTarget
   - Implement `remove_instructions()` for ClaudeCodeTarget
   - Wire up installation/uninstallation flow
   - **Full integration test**: Install git-module to claude-code, verify CLAUDE.md contains instructions

3. **Phase 3: ManagedInstructionsTarget Mixin**
   - Extract shared logic for managed instruction sections
   - Implement markers and content insertion/removal

4. **Phase 4: Remaining Target Implementations**
   - GeminiTarget: Generate GEMINI.md section (extend existing)
   - OpenCodeTarget: Generate AGENTS.md section (extend existing)
   - CursorTarget: Generate `.cursor/rules/{module}-instructions.mdc` file

5. **Phase 5: CLI Output**
   - Update `_print_summary()` to show instructions status

6. **Phase 6: Tests**
   - Unit tests for each component
   - Integration tests for full flow

## Open Questions

1. **Conflict resolution**: What if a user manually edits the managed section?
   - Decision: Regenerate on `lola install` or `lola update`; warn user that manual edits will be overwritten

2. **Max size warning threshold**: At what file size should we warn users about large instructions?
   - Decision: 10KB threshold


