"""Sync command for installing modules from .lola-req."""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table

from lola.config import MODULES_DIR, MARKET_DIR, CACHE_DIR
from lola.sync import load_lolareq, ModuleSpec
from lola.cli.mod import load_registered_module, save_source_info
from lola.targets import get_registry, TARGETS, default_assistants
from lola.targets.install import install_to_assistant
from lola.market.manager import parse_market_ref, MarketplaceRegistry
from lola.parsers import detect_source_type, fetch_module_as_name
from lola.models import Marketplace

console = Console()


def _fetch_from_marketplace_quiet(
    marketplace_name: str, module_name: str
) -> tuple[Path, dict]:
    """
    Fetch module from marketplace (quieter version for sync).

    Returns:
        Tuple of (module_path, module_metadata)

    Raises:
        Exception on error
    """
    ref_file = MARKET_DIR / f"{marketplace_name}.yml"

    if not ref_file.exists():
        raise ValueError(f"Marketplace '{marketplace_name}' not found")

    marketplace_ref = Marketplace.from_reference(ref_file)
    if not marketplace_ref.enabled:
        raise ValueError(f"Marketplace '{marketplace_name}' is disabled")

    cache_file = CACHE_DIR / f"{marketplace_name}.yml"
    if not cache_file.exists():
        raise ValueError(f"Marketplace '{marketplace_name}' cache not found")

    marketplace = Marketplace.from_cache(cache_file)

    module_dict = next(
        (m for m in marketplace.modules if m.get("name") == module_name), None
    )

    if not module_dict:
        raise ValueError(
            f"Module '{module_name}' not found in marketplace '{marketplace_name}'"
        )

    repository: str | None = module_dict.get("repository")
    if not repository or not isinstance(repository, str):
        raise ValueError(f"Module '{module_name}' has no repository URL")

    content_dirname = module_dict.get("path")

    source_type = detect_source_type(repository)
    module_path = fetch_module_as_name(
        repository, MODULES_DIR, module_name, content_dirname
    )
    save_source_info(module_path, repository, source_type, content_dirname)

    return module_path, module_dict


@click.command(name="sync")
@click.argument("project_path", type=click.Path(exists=True), default="./")
@click.option(
    "--file",
    "config_file",
    type=click.Path(),
    default=".lola-req",
    help="Path to config file",
)
@click.option("--dry-run", is_flag=True, help="Show what would be installed")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
@click.option(
    "-a",
    "--assistant",
    type=click.Choice(list(TARGETS.keys())),
    multiple=True,
    help="AI assistant(s) to sync for (repeatable, default: all detected assistants)",
)
def sync_cmd(
    project_path: str,
    config_file: str,
    dry_run: bool,
    verbose: bool,
    assistant: tuple[str, ...],
):
    """Sync modules from configuration file."""
    project = Path(project_path).resolve()

    # Resolve config file path
    config_path = Path(config_file)
    if not config_path.is_absolute():
        config_path = project / config_path

    if not config_path.exists():
        console.print(f"[yellow]Config file not found: {config_path}[/yellow]")
        console.print("[dim]Create a .lola-req with one module per line[/dim]")
        console.print(
            "[dim]Examples:\n"
            "  my-skill\n"
            "  python-tools>=1.0.0\n"
            "  https://github.com/user/repo.git#subdirectory=plugins/dev\n"
            "  https://github.com/user/repo.git#assistant=claude-code,cursor[/dim]"
        )
        raise click.Abort()

    # Load specs
    try:
        specs = load_lolareq(config_path)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    if not specs:
        console.print("[yellow]No modules specified in config file[/yellow]")
        return

    console.print(f"[bold]Syncing from {config_path.name}[/bold]\n")

    # Track results
    installed = []
    skipped = []
    failed = []

    # Process each spec
    for spec in specs:
        try:
            result = sync_module_spec(spec, project, dry_run, verbose, assistant)
            if result == "installed":
                installed.append(spec.raw_line)
            elif result == "skipped":
                skipped.append(spec.raw_line)
        except Exception as e:
            failed.append((spec.raw_line, str(e)))
            if verbose:
                console.print(f"[red]✗ {spec.module_ref}: {e}[/red]")

    # Print summary
    console.print()
    print_summary(console, installed, skipped, failed)

    if failed and not dry_run:
        raise click.Abort()


