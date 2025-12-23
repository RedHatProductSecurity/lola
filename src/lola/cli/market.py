"""
Marketplace management CLI commands.

Commands for adding, managing, and searching marketplaces.
"""

import click

from lola.config import MARKET_DIR, CACHE_DIR
from lola.market.manager import MarketplaceRegistry


@click.group(name="market")
def market():
    """
    Manage lola marketplaces.

    Add, update, and manage marketplace catalogs.
    """
    pass


@market.command(name="add")
@click.argument("name")
@click.argument("url")
def market_add(name: str, url: str):
    """
    Add a new marketplace.

    NAME: Marketplace name (e.g., 'official')
    URL: Marketplace catalog URL
    """
    registry = MarketplaceRegistry(MARKET_DIR, CACHE_DIR)
    registry.add(name, url)


@market.command(name="ls")
def market_ls():
    """List all registered marketplaces."""
    registry = MarketplaceRegistry(MARKET_DIR, CACHE_DIR)
    registry.list()


@market.command(name="set")
@click.argument("name")
@click.option("--enable", "action", flag_value="enable", help="Enable marketplace")
@click.option("--disable", "action", flag_value="disable", help="Disable marketplace")
def market_set(name: str, action: str):
    """
    Enable or disable a marketplace.

    NAME: Marketplace name
    """
    if not action:
        click.echo("Error: Must specify either --enable or --disable")
        raise SystemExit(1)

    registry = MarketplaceRegistry(MARKET_DIR, CACHE_DIR)

    if action == "enable":
        registry.enable(name)
    elif action == "disable":
        registry.disable(name)


@market.command(name="rm")
@click.argument("name")
def market_rm(name: str):
    """
    Remove a marketplace.

    NAME: Marketplace name
    """
    registry = MarketplaceRegistry(MARKET_DIR, CACHE_DIR)
    registry.remove(name)
