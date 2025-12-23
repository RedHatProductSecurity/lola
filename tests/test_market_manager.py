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


class TestMarketplaceRegistrySearch:
    """Tests for MarketplaceRegistry.search()."""

    def test_search_with_results(self, marketplace_with_modules, capsys):
        """Search displays results when matches found."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.search("git")

        captured = capsys.readouterr()
        assert "Found 1 module" in captured.out
        assert "git-tools" in captured.out
        assert "Git utilities" in captured.out

    def test_search_no_results(self, marketplace_with_modules, capsys):
        """Search displays message when no matches."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.search("nonexistent")

        captured = capsys.readouterr()
        assert "No modules found matching 'nonexistent'" in captured.out

    def test_search_no_marketplaces(self, tmp_path, capsys):
        """Search displays message when no marketplaces registered."""
        market_dir = tmp_path / "market"
        cache_dir = tmp_path / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        registry = MarketplaceRegistry(market_dir, cache_dir)
        registry.search("git")

        captured = capsys.readouterr()
        assert "No marketplaces registered" in captured.out
        assert "lola market add" in captured.out


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


class TestMarketplaceRegistrySearchModuleAll:
    """Tests for MarketplaceRegistry.search_module_all()."""

    def test_search_module_all_single_match(self, marketplace_with_modules):
        """Find module in single marketplace."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        matches = registry.search_module_all("git-tools")

        assert len(matches) == 1
        module, marketplace_name = matches[0]
        assert module["name"] == "git-tools"
        assert marketplace_name == "official"

    def test_search_module_all_multiple_matches(self, tmp_path):
        """Find module in multiple marketplaces."""
        import yaml

        market_dir = tmp_path / "market"
        cache_dir = tmp_path / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        # Create two marketplaces with the same module
        for idx, name in enumerate(["market-a", "market-b"]):
            ref = {
                "name": name,
                "url": f"https://example.com/{name}.yml",
                "enabled": True,
            }
            cache = {
                "name": f"Marketplace {name.upper()}",
                "version": "1.0.0",
                "url": f"https://example.com/{name}.yml",
                "modules": [
                    {
                        "name": "shared-module",
                        "description": f"Module from {name}",
                        "version": f"1.{idx}.0",
                        "repository": f"https://github.com/{name}/shared.git",
                    }
                ],
            }

            with open(market_dir / f"{name}.yml", "w") as f:
                yaml.dump(ref, f)
            with open(cache_dir / f"{name}.yml", "w") as f:
                yaml.dump(cache, f)

        registry = MarketplaceRegistry(market_dir, cache_dir)
        matches = registry.search_module_all("shared-module")

        assert len(matches) == 2
        marketplaces = {m[1] for m in matches}
        assert marketplaces == {"market-a", "market-b"}

    def test_search_module_all_no_matches(self, marketplace_with_modules):
        """Return empty list when module not found."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        matches = registry.search_module_all("nonexistent")

        assert matches == []

    def test_search_module_all_skips_disabled(self, tmp_path):
        """Skip disabled marketplaces."""
        import yaml

        market_dir = tmp_path / "market"
        cache_dir = tmp_path / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        # Create enabled marketplace
        enabled_ref = {
            "name": "enabled",
            "url": "https://example.com/enabled.yml",
            "enabled": True,
        }
        enabled_cache = {
            "name": "Enabled",
            "version": "1.0.0",
            "url": "https://example.com/enabled.yml",
            "modules": [{"name": "test-module", "description": "Test"}],
        }

        # Create disabled marketplace with same module
        disabled_ref = {
            "name": "disabled",
            "url": "https://example.com/disabled.yml",
            "enabled": False,
        }
        disabled_cache = {
            "name": "Disabled",
            "version": "1.0.0",
            "url": "https://example.com/disabled.yml",
            "modules": [{"name": "test-module", "description": "Test"}],
        }

        with open(market_dir / "enabled.yml", "w") as f:
            yaml.dump(enabled_ref, f)
        with open(cache_dir / "enabled.yml", "w") as f:
            yaml.dump(enabled_cache, f)
        with open(market_dir / "disabled.yml", "w") as f:
            yaml.dump(disabled_ref, f)
        with open(cache_dir / "disabled.yml", "w") as f:
            yaml.dump(disabled_cache, f)

        registry = MarketplaceRegistry(market_dir, cache_dir)
        matches = registry.search_module_all("test-module")

        # Should only find in enabled marketplace
        assert len(matches) == 1
        assert matches[0][1] == "enabled"


class TestMarketplaceRegistrySelectMarketplace:
    """Tests for MarketplaceRegistry.select_marketplace()."""

    def test_select_single_match(self, marketplace_with_modules):
        """Return marketplace name when only one match."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        matches = [({"name": "test", "description": "Test"}, "official")]

        result = registry.select_marketplace("test", matches)

        assert result == "official"

    def test_select_no_matches(self, marketplace_with_modules):
        """Return None when no matches."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.select_marketplace("test", [])

        assert result is None

    def test_select_multiple_matches_with_version(
        self, marketplace_with_modules, monkeypatch
    ):
        """Prompt user to select when multiple matches (with version)."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        matches = [
            (
                {
                    "name": "test",
                    "description": "From market A",
                    "version": "1.0.0",
                },
                "market-a",
            ),
            (
                {
                    "name": "test",
                    "description": "From market B",
                    "version": "2.0.0",
                },
                "market-b",
            ),
        ]

        # Mock user selecting option 2
        monkeypatch.setattr("click.prompt", lambda *args, **kwargs: 2)

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.select_marketplace("test", matches, show_version=True)

        assert result == "market-b"

    def test_select_multiple_matches_without_version(
        self, marketplace_with_modules, monkeypatch, capsys
    ):
        """Display format without version when show_version=False."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        matches = [
            (
                {
                    "name": "test",
                    "description": "From market A",
                    "version": "1.0.0",
                },
                "market-a",
            ),
            (
                {
                    "name": "test",
                    "description": "From market B",
                    "version": "2.0.0",
                },
                "market-b",
            ),
        ]

        # Mock user selecting option 1
        monkeypatch.setattr("click.prompt", lambda *args, **kwargs: 1)

        registry = MarketplaceRegistry(market_dir, cache_dir)
        result = registry.select_marketplace("test", matches, show_version=False)

        assert result == "market-a"

        # Verify output doesn't include version
        captured = capsys.readouterr()
        assert "@market-a/test - From market A" in captured.out
        assert ":1.0.0" not in captured.out
        assert ":2.0.0" not in captured.out