def sync_module_spec(
    spec: ModuleSpec,
    project_path: Path,
    dry_run: bool,
    verbose: bool,
    cli_assistants: tuple[str, ...] = (),
) -> str:
    """
    Sync a single module spec.

    Returns: "installed", "skipped", or raises exception on failure
    """
    # Resolve module name and fetch if needed
    module_name, module_dict = resolve_and_fetch_module(spec, verbose)

    # Load the module
    module_path = MODULES_DIR / module_name
    module = load_registered_module(module_path)
    if not module:
        raise ValueError(f"Failed to load module {module_name}")

    # Check if already installed with matching version
    registry = get_registry()
    installations = registry.find(module_name)

    # Filter installations for this project
    project_installations = [
        inst
        for inst in installations
        if inst.scope == "project" and inst.project_path == str(project_path)
    ]

    # Determine target assistants
    # Priority: CLI flag > URL fragment > all assistants
    if cli_assistants:
        target_assistants = list(dict.fromkeys(cli_assistants))
    elif spec.assistants:
        # Deduplicate while preserving order
        unique_assistants = list(dict.fromkeys(spec.assistants))
        # Validate all assistants from fragment
        for asst in unique_assistants:
            if asst not in TARGETS:
                raise ValueError(f"Unknown assistant in fragment: {asst}")
        target_assistants = unique_assistants
    else:
        target_assistants = default_assistants()

    # Check if already installed
    already_installed_assistants = {inst.assistant for inst in project_installations}
    needs_assistants = []

    for asst in target_assistants:
        if asst in already_installed_assistants:
            # Check version constraints
            inst = next(i for i in project_installations if i.assistant == asst)
            if spec.version_spec and inst.version:
                if not spec.matches_version(inst.version):
                    # Version mismatch - need to reinstall
                    needs_assistants.append(asst)
                    if verbose:
                        console.print(
                            f"[dim]Version mismatch for {module_name} ({asst}): "
                            f"have {inst.version}, need {spec.version_spec}[/dim]"
                        )
            # else: already installed and version OK
        else:
            # Not installed for this assistant
            needs_assistants.append(asst)

    if not needs_assistants:
        if verbose:
            console.print(f"[dim]⊘ {spec.module_ref} (already installed)[/dim]")
        return "skipped"

    if dry_run:
        assistants_str = ", ".join(needs_assistants)
        console.print(f"[blue]Would install {module_name} ({assistants_str})[/blue]")
        return "skipped"

    # Install to each assistant
    local_modules = project_path / ".lola" / "modules"

    # Extract version from module_dict if available
    version = module_dict.get("version") if module_dict else None

    # Resolve hooks from module_dict and module
    marketplace_hooks = module_dict.get("hooks", {}) if module_dict else {}
    pre_install = marketplace_hooks.get("pre-install") or module.pre_install_hook
    post_install = marketplace_hooks.get("post-install") or module.post_install_hook

    for asst in needs_assistants:
        try:
            install_to_assistant(
                module,
                asst,
                "project",
                str(project_path),
                local_modules,
                registry,
                verbose=verbose,
                force=False,
                pre_install_script=pre_install,
                post_install_script=post_install,
            )

            # Update the installation record with version
            if version:
                installations = registry.find(module_name)
                for inst in installations:
                    if inst.assistant == asst and inst.project_path == str(
                        project_path
                    ):
                        inst.version = version
                        registry.add(inst)  # This will update the existing record

        except Exception as e:
            raise ValueError(f"Failed to install to {asst}: {e}") from e

    assistants_str = ", ".join(needs_assistants)
    console.print(f"[green]✓ {module_name} ({assistants_str})[/green]")
    return "installed"


