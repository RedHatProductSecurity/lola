"""Tests for the MarketplaceRegistry manager."""

from unittest.mock import patch, mock_open

from lola.models import Marketplace
from lola.market.manager import MarketplaceRegistry


class TestMarketplaceRegistryAdd:
    """Tests for MarketplaceRegistry.add()."""

    def test_registry_add_success(self, tmp_path):
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

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            registry.add("official", "https://example.com/market.yml")

            # Verify reference file created
            ref_file = market_dir / "official.yml"
            assert ref_file.exists()

            # Verify cache file created
            cache_file = cache_dir / "official.yml"
            assert cache_file.exists()

            # Verify reference content
            marketplace = Marketplace.from_reference(ref_file)
            assert marketplace.name == "official"
            assert marketplace.url == "https://example.com/market.yml"
            assert marketplace.enabled is True

            # Verify cache content
            cached = Marketplace.from_cache(cache_file)
            assert cached.description == "Test catalog"
            assert cached.version == "1.0.0"
            assert len(cached.modules) == 1

    def test_registry_add_duplicate(self, tmp_path, capsys):
        """Adding duplicate marketplace shows warning."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        yaml_content = "name: Test\ndescription: Test\nversion: 1.0.0\nmodules: []\n"
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)

            # Add first time
            registry.add("test", "https://example.com/market.yml")

            # Add second time - should warn
            registry.add("test", "https://example.com/market.yml")

            # Verify warning message was printed
            captured = capsys.readouterr()
            assert "already exists" in captured.out

    def test_registry_add_invalid_yaml(self, tmp_path, capsys):
        """Adding marketplace with invalid YAML shows errors."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        # Has modules but missing version (should fail validation)
        yaml_content = (
            "name: Test\nmodules:\n  - name: test-module\n    description: Test\n"
        )
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            registry.add("invalid", "https://example.com/bad.yml")

            # Verify validation failure message was printed
            captured = capsys.readouterr()
            assert "Validation failed" in captured.out

    def test_registry_add_network_error(self, tmp_path, capsys):
        """Handle network error when adding marketplace."""
        from urllib.error import URLError

        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        with patch(
            "urllib.request.urlopen",
            side_effect=URLError("Connection failed"),
        ):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            registry.add("test", "https://invalid.com/market.yml")

            # Verify error message was printed
            captured = capsys.readouterr()
            assert "Error:" in captured.out
