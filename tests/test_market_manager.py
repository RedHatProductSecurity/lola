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


class TestMarketplaceRegistrySearchModule:
    """Tests for MarketplaceRegistry.search_module()."""

    def test_search_module_success(self, marketplace_with_modules):
        """Search module in marketplace successfully."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.search_module("git-tools")

        assert result is not None
        module, marketplace_name = result
        assert module["name"] == "git-tools"
        assert module["repository"] == "https://github.com/test/git-tools.git"
        assert marketplace_name == "official"

    def test_search_module_not_found(self, marketplace_with_modules):
        """Module not found in any marketplace."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.search_module("nonexistent-module")

        assert result is None

    def test_search_module_disabled_marketplace(self, marketplace_disabled):
        """Skip disabled marketplaces when searching."""
        market_dir = marketplace_disabled["market_dir"]
        cache_dir = marketplace_disabled["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.search_module("test-module")

        # Should not find module in disabled marketplace
        assert result is None


class TestMarketplaceRegistryList:
    """Tests for MarketplaceRegistry.list()."""

    def test_list_empty(self, tmp_path, capsys):
        """List when no marketplaces registered."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.list()

        captured = capsys.readouterr()
        assert "No marketplaces registered" in captured.out

    def test_list_with_marketplaces(self, marketplace_with_modules, capsys):
        """List registered marketplaces."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.list()

        captured = capsys.readouterr()
        assert "official" in captured.out
        assert "2" in captured.out  # Module count
        assert "enabled" in captured.out


class TestMarketplaceRegistryEnableDisable:
    """Tests for MarketplaceRegistry enable/disable."""

    def test_enable_marketplace(self, marketplace_disabled, capsys):
        """Enable a disabled marketplace."""
        market_dir = marketplace_disabled["market_dir"]
        cache_dir = marketplace_disabled["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.enable("disabled-market")

        captured = capsys.readouterr()
        assert "enabled" in captured.out

        # Verify enabled status persisted
        from lola.models import Marketplace

        ref_file = market_dir / "disabled-market.yml"
        marketplace = Marketplace.from_reference(ref_file)
        assert marketplace.enabled is True

    def test_disable_marketplace(self, marketplace_with_modules, capsys):
        """Disable an enabled marketplace."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.disable("official")

        captured = capsys.readouterr()
        assert "disabled" in captured.out

        # Verify disabled status persisted
        from lola.models import Marketplace

        ref_file = market_dir / "official.yml"
        marketplace = Marketplace.from_reference(ref_file)
        assert marketplace.enabled is False

    def test_enable_not_found(self, tmp_path, capsys):
        """Enable non-existent marketplace shows error."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.enable("nonexistent")

        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestMarketplaceRegistryRemove:
    """Tests for MarketplaceRegistry.remove()."""

    def test_remove_marketplace(self, marketplace_with_modules, capsys):
        """Remove a marketplace successfully."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.remove("official")

        captured = capsys.readouterr()
        assert "Removed marketplace" in captured.out

        # Verify files removed
        ref_file = market_dir / "official.yml"
        cache_file = cache_dir / "official.yml"
        assert not ref_file.exists()
        assert not cache_file.exists()

    def test_remove_not_found(self, tmp_path, capsys):
        """Remove non-existent marketplace shows error."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.remove("nonexistent")

        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestMarketplaceRegistryUpdate:
    """Tests for MarketplaceRegistry update methods."""

    def test_update_one_success(self, marketplace_with_modules, capsys):
        """Update a single marketplace and verify cache changes."""
        from lola.models import Marketplace

        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        # Verify initial cache state
        cache_file = cache_dir / "official.yml"
        initial_marketplace = Marketplace.from_cache(cache_file)
        assert len(initial_marketplace.modules) == 2
        assert initial_marketplace.modules[0]["name"] == "git-tools"

        # Updated YAML with different modules
        yaml_content = (
            "name: Updated Marketplace\n"
            "description: Updated catalog\n"
            "version: 2.0.0\n"
            "modules:\n"
            "  - name: new-module\n"
            "    description: A new module\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/new-module.git\n"
            "  - name: another-module\n"
            "    description: Another new module\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/another-module.git\n"
            "  - name: third-module\n"
            "    description: Third module\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/third-module.git\n"
        )
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            result = registry.update_one("official")

            assert result is True

            captured = capsys.readouterr()
            assert "Updated 'official' with 3 modules" in captured.out

            # Verify cache was updated with new content
            updated_marketplace = Marketplace.from_cache(cache_file)
            assert len(updated_marketplace.modules) == 3
            assert updated_marketplace.modules[0]["name"] == "new-module"
            assert (
                updated_marketplace.modules[0]["repository"]
                == "https://github.com/test/new-module.git"
            )
            assert updated_marketplace.modules[1]["name"] == "another-module"
            assert updated_marketplace.modules[2]["name"] == "third-module"

    def test_update_one_not_found(self, tmp_path, capsys):
        """Update non-existent marketplace returns False."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.update_one("nonexistent")

        assert result is False
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_update_one_validation_failure(self, marketplace_with_modules, capsys):
        """Update with invalid data returns False."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        # Missing version field (validation will fail)
        yaml_content = "name: Test\nmodules:\n  - name: test\n    description: Test\n"
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            result = registry.update_one("official")

            assert result is False
            captured = capsys.readouterr()
            assert "Validation failed" in captured.out

    def test_update_all(self, marketplace_with_modules, capsys):
        """Update all marketplaces."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        yaml_content = (
            "name: Updated\n"
            "description: Updated\n"
            "version: 2.0.0\n"
            "modules:\n"
            "  - name: new-module\n"
            "    description: New\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/new.git\n"
        )
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            registry = MarketplaceRegistry(market_dir, cache_dir)
            registry.update()

            captured = capsys.readouterr()
            assert "Updated 1/1 marketplaces" in captured.out

    def test_update_all_empty(self, tmp_path, capsys):
        """Update with no marketplaces registered."""
        market_dir = tmp_path / "market"
        cache_dir = market_dir / "cache"

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.update()

        captured = capsys.readouterr()
        assert "No marketplaces registered" in captured.out
