# Feature Specification: Module Marketplace

**Feature Branch**: `003-marketplace`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "Let's implement a marketplace command for lola.
This will allow lola to add modules and install modules from marketplaces.
Marketplaces will be a YAML file in the format to be defined, which will have
name, description, version and repo or path. When using lola market add
some-url that contains the YAML structure supported by the market, lola will be
able to search modules from such market using lola mod search some-module or
some-string. When using lola install mod-name, if the mod is not added, lola
will add the module and install as requested by the user. For example, lola
install -a assistant will be able to install a module straight from the
marketplace to the assistant. It will do that by first auto-adding the module
using lola mod add repo/path and after installing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register Marketplace (Priority: P1)

A user wants to register a module marketplace so they can discover and install
modules from a curated collection. The user provides a name and URL to a
marketplace definition file, and Lola registers it for future searches and
installations.

**Why this priority**: This is the foundational capability that enables all
other marketplace features. Without marketplace registration, there's no source
to search or install from.

**Independent Test**: Can be fully tested by running
`lola market add <name> <url>`, verifying the marketplace reference is created
at `$LOLA_HOME/market/<name>.yml`, and confirming the marketplace data is
cached at `$LOLA_HOME/market/cache/<name>.yml`.

**Acceptance Scenarios**:

1. **Given** no marketplaces are registered, **When** user runs
   `lola market add official https://example.com/marketplace.yaml`, **Then**
   Lola creates `$LOLA_HOME/market/official.yml` with reference to source URL
   and enabled: true, downloads marketplace to
   `$LOLA_HOME/market/cache/official.yml`
2. **Given** a marketplace URL with valid YAML structure, **When** user adds
   the marketplace, **Then** marketplace reference file contains source URL and
   enabled status, cached marketplace contains full module catalog
3. **Given** a marketplace name is already registered, **When** user attempts
   to add the same name again, **Then** system prompts for confirmation to
   update or skip
4. **Given** an invalid marketplace URL or malformed YAML, **When** user
   attempts to add it, **Then** system displays clear error message explaining
   the validation failure

---

### User Story 2 - Search Marketplace Modules (Priority: P2)

A user wants to search across all enabled marketplaces to find modules
matching their needs. The user provides search terms and Lola returns matching
modules with their descriptions and sources from cached marketplace data.

**Why this priority**: Search enables discovery, which is the primary value
proposition of a marketplace. This should work immediately after P1.

**Independent Test**: Can be fully tested by adding a marketplace with known
modules, running `lola search <term>`, and verifying matching modules are
displayed with relevant information from enabled marketplace caches only.

**Acceptance Scenarios**:

1. **Given** one or more enabled marketplaces exist with cached data, **When**
   user runs `lola search authentication`, **Then** all modules matching
   "authentication" in name or description are displayed from cache
2. **Given** multiple matches across different marketplaces, **When** search
   results are displayed, **Then** results show module name, description,
   version, and marketplace name
3. **Given** no matches found, **When** user searches for a term, **Then**
   system displays helpful message suggesting to check spelling or browse
   available modules
4. **Given** no marketplaces are registered or all are disabled, **When** user
   attempts to search, **Then** system prompts user to add or enable a
   marketplace first
5. **Given** some marketplaces are disabled, **When** user searches, **Then**
   only enabled marketplace caches are searched

---

### User Story 3 - Install Module from Marketplace (Priority: P1)

A user wants to install a module directly from a marketplace without manually
finding the repository URL. The user specifies the module name and target
assistant, and Lola automatically adds the module and installs it.

**Why this priority**: This is the core value proposition - seamless
installation from marketplace. It combines discovery with installation in one
command, making it equally critical as marketplace registration.

**Independent Test**: Can be fully tested by running
`lola install <module-name> -a <assistant>`, verifying the module is both
added to Lola's registry and installed to the specified assistant.

**Acceptance Scenarios**:

1. **Given** a module exists in an enabled marketplace cache but is not added
   locally, **When** user runs `lola install git-tools -a claude-code`,
   **Then** Lola finds the module in cache, adds it via
   `lola mod add <repo>`, and installs it to claude-code
2. **Given** a module name matches multiple modules across enabled marketplace
   caches, **When** user attempts to install, **Then** Lola prompts user to
   select which marketplace to install from
3. **Given** a module is already added locally, **When** user runs install,
   **Then** Lola skips the add step and proceeds directly to installation
4. **Given** module name is not found in any enabled marketplace cache,
   **When** user attempts to install, **Then** system displays error and
   suggests using `lola search` to find available modules
