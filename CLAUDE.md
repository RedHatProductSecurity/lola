@AGENTS.md

## Active Technologies
- Python 3.13 + click, rich, pyyaml, python-frontmatter (001-mod-init-template)
- Local filesystem (YAML frontmatter in .md files, JSON for mcps.json) (001-mod-init-template)
- Python 3.13 (project uses modern type hints like `list[str]`) + click (CLI), rich (console output), pathlib (file operations) (002-target-uninstall)
- Local filesystem (markdown files, JSON config files) (002-target-uninstall)
- Python 3.13 + click (CLI), rich (console output), pyyaml (003-marketplace)
- YAML files at `$LOLA_HOME/market/*.yml` (references) and `$LOLA_HOME/market/cache/*.yml` (catalogs) (003-marketplace)
- HTTP/HTTPS downloads via urllib for fetching marketplaces and modules (003-marketplace)

## Recent Changes
- 001-mod-init-template: Added Python 3.13 + click, rich, pyyaml, python-frontmatter
- 003-marketplace: Added complete marketplace feature
  - `lola market add/ls/update/set/rm` commands for marketplace management
  - `lola mod search` for cross-marketplace module discovery
  - Auto-install from marketplaces via `lola install <module>`
  - Multi-marketplace conflict resolution with user prompts
  - Cache recovery on missing cache files
  - MarketplaceRegistry class with search_module_all() and select_marketplace() methods
