"""
market.search:
    Module search functionality across marketplaces
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table

from lola.models import Marketplace


def get_enabled_marketplaces(market_dir: Path, cache_dir: Path):
    """
    Get all enabled marketplaces with their cached data.

    Args:
        market_dir: Directory containing marketplace reference files
        cache_dir: Directory containing marketplace cache files

    Returns:
        List of tuples (Marketplace, marketplace_name)
    """
    marketplaces = []

    for ref_file in market_dir.glob("*.yml"):
        marketplace_ref = Marketplace.from_reference(ref_file)

        if not marketplace_ref.enabled:
            continue

        cache_file = cache_dir / ref_file.name
        if not cache_file.exists():
            continue

        marketplace = Marketplace.from_cache(cache_file)
        marketplaces.append((marketplace, marketplace_ref.name))

    return marketplaces


def match_module(module: dict, query_lower: str) -> bool:
    """
    Check if module matches search query.

    Args:
        module: Module dictionary with name, description, tags
        query_lower: Lowercase search query

    Returns:
        True if module matches query
    """
    name = module.get("name", "").lower()
    description = module.get("description", "").lower()
    tags = module.get("tags", [])

    return (
        query_lower in name
        or query_lower in description
        or any(query_lower in tag.lower() for tag in tags)
    )


def format_search_result(
    module: dict, marketplace_name: str
) -> dict:
    """
    Format module data for search results display.

    Args:
        module: Module dictionary
        marketplace_name: Name of the marketplace

    Returns:
        Formatted result dictionary
    """
    description = module.get("description", "")
    if len(description) > 60:
        description = description[:60] + "..."

    return {
        "name": module.get("name", ""),
        "description": description,
        "version": module.get("version", ""),
        "marketplace": marketplace_name,
    }


def search_market(query: str, market_dir: Path, cache_dir: Path) -> list[dict]:
    """
    Search for modules across all enabled marketplaces.

    Args:
        query: Search term to match
        market_dir: Directory containing marketplace references
        cache_dir: Directory containing marketplace caches

    Returns:
        List of formatted search results
    """
    marketplaces = get_enabled_marketplaces(market_dir, cache_dir)
    results = []
    query_lower = query.lower()

    for marketplace, name in marketplaces:
        for module in marketplace.modules:
            if match_module(module, query_lower):
                result = format_search_result(module, name)
                results.append(result)

    return results


def display_market(results: list[dict], query: str, console: Console) -> None:
    """
    Display search results in a table.

    Args:
        results: List of formatted search results
        query: Original search query
        console: Rich console for output
    """
    if not results:
        console.print(
            f"[yellow]No modules found matching '{query}'[/yellow]"
        )
        console.print(
            "[dim]Tip: Check spelling or try a different search "
            "term[/dim]"
        )
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Module")
    table.add_column("Version")
    table.add_column("Marketplace")
    table.add_column("Description")

    for result in results:
        table.add_row(
            result["name"],
            result["version"],
            result["marketplace"],
            result["description"],
        )

    count_text = "s" if len(results) != 1 else ""
    console.print(
        f"\n[bold]Found {len(results)} module{count_text}[/bold]\n"
    )
    console.print(table)
