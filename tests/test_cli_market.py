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


class TestMarketLs:
    """Tests for market ls command."""

    def test_ls_help(self, cli_runner):
        """Show ls help."""
        result = cli_runner.invoke(market, ["ls", "--help"])
        assert result.exit_code == 0
        assert "List all registered marketplaces" in result.output

    def test_ls_empty(self, cli_runner, tmp_path):
        """List when no marketplaces registered."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["ls"])

        assert result.exit_code == 0
        assert "No marketplaces registered" in result.output

    def test_ls_with_marketplaces(self, cli_runner, marketplace_with_modules):
        """List registered marketplaces."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["ls"])

        assert result.exit_code == 0
        assert "official" in result.output
        assert "enabled" in result.output


class TestMarketSet:
    """Tests for market set command."""

    def test_set_help(self, cli_runner):
        """Show set help."""
        result = cli_runner.invoke(market, ["set", "--help"])
        assert result.exit_code == 0
        assert "Enable or disable a marketplace" in result.output

    def test_set_no_action(self, cli_runner, tmp_path):
        """Fail when no action specified."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["set", "test"])

        assert result.exit_code == 1
        assert "Must specify either --enable or --disable" in result.output

    def test_set_enable(self, cli_runner, marketplace_disabled):
        """Enable a marketplace."""
        market_dir = marketplace_disabled["market_dir"]
        cache_dir = marketplace_disabled["cache_dir"]

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["set", "disabled-market", "--enable"])

        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_set_disable(self, cli_runner, marketplace_with_modules):
        """Disable a marketplace."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["set", "official", "--disable"])

        assert result.exit_code == 0
        assert "disabled" in result.output


class TestMarketRm:
    """Tests for market rm command."""

    def test_rm_help(self, cli_runner):
        """Show rm help."""
        result = cli_runner.invoke(market, ["rm", "--help"])
        assert result.exit_code == 0
        assert "Remove a marketplace" in result.output

    def test_rm_not_found(self, cli_runner, tmp_path):
        """Fail when marketplace not found."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["rm", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.output

    def test_rm_success(self, cli_runner, marketplace_with_modules):
        """Remove a marketplace successfully."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["rm", "official"])

        assert result.exit_code == 0
        assert "Removed marketplace" in result.output


class TestMarketUpdate:
    """Tests for market update command."""

    def test_update_help(self, cli_runner):
        """Show update help."""
        result = cli_runner.invoke(market, ["update", "--help"])
        assert result.exit_code == 0
        assert "Update marketplace cache" in result.output

    def test_update_name_and_all_conflict(self, cli_runner, tmp_path):
        """Fail when both name and --all specified."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["update", "test", "--all"])

        assert result.exit_code == 1
        assert "Cannot specify both NAME and --all" in result.output

    def test_update_empty(self, cli_runner, tmp_path):
        """Update when no marketplaces registered."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        with (
            patch("lola.cli.market.MARKET_DIR", market_dir),
            patch("lola.cli.market.CACHE_DIR", cache_dir),
        ):
            result = cli_runner.invoke(market, ["update"])

        assert result.exit_code == 0
        assert "No marketplaces registered" in result.output