5. **Given** module only exists in disabled marketplace caches, **When** user
   attempts to install, **Then** system informs user and suggests enabling the
   marketplace

---

### User Story 4 - Update Marketplace Cache (Priority: P2)

A user wants to refresh a marketplace's cached data to get the latest module
list and updates. The user runs the update command and Lola re-downloads the
marketplace definition.

**Why this priority**: Updates are essential for discovering new modules and
getting version updates, making this higher priority than general management.

**Independent Test**: Can be fully tested by adding a marketplace, modifying
the source file, running `lola market update <name>`, and verifying the cache
is refreshed with new data.

**Acceptance Scenarios**:

1. **Given** a marketplace is registered, **When** user runs
   `lola market update official`, **Then** Lola fetches marketplace YAML from
   URL in reference file and updates `$LOLA_HOME/market/cache/official.yml`
2. **Given** marketplace source URL is unavailable, **When** user attempts
   update, **Then** system displays error but preserves existing cache
3. **Given** updated marketplace has schema changes, **When** update completes,
   **Then** system validates new structure and warns if incompatibilities exist
4. **Given** user wants to update all marketplaces, **When** user runs
   `lola market update --all`, **Then** all registered marketplaces are
   refreshed from their source URLs

---

### User Story 5 - Manage Marketplaces (Priority: P3)

A user wants to view, enable, disable, or remove registered marketplaces to
manage their module sources.

**Why this priority**: Management capabilities are important for maintenance
but not critical for initial adoption. Users can start using marketplaces
without these features.

**Independent Test**: Can be fully tested by adding marketplaces, listing them
with `lola market ls`, enabling/disabling, and removing with `lola market rm`.

**Acceptance Scenarios**:

1. **Given** multiple marketplaces are registered, **When** user runs
   `lola market ls`, **Then** all marketplaces are listed with name,
   description, version, module count, and enabled/disabled status from
   reference files
2. **Given** a user wants to temporarily disable a marketplace, **When** user
   runs `lola market disable official`, **Then** marketplace reference file at
   `$LOLA_HOME/market/official.yml` is updated with enabled: false
3. **Given** a disabled marketplace exists, **When** user runs
   `lola market enable official`, **Then** marketplace reference file is
   updated with enabled: true
4. **Given** a marketplace is no longer needed, **When** user runs
   `lola market rm official`, **Then** both reference file
   `$LOLA_HOME/market/official.yml` and cache
   `$LOLA_HOME/market/cache/official.yml` are deleted
5. **Given** modules were installed from a removed marketplace, **When**
   marketplace is removed, **Then** installed modules remain intact and
   functional

---

### Edge Cases

- What happens when a marketplace URL becomes unavailable during search or
  install?
- How does the system handle marketplace YAML files with version conflicts
  between marketplace schema and module versions?
- What happens if a module exists in multiple enabled marketplaces with
  different versions?
- How does the system handle network failures during marketplace registration
  or updates?
- What happens when a marketplace contains modules with duplicate names?
- What happens when installing a module whose repository URL in the cached
  marketplace is no longer valid?
- How does the system handle partial module installations if the install
  process fails midway?
- What happens if marketplace metadata is missing required fields (name,
  description, modules)?
- What happens if a marketplace reference file exists but cache is missing?
- What happens when updating a marketplace that has been removed from its
  original URL?
- How does the system handle permission errors when writing to
  `$LOLA_HOME/market/` or `$LOLA_HOME/market/cache/` directories?
- What happens if cache becomes corrupted or manually modified?
- What happens if user tries to add a marketplace with invalid characters in
  the name?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST provide a name and URL when registering a marketplace
  via `lola market add <name> <url>`
- **FR-002**: System MUST validate marketplace YAML structure before
  registration (required fields: name, description, version, modules list)
- **FR-003**: System MUST create marketplace reference file at
  `$LOLA_HOME/market/<name>.yml` containing source URL and enabled status
- **FR-004**: System MUST download and cache marketplace data at
  `$LOLA_HOME/market/cache/<name>.yml` containing full module catalog
- **FR-005**: Users MUST be able to search across all enabled marketplace
  caches using keywords
- **FR-006**: System MUST match search terms against module name, description,
  and tags in cached marketplace data
- **FR-007**: System MUST display search results with module name, description,
  version, and marketplace source
- **FR-008**: System MUST support installing modules from marketplace without
  requiring pre-registration via `lola mod add`
- **FR-009**: System MUST automatically add module to local registry before
  installation if not already present