def resolve_and_fetch_module(spec: ModuleSpec, verbose: bool) -> tuple[str, dict]:
    """
    Resolve module spec and fetch if needed.

    Returns:
        Tuple of (module_name, module_dict) where module_dict may be empty
        if not from marketplace

    Raises:
        Exception if module cannot be resolved or fetched
    """
    # Check if it's a marketplace reference (@marketplace/module)
    marketplace_ref = parse_market_ref(spec.module_ref)
    if marketplace_ref:
        marketplace_name, module_name = marketplace_ref
        module_path = MODULES_DIR / module_name

        # Fetch from marketplace if not in registry
        if not module_path.exists():
            if verbose:
                console.print(
                    f"[dim]Fetching {module_name} from {marketplace_name}...[/dim]"
                )
            _, module_dict = _fetch_from_marketplace_quiet(
                marketplace_name, module_name
            )
            return module_name, module_dict
        else:
            # Already in registry, try to get module dict from cache
            cache_file = CACHE_DIR / f"{marketplace_name}.yml"
            if cache_file.exists():
                marketplace = Marketplace.from_cache(cache_file)
                module_dict = next(
                    (m for m in marketplace.modules if m.get("name") == module_name),
                    {},
                )
                return module_name, module_dict
            return module_name, {}

    # Check if it's a URL (including git+https://, git+http://, git+ssh://)
    module_url = spec.module_ref
    git_ref = None

    # Handle git+ prefix (pip-style)
    if module_url.startswith("git+"):
        module_url = module_url[4:]  # Strip "git+" prefix

    if module_url.startswith(("http://", "https://", "git@", "ssh://", "file://")):
        # Extract @ref from URL (branch, tag, or commit)
        # Only split on @ if it comes after .git or at the very end
        if "@" in module_url and (".git@" in module_url or module_url.count("@") > 1):
            # For URLs like git@github.com:user/repo.git@branch, split on last @
            # For URLs like ssh://git@github.com/user/repo.git@branch, split on @ after .git
            if ".git@" in module_url:
                module_url, git_ref = module_url.rsplit("@", 1)
            elif "/" in module_url.split("@")[-1]:
                # The part after @ contains /, so it's part of the URL path, not a ref
                pass
            else:
                # The part after last @ has no /, likely a ref
                module_url, git_ref = module_url.rsplit("@", 1)

        # Extract module name from URL (last segment, remove .git)
        url_path = module_url.rstrip("/")
        if url_path.endswith(".git"):
            url_path = url_path[:-4]
        module_name = Path(url_path).stem

        # Combine repo stem + subdirectory leaf so entries from the same
        # repo get distinct names without colliding across repos.
        if spec.subdirectory:
            subdir_name = Path(spec.subdirectory).name
            if subdir_name:
                module_name = f"{module_name}-{subdir_name}"

        module_path = MODULES_DIR / module_name

        # Add repository to registry if not already present
        if not module_path.exists():
            ref_msg = f"@{git_ref}" if git_ref else ""
            if verbose:
                console.print(
                    f"[dim]Adding {module_name} to registry from {module_url}{ref_msg}...[/dim]"
                )
            else:
                console.print(f"[dim]Adding {module_name} from URL{ref_msg}...[/dim]")

            source_type = detect_source_type(module_url)
            module_path = fetch_module_as_name(
                module_url,
                MODULES_DIR,
                module_name,
                module_content_dirname=spec.subdirectory,
                ref=git_ref,
            )
            save_source_info(
                module_path,
                module_url,
                source_type,
                content_dirname=spec.subdirectory,
                ref=git_ref,
            )

        return module_name, {}

    # Otherwise it's a module name - check if exists in registry
    module_name = spec.module_name_only
    module_path = MODULES_DIR / module_name

    if not module_path.exists():
        # Search marketplaces before raising error
        mp_registry = MarketplaceRegistry(MARKET_DIR, CACHE_DIR)
        matches = mp_registry.search_module_all(module_name)

        if matches:
            selected_marketplace = mp_registry.select_marketplace(module_name, matches)
            if selected_marketplace is None:
                raise ValueError(f"Module '{module_name}' installation cancelled")

            if verbose:
                console.print(
                    f"[dim]Fetching {module_name} from {selected_marketplace}...[/dim]"
                )
            _, module_dict = _fetch_from_marketplace_quiet(
                selected_marketplace, module_name
            )
            return module_name, module_dict

        # No matches in marketplaces either
        raise ValueError(
            f"Module '{module_name}' not found in registry or marketplaces. "
            f"Use 'lola mod add' or specify a marketplace/URL."
        )

    return module_name, {}


def print_summary(
    console: Console,
    installed: list[str],
    skipped: list[str],
    failed: list[tuple[str, str]],
):
    """Print sync summary."""
    table = Table(show_header=False, box=None)

    if installed:
        table.add_row("[green]✓ Installed:", str(len(installed)))
    if skipped:
        table.add_row("[dim]⊘ Skipped:", str(len(skipped)))
    if failed:
        table.add_row("[red]✗ Failed:", str(len(failed)))

    console.print(table)

    if failed:
        console.print("\n[bold red]Failures:[/bold red]")
        for module, error in failed:
            console.print(f"  [red]• {module}: {error}[/red]")
