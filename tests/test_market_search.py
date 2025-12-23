"""Tests for marketplace search functionality."""

from pathlib import Path

from rich.console import Console

from lola.market.search import (
    get_enabled_marketplaces,
    match_module,
    format_search_result,
    search_market,
    display_market,
)


class TestGetEnabledMarketplaces:
    """Tests for get_enabled_marketplaces()."""

    def test_get_enabled_marketplaces(self, marketplace_with_modules):
        """Get enabled marketplaces successfully."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        marketplaces = get_enabled_marketplaces(market_dir, cache_dir)

        assert len(marketplaces) == 1
        marketplace, name = marketplaces[0]
        assert name == "official"
        assert len(marketplace.modules) == 2

    def test_get_enabled_skips_disabled(self, marketplace_with_modules):
        """Skip disabled marketplaces."""
        import yaml

        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        # Add disabled marketplace to the same directory
        disabled_ref = {
            "name": "disabled-market",
            "url": "https://example.com/disabled.yml",
            "enabled": False,
        }
        disabled_cache = {
            "name": "Disabled",
            "version": "1.0.0",
            "url": "https://example.com/disabled.yml",
            "enabled": False,
            "modules": [{"name": "test-module"}],
        }

        with open(market_dir / "disabled-market.yml", "w") as f:
            yaml.dump(disabled_ref, f)
        with open(cache_dir / "disabled-market.yml", "w") as f:
            yaml.dump(disabled_cache, f)

        marketplaces = get_enabled_marketplaces(market_dir, cache_dir)

        # Only the enabled marketplace should be returned
        assert len(marketplaces) == 1
        assert marketplaces[0][1] == "official"

    def test_get_enabled_empty(self, tmp_path):
        """Return empty list when no marketplaces."""
        market_dir = tmp_path / "market"
        cache_dir = tmp_path / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        marketplaces = get_enabled_marketplaces(market_dir, cache_dir)

        assert marketplaces == []

    def test_cache_recovery(self, marketplace_with_modules):
        """Recover missing cache by re-downloading."""
        from unittest.mock import patch, mock_open

        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        cache_file = cache_dir / "official.yml"
        cache_file.unlink()

        yaml_content = (
            "name: Official Marketplace\n"
            "description: Official catalog\n"
            "version: 1.0.0\n"
            "modules:\n"
            "  - name: git-tools\n"
            "    description: Git utilities\n"
            "    version: 1.0.0\n"
            "    repository: https://github.com/test/git-tools.git\n"
        )
        mock_response = mock_open(read_data=yaml_content.encode())()

        with patch("urllib.request.urlopen", return_value=mock_response):
            marketplaces = get_enabled_marketplaces(market_dir, cache_dir)

        assert len(marketplaces) == 1
        assert cache_file.exists()

    def test_cache_recovery_fails(self, marketplace_with_modules):
        """Skip marketplace when cache recovery fails."""
        from unittest.mock import patch
        from urllib.error import URLError

        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        cache_file = cache_dir / "official.yml"
        cache_file.unlink()

        with patch(
            "urllib.request.urlopen",
            side_effect=URLError("Connection failed"),
        ):
            marketplaces = get_enabled_marketplaces(market_dir, cache_dir)

        assert marketplaces == []
        assert not cache_file.exists()


class TestMatchModule:
    """Tests for match_module()."""

    def test_match_by_name(self):
        """Match module by name."""
        module = {
            "name": "git-tools",
            "description": "Git utilities",
            "tags": ["git", "vcs"],
        }

        assert match_module(module, "git") is True
        assert match_module(module, "tools") is True
        assert match_module(module, "git-tools") is True

    def test_match_by_description(self):
        """Match module by description."""
        module = {
            "name": "git-tools",
            "description": "Git utilities for version control",
            "tags": [],
        }

        assert match_module(module, "utilities") is True
        assert match_module(module, "version") is True
        assert match_module(module, "control") is True

    def test_match_by_tags(self):
        """Match module by tags."""
        module = {
            "name": "git-tools",
            "description": "Git utilities",
            "tags": ["git", "vcs", "version-control"],
        }

        assert match_module(module, "vcs") is True
        assert match_module(module, "version") is True

    def test_match_case_insensitive(self):
        """Match is case insensitive."""
        module = {
            "name": "Git-Tools",
            "description": "GIT Utilities",
            "tags": ["GIT", "VCS"],
        }

        assert match_module(module, "git") is True
        assert match_module(module, "utilities") is True
        assert match_module(module, "vcs") is True

    def test_no_match(self):
        """Return False when no match."""
        module = {
            "name": "git-tools",
            "description": "Git utilities",
            "tags": ["git", "vcs"],
        }

        assert match_module(module, "python") is False
        assert match_module(module, "docker") is False


class TestFormatSearchResult:
    """Tests for format_search_result()."""

    def test_format_result(self):
        """Format search result correctly."""
        module = {
            "name": "git-tools",
            "description": "Git utilities for version control",
            "version": "1.0.0",
        }

        result = format_search_result(module, "official")

        assert result["name"] == "git-tools"
        assert result["description"] == "Git utilities for version control"
        assert result["version"] == "1.0.0"
        assert result["marketplace"] == "official"

    def test_format_truncates_long_description(self):
        """Truncate long descriptions to 60 characters."""
        module = {
            "name": "test-module",
            "description": "This is a very long description that should be truncated at sixty characters",
            "version": "1.0.0",
        }

        result = format_search_result(module, "official")

        assert len(result["description"]) == 63  # 60 chars + "..."
        assert result["description"].endswith("...")
        assert "This is a very long description that should be truncated" in result["description"]

    def test_format_handles_missing_fields(self):
        """Handle missing optional fields."""
        module = {"name": "test-module"}

        result = format_search_result(module, "official")

        assert result["name"] == "test-module"
        assert result["description"] == ""
        assert result["version"] == ""
        assert result["marketplace"] == "official"


class TestSearchMarket:
    """Tests for search_market()."""

    def test_search_finds_matches(self, marketplace_with_modules):
        """Search finds matching modules."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        results = search_market("git", market_dir, cache_dir)

        assert len(results) == 1
        assert results[0]["name"] == "git-tools"
        assert results[0]["marketplace"] == "official"

    def test_search_multiple_matches(self, marketplace_with_modules):
        """Search finds multiple matching modules."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        # Search for "util" which matches both modules' descriptions
        results = search_market("util", market_dir, cache_dir)

        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"git-tools", "python-utils"}

    def test_search_no_matches(self, marketplace_with_modules):
        """Search returns empty list when no matches."""
        market_dir = marketplace_with_modules["market_dir"]
        cache_dir = marketplace_with_modules["cache_dir"]

        results = search_market("nonexistent", market_dir, cache_dir)

        assert results == []

    def test_search_empty_marketplaces(self, tmp_path):
        """Search returns empty list when no marketplaces."""
        market_dir = tmp_path / "market"
        cache_dir = tmp_path / "cache"
        market_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)

        results = search_market("git", market_dir, cache_dir)

        assert results == []


class TestDisplayMarket:
    """Tests for display_market()."""

    def test_display_results(self, capsys):
        """Display search results in table."""
        results = [
            {
                "name": "git-tools",
                "description": "Git utilities",
                "version": "1.0.0",
                "marketplace": "official",
            },
            {
                "name": "python-utils",
                "description": "Python utilities",
                "version": "1.2.0",
                "marketplace": "official",
            },
        ]

        console = Console()
        display_market(results, "util", console)

        captured = capsys.readouterr()
        assert "Found 2 modules" in captured.out
        assert "git-tools" in captured.out
        assert "python-utils" in captured.out
        assert "1.0.0" in captured.out
        assert "1.2.0" in captured.out
        assert "official" in captured.out

    def test_display_single_result(self, capsys):
        """Display singular form for single result."""
        results = [
            {
                "name": "git-tools",
                "description": "Git utilities",
                "version": "1.0.0",
                "marketplace": "official",
            }
        ]

        console = Console()
        display_market(results, "git", console)

        captured = capsys.readouterr()
        assert "Found 1 module" in captured.out
        assert "git-tools" in captured.out

    def test_display_no_results(self, capsys):
        """Display message when no results found."""
        console = Console()
        display_market([], "nonexistent", console)

        captured = capsys.readouterr()
        assert "No modules found matching 'nonexistent'" in captured.out
        assert "Tip: Check spelling" in captured.out
