# Feature Specification: Improved Module Init Template

**Feature Branch**: `001-mod-init-template`
**Created**: 2025-12-18
**Status**: Draft
**Input**: User description: "Build a spec for the lola modules that is easy to use. Users should be able to run `lola mod init` and have a full template that they can modify for their usecase. Files like AGENTS.md should be in a folder so that the user can modify it without affecting any running coding agents."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initialize Complete Module Template (Priority: P1)

A module author wants to quickly scaffold a new lola module with all the standard components (skills, commands, agents, instructions, MCP servers) pre-configured with helpful examples and documentation. They run `lola mod init` and get a complete, well-documented template that they can immediately customize.

**Why this priority**: This is the core functionality - providing a complete, usable template is the primary value proposition. Without a good template, users must read extensive documentation or reverse-engineer existing modules.

**Independent Test**: Can be fully tested by running `lola mod init my-module` and verifying all expected files/directories are created with useful content.

**Acceptance Scenarios**:

1. **Given** an empty directory, **When** the user runs `lola mod init my-module`, **Then** a `my-module/` directory is created containing:
   - `README.md` at the root explaining the module (not imported by lola)
   - `module/` subdirectory containing all lola-importable content:
     - `module/skills/` directory with an example skill containing SKILL.md
     - `module/commands/` directory with an example command
     - `module/agents/` directory with an example agent
     - `module/mcps.json` with example MCP server configuration
     - `module/AGENTS.md` with module-level instructions

2. **Given** the initialized module, **When** the user opens any template file, **Then** the file contains:
   - Clear placeholder text indicating what to replace
   - Working example content that can be used as-is for testing
   - Comments/documentation explaining the purpose of each section

3. **Given** the user wants to initialize in the current directory, **When** they run `lola mod init` without a name, **Then** the current directory is scaffolded using its name as the module name.

---

### User Story 2 - Edit Module Without Affecting Running Agents (Priority: P2)

A module author is actively developing their module while a coding agent (like Claude Code) is running and has loaded the module's instructions file. They want to edit the AGENTS.md file without the changes being picked up mid-session by the running agent, which could cause confusion or errors.

**Why this priority**: This addresses a real pain point where editing files that are actively being read by coding agents can cause unpredictable behavior. Isolating all lola content in a `module/` subdirectory prevents accidental interference and allows the repo to have its own README, build files, etc.

**Independent Test**: Can be tested by verifying all lola content is created in `module/` subdirectory and that `lola install` correctly reads from this location.

**Acceptance Scenarios**:

1. **Given** a module initialized with `lola mod init`, **When** the user looks for lola-importable content, **Then** all content (AGENTS.md, skills/, commands/, agents/, mcps.json) is located under `module/` subdirectory.

2. **Given** a module with `module/AGENTS.md`, **When** the user runs `lola install <module>`, **Then** the installation process correctly reads instructions from `module/AGENTS.md`.

3. **Given** a running coding agent that has loaded module instructions, **When** the user edits `module/AGENTS.md`, **Then** the agent's context is not affected (the file is not in a location the agent automatically monitors).

4. **Given** a module repo, **When** the user wants to add repo-level documentation or build tooling, **Then** they can add files at the root without affecting lola imports.

---

### User Story 3 - Selective Component Initialization (Priority: P3)

A module author only needs specific components (e.g., just skills, or just commands). They want to initialize a module with only the components they need, without creating unnecessary empty directories or placeholder files.

**Why this priority**: Provides flexibility for users who know exactly what they need. The full template (P1) covers most users, but power users benefit from fine-grained control.

**Independent Test**: Can be tested by running `lola mod init --no-agent --no-mcps` and verifying only requested components are created.

**Acceptance Scenarios**:

1. **Given** the user only needs skills, **When** they run `lola mod init --no-command --no-agent --no-mcps`, **Then** only `module/skills/` directory and `module/AGENTS.md` are created.

2. **Given** the user wants no example content, **When** they run `lola mod init --minimal`, **Then** empty directory structures are created without example files.

---

### Edge Cases

