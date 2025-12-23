"""Tests for the market CLI commands."""

from unittest.mock import patch, mock_open

from lola.cli.market import market


class TestMarketGroup:
    """Tests for the market command group."""

    def test_market_help(self, cli_runner):
        """Show market help."""
        result = cli_runner.invoke(market, ["--help"])
        assert result.exit_code == 0
        assert "Manage lola marketplaces" in result.output

    def test_market_no_args(self, cli_runner):
        """Show help when no subcommand."""
        result = cli_runner.invoke(market, [])
        assert "Manage lola marketplaces" in result.output or "Usage" in result.output


class TestMarketAdd:
    """Tests for market add command."""

    def test_add_help(self, cli_runner):
        """Show add help."""
        result = cli_runner.invoke(market, ["add", "--help"])
        assert result.exit_code == 0
        assert "Add a new marketplace" in result.output

    def test_add_marketplace_success(self, cli_runner, tmp_path):
        """Add marketplace successfully."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        yaml_content = (
            "name: Test Marketplace\n"
            "description: Test catalog\n"
            "version: 1.0.0\n"
            "modules:\n"
            "  - name: test-module\n"
            "    description: A test module\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/module.git\n"
        )
        mock_response = mock_open(read_data=yaml_content.encode())()

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
            patch("urllib.request.urlopen", return_value=mock_response),
        ):
            result = cli_runner.invoke(
                market, ["add", "official", "https://example.com/mkt.yml"]
            )

        assert result.exit_code == 0
        assert "Added marketplace 'official'" in result.output
        assert "1 modules" in result.output

    def test_add_marketplace_duplicate(self, cli_runner, tmp_path):
        """Adding duplicate marketplace shows warning."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        yaml_content = "name: Test\ndescription: Test\nversion: 1.0.0\nmodules: []\n"
        mock_response = mock_open(read_data=yaml_content.encode())()

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
            patch("urllib.request.urlopen", return_value=mock_response),
        ):
            # Add first time
            result = cli_runner.invoke(
                market, ["add", "test", "https://example.com/mkt.yml"]
            )
            assert result.exit_code == 0

            # Add second time - should warn
            result = cli_runner.invoke(
                market, ["add", "test", "https://example.com/mkt.yml"]
            )
            assert result.exit_code == 0
            assert "already exists" in result.output

    def test_add_marketplace_network_error(self, cli_runner, tmp_path):
        """Handle network error when adding marketplace."""
        from urllib.error import URLError

        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
            patch(
                "urllib.request.urlopen",
                side_effect=URLError("Connection failed"),
            ),
        ):
            result = cli_runner.invoke(
                market, ["add", "test", "https://invalid.com/mkt.yml"]
            )

        assert result.exit_code == 0
        assert "Error:" in result.output