- **FR-010**: System MUST handle module name conflicts across enabled
  marketplace caches by prompting user for selection
- **FR-011**: Users MUST be able to list all registered marketplaces with
  metadata and enabled/disabled status from reference files
- **FR-012**: Users MUST be able to update a registered marketplace using
  `lola market update <name>` which fetches from source URL and updates cache
- **FR-013**: Users MUST be able to enable a marketplace using
  `lola market enable <name>` which sets enabled: true in reference file
- **FR-014**: Users MUST be able to disable a marketplace using
  `lola market disable <name>` which sets enabled: false in reference file
- **FR-015**: Users MUST be able to remove a marketplace using
  `lola market rm <name>` which deletes both reference file and cache
- **FR-016**: System MUST preserve installed modules when their source
  marketplace is removed or disabled
- **FR-017**: System MUST provide clear error messages for invalid marketplace
  URLs, malformed YAML, or network failures
- **FR-018**: System MUST only search and install from enabled marketplace
  caches
- **FR-019**: Marketplace YAML MUST support module entries with fields: name,
  description, version, repository/path
- **FR-020**: System MUST handle both HTTP/HTTPS URLs and local file paths for
  marketplace definitions
- **FR-021**: System MUST create `$LOLA_HOME/market/` and
  `$LOLA_HOME/market/cache/` directories if they don't exist
- **FR-022**: System MUST support `lola market update --all` to refresh all
  registered marketplace caches
- **FR-023**: System MUST handle missing cache gracefully by re-downloading
  from source URL when marketplace is accessed
- **FR-024**: System MUST validate marketplace names to ensure they are valid
  filesystem names (no special characters, path separators, etc.)
- **FR-025**: System MUST verify module repository URLs are valid and
  accessible before installation by warning the user if verification fails or
  times out, then proceeding with installation attempt

### Key Entities

- **Marketplace Reference File** (`$LOLA_HOME/market/<name>.yml`): Contains
  reference to marketplace source URL, enabled/disabled status, and basic
  metadata. The name is user-provided during registration.
- **Marketplace Cache** (`$LOLA_HOME/market/cache/<name>.yml`): Downloaded
  copy of marketplace definition containing complete module catalog with name,
  description, version, and repository URLs
- **Marketplace Module Entry**: Represents a module within cached marketplace,
  containing module metadata (name, description, version, repository URL or
  path, optional tags)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can discover and install a module from marketplace in under
  30 seconds (register marketplace, search, install)
- **SC-002**: System successfully handles 100+ modules across multiple
  marketplace caches without performance degradation
- **SC-003**: Search results are returned in under 2 seconds for typical
  marketplace cache sizes (up to 500 modules)
- **SC-004**: 95% of marketplace operations (add, search, install, enable,
  disable, update) complete successfully without user intervention
- **SC-005**: Module installation from marketplace succeeds at the same rate as
  direct `lola mod add` + `lola install` workflow
- **SC-006**: Users can work with marketplace search commands offline using
  cached data after initial marketplace registration
- **SC-007**: Marketplace updates complete in under 5 seconds for typical
  marketplace sizes
- **SC-008**: Cache misses are automatically recovered by re-downloading from
  source URL in under 3 seconds

## Assumptions

- Marketplace YAML files follow a schema similar to yum/dnf RPM repository
  management
- Users have network access when registering or updating marketplaces, but not
  necessarily for search/install operations (uses cache)
- Module repositories referenced in marketplace definitions use the same source
  formats already supported by Lola (git, zip, tar, folder)
- Marketplace URLs are expected to be stable and long-lived (not ephemeral)
- A single module can appear in multiple marketplaces (not enforced uniqueness
  across marketplaces)
- Version conflicts are resolved by user selection, not automatic semantic
  versioning comparison
- Marketplace schema versioning will be handled via version field in
  marketplace YAML for future compatibility
- Disabled marketplaces remain in `$LOLA_HOME/market/` but their caches are
  excluded from search and install operations
- The marketplace reference file tracks the original source URL for each
  marketplace to enable updates
- The marketplace name provided by user is used as the filename, independent of
  any name field in the marketplace YAML itself
- Updates preserve the user-provided marketplace name even if the source file
  changes its internal name field
- Cache invalidation is manual via `lola market update` command (no automatic
  TTL or expiration)
- Directory structure follows existing LOLA_HOME pattern similar to MODULES_DIR
  and INSTALLED_FILE
- Repository URL verification uses a timeout mechanism to avoid blocking on
  slow or unresponsive URLs, displaying warnings but allowing installation to
  proceed
