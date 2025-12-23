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
