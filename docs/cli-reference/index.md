# CLI Reference

Complete command reference for the Lola CLI. Use `lola --help` or `lola <command> --help` for detailed usage.

## Module Management (`lola mod`)

| Command                                              | Description                                    |
| ---------------------------------------------------- | ---------------------------------------------- |
| `lola mod add <source>`                              | Add a module from git, folder, zip, or tar     |
| `lola mod add <source> --ref <ref>`                  | Add from a specific git branch, tag, or SHA    |
| `lola mod ls`                                        | List registered modules                        |
| `lola mod info <name>`                               | Show module details                            |
| `lola mod init [name]`                               | Initialize a new module                        |
| `lola mod update [name]`                             | Update module(s) from source                   |
| `lola mod rm <name>`                                 | Remove a module                                |

## Marketplace Management (`lola market`)

| Command                                      | Description                                   |
| -------------------------------------------- | --------------------------------------------- |
| `lola market add <name> <url>`               | Register a marketplace                        |
| `lola market ls`                             | List registered marketplaces                  |
| `lola market update [name]`                  | Update marketplace cache                      |
| `lola market set --enable <name>`            | Enable a marketplace                          |
| `lola market set --disable <name>`           | Disable a marketplace                         |
| `lola market rm <name>`                      | Remove a marketplace                          |

## Search

| Command                          | Description                                                       |
| -------------------------------- | ----------------------------------------------------------------- |
| `lola search <query>`            | Search the local registry and enabled marketplaces                |
| `lola search <query> --mod`      | Search only the local module registry                             |
| `lola search <query> --market`   | Search only enabled marketplaces                                  |
| `lola mod search <query>`        | Deprecated alias for `lola search <query> --mod`                  |

## Installation

| Command                                             | Description                                   |
| --------------------------------------------------- | --------------------------------------------- |
| `lola install <module>`                             | Install to all detected assistants             |
| `lola install <module> -a <assistant>`              | Install to specific assistant                 |
| `lola install <module>@<ref>`                       | Install at a specific git ref                 |
| `lola install @<marketplace>/<module>`              | Install from a specific marketplace           |
| `lola install @<marketplace>/<module>@<ref>`        | Install from a marketplace at a specific ref  |
| `lola install <module> --append-context <path>`     | Append context reference                      |
| `lola install <module> --plugin`                    | Install as a self-contained plugin bundle (uses existing `plugin.json` or generates one) |
| `lola uninstall <module>`                           | Uninstall module                              |
| `lola uninstall <module> --plugin`                  | Uninstall a plugin bundle                     |
| `lola list`                                         | List all installations (shows version and ref when set) |
| `lola update`                                       | Regenerate assistant files                    |
| `lola sync`                                         | Install modules from `.lola-req`              |
