# Tasks

- [x] Resolve module format inconsistency (Codex #1)
- [x] Unify competing module concepts (Codex #2) - Already resolved: docs/, modules/ removed
- [x] Fix release hygiene and metadata (Codex #3)
- [ ] Standardize error handling strategy (Claude #1)
- [x] Extract shared ManagedSectionTarget base class (Claude #2)
- [ ] Refactor large functions into smaller units (Claude #3)
- [x] Fix leaky abstraction in Strategy pattern (Gemini #1)
- [ ] Add tests for concrete target implementations (Gemini #2)
- [ ] Improve error handling and observability (Gemini #3)

---

# Feedback from Codex

## 1. Module Format Inconsistency

**Location:** `src/lola/cli/mod.py:275`, `src/lola/models.py:115`, `src/lola/cli/install.py:94`, `README.md:201`

**Issue:** The module format is internally inconsistent. `lola mod init` scaffolds skills at the module root, but `Module.from_path()` only discovers skills under `skills/<name>/`, and install errors with a manifest that isn't actually used.

**Impact:** A freshly initialized module can fail discovery/validation/installation depending on whether it has commands/agents, and the docs reinforce conflicting layouts.

**Recommendation:** Make the module format internally consistent by aligning `lola mod init`, `Module.from_path()`, and the install command to use the same structure.

---

## 2. Competing Module Concepts

**Location:** `README.md`, `docs/modules.md:19`, `examples/`, `modules/chef-buddy/`

**Issue:** There are two competing "Lola module" concepts:
- "Skills/commands/agents modules" (README + examples)
- "Lazy context modules" using `.lolas/` + `modules/lolamod.yml` (docs + modules/chef-buddy)

**Impact:** This will confuse users immediately because the CLI/documentation surface area points to different structures and even different commands.

**Recommendation:** Pick one "Lola module" concept and align docs/examples around it.

---

## 3. Release Hygiene and Metadata

**Location:** `.gitignore:2`, `README.md`, `pyproject.toml:22`, `pyproject.toml:49`

**Issue:** 
- The repo contains compiled artifacts like `src/lola/__pycache__/config.cpython-314.pyc` (and many more) despite `.gitignore`
- `README.md` claims a GPL license but there's no LICENSE file in the repo
- `pyproject.toml` duplicates dev deps in two places with different minimums

**Impact:** Red flag for packaging/distribution cleanliness and makes contributor setup harder than it needs to be.

**Recommendation:** Remove compiled artifacts, add LICENSE file, and consolidate dev dependencies in `pyproject.toml`.

---

# Feedback from Claude

## 1. Inconsistent Error Handling Strategy

**Location:** `src/lola/cli/mod.py`, `src/lola/models.py`, `src/lola/parsers.py`

**Issue:** The codebase mixes three different approaches to error handling:
- `SystemExit(1)` - Used in some CLI commands
- Return tuples - `(False, "error message")` pattern in validation
- Raised exceptions - `ValueError`, etc.

**Examples:**
- `cli/mod.py` uses `raise SystemExit(1)` directly
- `models.py::validate()` returns `tuple[bool, list[str]]`
- `parsers.py` raises `ValueError` for security violations

**Impact:** This makes it difficult to:
- Predict how functions fail
- Write consistent calling code
- Chain operations together

**Recommendation:** Define a custom exception hierarchy (e.g., `LolaError`, `ModuleNotFoundError`, `ValidationError`) and use consistently. Reserve exit codes for the CLI layer only.

---

## 2. Code Duplication Between Gemini and OpenCode Targets

**Location:** `src/lola/targets.py`

**Issue:** `targets.py` has substantial duplication between `GeminiTarget` and `OpenCodeTarget`:

| Shared Pattern                      | Location             |
|-------------------------------------|----------------------|
| START_MARKER / END_MARKER constants | Both classes         |
| HEADER template                     | Nearly identical     |
| generate_skills_batch() logic       | ~50 lines duplicated |
| remove_skill() implementation       | Similar logic        |
| Managed section parsing             | Repeated pattern     |

Both targets implement the "managed section in a markdown file" pattern.

**Impact:** This violates DRY and means bug fixes or format changes must be applied twice.

**Recommendation:** Extract a `ManagedSectionTarget` base class or mixin that handles the common file-with-markers pattern.

---

## 3. Large Functions That Do Too Much

**Location:** `src/lola/cli/install.py`, `src/lola/targets.py`

**Issue:** Several functions exceed 100 lines and handle multiple responsibilities:

| Function                           | Lines | Responsibilities                                                  |
|------------------------------------|-------|-------------------------------------------------------------------|
| cli/install.py::update_cmd()       | ~307  | Validation, diffing, user prompts, installation, registry updates |
| targets.py::install_to_assistant() | ~150  | Target resolution, batch handling, skill/command/agent loops      |

**Impact:** These large functions are:
- Hard to test in isolation
- Difficult to understand at a glance
- Prone to accumulating more responsibilities over time

**Recommendation:** Extract helper functions like `_validate_update_candidates()`, `_prompt_for_selection()`, `_perform_installation()` to create smaller, focused units.

---

# Feedback from Gemini

## 1. Leaky Abstraction in the Strategy Pattern

**Location:** `src/lola/targets.py`, `src/lola/cli/install.py`

**Issue:** The project uses a Strategy pattern (`AssistantTarget` protocol) to support different AI assistants, but the abstraction is broken by explicit type checks.

**Violation:** The code frequently uses `isinstance(target, (GeminiTarget, OpenCodeTarget))` to trigger special "batch processing" logic (e.g., in `_install_skills` and `update_cmd`).

**Impact:** This violates the Open/Closed Principle and Liskov Substitution Principle. Adding a new assistant that requires batching would require modifying the core installer logic, increasing the risk of regression. The "installer" should not know about the implementation details of specific targets.

**Recommendation:** Refactor the Strategy pattern to eliminate type checks. Consider adding a protocol method like `requires_batch_processing()` or similar to handle batching through the interface.

---

## 2. Lack of Tests for Concrete Implementations

**Location:** `tests/` vs `src/lola/targets.py`

**Issue:** While the CLI and higher-level logic are tested, the concrete implementations of the targets are not.

**Missing Coverage:** There are no unit tests for `ClaudeCodeTarget`, `CursorTarget`, or `GeminiTarget`. The existing integration tests (e.g., `test_cli_install.py`) completely mock these classes.

**Impact:** Critical logic—such as path rewriting, Frontmatter parsing, and file copying—is unverified. If a bug is introduced in how `GeminiTarget` parses a skill file, the test suite will likely still pass because it uses a mock that always returns `True`.

**Recommendation:** Add unit tests for each concrete target implementation to verify path rewriting, Frontmatter parsing, and file copying logic.

---

## 3. Weak Error Handling and Observability

**Location:** `src/lola/targets.py`

**Issue:** Core functions rely on returning `bool` (`True`/`False`) to indicate success or failure instead of using Exceptions or Result objects.

**Detail:** Functions like `generate_skill` return `False` if anything goes wrong (source missing, permission denied, parse error), effectively swallowing the error message.

**Impact:** This makes debugging extremely difficult for users and developers. The CLI cannot tell the user why an installation failed (e.g., "Permission denied" vs. "Invalid Frontmatter"), only that it did. It also leads to fragile code where the caller has to guess the failure reason.

**Recommendation:** Replace boolean return values with exceptions or Result objects that carry error information, enabling proper error messages and debugging.
