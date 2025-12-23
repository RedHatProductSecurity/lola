# Research: Module Marketplace

**Feature**: 003-marketplace
**Date**: 2025-12-22
**Purpose**: Resolve technical decisions and clarifications for marketplace
implementation

## HTTP Library Selection

**Decision**: Use `urllib` from Python standard library

**Rationale**:
- Already available in Python stdlib - no new dependency
- Sufficient for simple GET requests to download marketplace YAML files
- Lola follows minimal dependency philosophy (only click, rich, pyyaml,
  python-frontmatter)
- No need for advanced features like session management, connection pooling
- Fits with existing source handlers in `parsers.py` which use basic HTTP

**Alternatives Considered**:
- **requests**: Popular, simple API, but adds external dependency
  - Rejected: Unnecessary dependency for simple file downloads
- **httpx**: Modern async-capable library
  - Rejected: Overkill for synchronous YAML downloads, adds dependency
- **aiohttp**: Async HTTP client
  - Rejected: No async requirements in spec, adds complexity

**Implementation Notes**:
- Use `urllib.request.urlopen()` for HTTP/HTTPS downloads
- Use `urllib.parse` for URL validation
- Add timeout parameter (default: 10 seconds) to prevent hanging
- Follow existing pattern from source handlers if they use urllib

## Marketplace YAML Schema

**Decision**: Define schema with required and optional fields

**Required Fields**:
- `name`: string - marketplace display name
- `description`: string - marketplace description
- `version`: string - marketplace schema version (semver)
- `modules`: list - array of module entries

**Module Entry Fields** (within modules list):
- `name`: string - module name (required)
- `description`: string - module description (required)
- `version`: string - module version (required)
- `repository`: string - git/zip/tar/folder URL or path (required)
- `tags`: list[string] - searchable tags (optional)

**Example**:
```yaml
name: "Official Lola Marketplace"
description: "Curated modules from the Lola team"
version: "1.0.0"
modules:
  - name: "git-tools"
    description: "Git workflow automation tools"
    version: "1.2.0"
    repository: "https://github.com/example/git-tools.git"
    tags: ["git", "automation", "workflow"]
  - name: "code-review"
    description: "Code review assistance"
    version: "2.0.1"
    repository: "https://github.com/example/code-review.git"
    tags: ["review", "quality"]
```

**Rationale**:
- Mirrors yum/dnf repodata structure concept
- Simple YAML format matches existing Lola patterns
- Tags enable flexible search beyond name/description
- Version field allows future schema evolution
- Repository field reuses existing source handler logic

## Marketplace Reference File Structure

**Decision**: Store minimal metadata in reference files

**Reference File** (`$LOLA_HOME/market/<name>.yml`):
```yaml
name: "official"
url: "https://example.com/marketplace.yaml"
enabled: true
```

**Rationale**:
- Lightweight reference separate from cached data
- Enables quick enable/disable without re-downloading
- URL stored for update operations
- Name is user-provided CLI argument (key for file naming)

## Cache Management Strategy

**Decision**: Simple file-based cache with manual invalidation

**Strategy**:
- Download marketplace YAML to `$LOLA_HOME/market/cache/<name>.yml` on add
- Search reads from cache files (no network required)
- Update command re-downloads from URL in reference file
- No automatic expiration or TTL
- Cache miss triggers re-download from reference URL

**Rationale**:
- Offline capability after initial registration (per requirements)
- Simple implementation - no cache database needed
- Manual control aligns with dnf/yum model (explicit `update` command)
- Predictable behavior for users

## Search Implementation

**Decision**: In-memory search across cached YAML files

**Approach**:
1. Load all enabled marketplace cache files
2. Parse YAML and extract modules
3. Filter by search term (case-insensitive substring match)
4. Match against: name, description, tags
5. Return results with marketplace source attribution

**Rationale**:
- Performance requirement: < 2 seconds for 500 modules
- Loading ~5-10 YAML files (typical marketplaces) is fast
- No indexing needed for this scale
- Simple implementation, easy to test

**Performance Notes**:
- YAML parsing is bottleneck (~1-5ms per file)
- For 10 marketplaces × 50 modules each = 500 modules
- Expected search time: < 100ms (well under 2s requirement)

## Integration with Existing Commands

**Decision**: Extend `lola install` to check marketplaces before failing

**Flow**:
1. User runs: `lola install <module-name> -a <assistant>`
2. Check if module already added to `$LOLA_HOME/modules/`
3. If not found, search enabled marketplace caches
4. If found in marketplace, run `lola mod add <repo>` automatically
5. Then proceed with normal install

**Rationale**:
- Seamless user experience (single command)
- Reuses existing `lola mod add` logic (no duplication)
- Maintains separation of concerns (marketplace = discovery, mod = storage)
- Backwards compatible (existing workflow still works)

## Error Handling Strategy

**Decision**: Warn and continue for network/validation errors

**Approach**:
- Invalid marketplace YAML: validate on add, show errors, abort add
- Network timeout during add: show error, abort add
- Network timeout during update: show error, keep existing cache
- Missing cache on search: attempt re-download from reference URL
- Repository URL validation: warn user if unreachable, proceed with install

**Timeout Values**:
- HTTP download: 10 seconds default
- Repository URL check: 5 seconds (non-blocking)

**Rationale**:
- Fail-fast on add/update (user-initiated, expects success)
- Graceful degradation on search (use cached data)
- Repository validation is advisory (per spec clarification)

## Testing Strategy

**Unit Tests** (`tests/test_market_manager.py`):
- Marketplace.add() with valid/invalid YAML
- Marketplace.remove() with existing/non-existent marketplace
- Marketplace.enable() / disable()
- Marketplace.update() with network mocks

**Unit Tests** (`tests/test_market_cache.py`):
- Cache miss recovery
- Cache loading and parsing

**Unit Tests** (`tests/test_market_search.py`):
- Search with single/multiple marketplaces
- Search with no results
- Search with disabled marketplaces

**Integration Tests** (`tests/test_cli_market.py`):
- Full command workflows (add → search → install)
- Error scenarios (network failures, invalid URLs)

**CLI Tests**:
- Click CliRunner for command testing
- Mock filesystem and HTTP calls
- Follow existing patterns from `test_cli_mod.py`

**Rationale**:
- Comprehensive coverage per constitution requirements
- Follows existing test patterns in codebase
- Separates unit (business logic) from integration (CLI + I/O)