- What happens when the target directory already exists? The command should fail with a clear error message rather than overwriting.
- What happens when the user runs `lola mod init` in a directory that already has a partial module structure? The command MUST prompt the user for each conflicting file, asking whether to overwrite, skip, or abort the entire operation.
- What happens when `module/` directory exists but some content is missing? The command should create only the missing files/directories.
- What happens when using both `--no-instructions` and other flags? The `--no-instructions` flag should take precedence for AGENTS.md creation.
- What happens when `lola install` encounters a legacy module without `module/` subdirectory? The command MUST fail with an error message explaining the required structure and providing migration instructions (e.g., "Move your skills/, commands/, agents/, AGENTS.md into a module/ subdirectory").
- What happens when installing an MCP server whose name conflicts with an existing MCP? The command MUST prompt the user to overwrite the existing MCP or skip installing the conflicting one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a complete module directory structure when `lola mod init` is run without exclusion flags.
- **FR-002**: System MUST place all lola-importable content (AGENTS.md, skills/, commands/, agents/, mcps.json) inside a `module/` subdirectory.
- **FR-003**: System MUST generate example content for each component (skill, command, agent, MCP server, instructions) that serves as both documentation and working template.
- **FR-004**: System MUST allow users to skip specific components using `--no-skill`, `--no-command`, `--no-agent`, `--no-mcps`, `--no-instructions` flags.
- **FR-005**: System MUST update the installation logic to read content from the `module/` subdirectory.
- **FR-006**: System MUST generate a README.md at the repo root (outside `module/`) explaining the module and how to customize it.
- **FR-007**: System MUST use descriptive placeholder text that clearly indicates what the user should replace (e.g., `[REPLACE: Your skill description]`).
- **FR-008**: System MUST display a helpful summary after initialization showing what was created and suggested next steps.
- **FR-009**: System MUST support a `--minimal` flag to create directory structure without example content.
- **FR-010**: System MUST fail with a clear error message and migration instructions when `lola install` encounters a module without the required `module/` subdirectory structure.
- **FR-011**: System MUST prompt the user interactively when `lola mod init` encounters existing files, offering options to overwrite, skip, or abort for each conflict.
- **FR-012**: System MUST support a `--force` flag that overwrites all conflicting files without prompting, enabling non-interactive/CI usage.
- **FR-013**: System MUST generate `mcps.json` template as a commented placeholder showing the schema structure with explanatory notes, not a working example.
- **FR-014**: System MUST install MCP servers using their original names (not prefixed with module name).
- **FR-015**: System MUST prompt the user to overwrite when installing an MCP server with a name that conflicts with an existing MCP configuration.
- **FR-016**: System MUST use dot-separated naming convention for installed components: `module-name.component-name` (e.g., `.claude/commands/my-module.my-command.md`, `.claude/skills/my-module.my-skill/`).

### Key Entities

- **Module Repository**: The top-level directory that can contain repo-level files (README.md, build files) and a `module/` subdirectory with lola content.
- **Module Content**: All lola-importable content located under the `module/` subdirectory.
- **Skill**: A folder under `module/skills/` containing a SKILL.md file with frontmatter and markdown content.
- **Command**: A markdown file under `module/commands/` with frontmatter defining a slash command.
- **Agent**: A markdown file under `module/agents/` with frontmatter defining a subagent.
- **MCP Server**: Configuration in `module/mcps.json` defining external tool servers.
- **Instructions**: Module-level guidance in `module/AGENTS.md` describing when and how to use the module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can initialize a complete module template in under 10 seconds by running a single command.
- **SC-002**: 90% of initialized template files require no structural changes to be valid for installation (only content replacement needed).
- **SC-003**: Users can edit files in `module/` without any impact on concurrently running coding agents that have loaded the module.
- **SC-004**: README.md and example files reduce time-to-first-working-module by providing clear, actionable guidance.
- **SC-005**: Users report the template structure as "easy to understand" based on self-documenting content and clear placeholder text.
- **SC-006**: Module repos can include their own tooling (build scripts, tests, CI config) at the root without interfering with lola imports.

## Clarifications

### Session 2025-12-18

- Q: When `lola install` encounters an existing module without the new `module/` subdirectory structure, what should happen? → A: Require migration - fail with error and migration instructions if `module/` subdirectory not found.
- Q: When `lola mod init` finds an existing `module/` directory with some but not all components, should it merge by adding missing components or treat it as an error? → A: Prompt - ask user whether to merge or abort for each conflict.
- Q: How should `lola mod init` behave in non-interactive environments when conflicts exist? → A: Add `--force` flag to overwrite all conflicts without prompting.
- Q: What type of MCP server example should the template include? → A: Commented placeholder showing schema structure with explanatory notes. Additionally, MCP installation should NOT prefix names with module name - use the MCP name as-is, and prompt user to overwrite if there's a name conflict with an existing MCP.
- Q: What naming convention should be used for installed module components (skills, commands, agents)? → A: Use dot-separated format: `module-name.component-name` (e.g., `my-module.my-command`).

## Assumptions

- Users are familiar with markdown file format.
- The `module/` subdirectory convention is intuitive for isolating lola-importable content.
- Coding agents (like Claude Code, Cursor) typically monitor files at the project root or in specific directories but not arbitrary subdirectories like `module/`.
- Module authors may want to include repo-level tooling (tests, CI, build scripts) that should not be imported by lola.
- Existing modules will need to be migrated to the new `module/` structure (breaking change is acceptable).
