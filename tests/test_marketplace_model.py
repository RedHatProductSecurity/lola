"""Tests for the Marketplace model."""

from unittest.mock import patch, mock_open
import pytest

from lola.models import Marketplace


class TestMarketplaceFromReference:
    """Tests for Marketplace.from_reference()."""

    @pytest.mark.parametrize(
        "yaml_content,expected",
        [
            (
                "name: official\n"
                "url: https://example.com/marketplace.yml\n"
                "enabled: true\n",
                {
                    "name": "official",
                    "url": "https://example.com/marketplace.yml",
                    "enabled": True,
                },
            ),
            (
                "name: test\n"
                "url: https://test.com/market.yml\n"
                "enabled: false\n",
                {
                    "name": "test",
                    "url": "https://test.com/market.yml",
                    "enabled": False,
                },
            ),
        ],
    )
    def test_from_reference(self, tmp_path, yaml_content, expected):
        """Load marketplace from reference file."""
        ref_file = tmp_path / "market.yml"
        ref_file.write_text(yaml_content)
        marketplace = Marketplace.from_reference(ref_file)
        assert marketplace.name == expected["name"]
        assert marketplace.url == expected["url"]
        assert marketplace.enabled == expected["enabled"]


class TestMarketplaceFromCache:
    """Tests for Marketplace.from_cache()."""

    def test_from_cache_full_catalog(self, tmp_path):
        """Load marketplace from cache with full catalog."""
        cache_file = tmp_path / "official.yml"
        cache_file.write_text(
            "name: Official Marketplace\n"
            "description: Curated modules\n"
            "version: 1.0.0\n"
            "url: https://example.com/marketplace.yml\n"
            "enabled: true\n"
            "modules:\n"
            "  - name: git-tools\n"
            "    description: Git automation\n"
            "    version: 1.2.0\n"
            "    repository: https://github.com/example/git-tools.git\n"
        )
        marketplace = Marketplace.from_cache(cache_file)
        assert marketplace.name == "Official Marketplace"
        assert marketplace.description == "Curated modules"
        assert marketplace.version == "1.0.0"
        assert len(marketplace.modules) == 1
        assert marketplace.modules[0]["name"] == "git-tools"


class TestMarketplaceFromUrl:
    """Tests for Marketplace.from_url()."""

    def test_from_url_downloads_and_parses(self):
        """Download marketplace from URL successfully."""
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
            marketplace = Marketplace.from_url(
                "https://example.com/market.yml", "test"
            )
            assert marketplace.name == "test"
            assert marketplace.url == "https://example.com/market.yml"
            assert marketplace.description == "Test catalog"
            assert marketplace.version == "1.0.0"
            assert len(marketplace.modules) == 1

    def test_from_url_network_error(self):
        """Handle network error when downloading marketplace."""
        from urllib.error import URLError

        with patch(
            "urllib.request.urlopen",
            side_effect=URLError("Connection failed"),
        ):
            with pytest.raises(
                ValueError, match="Failed to download marketplace"
            ):
                Marketplace.from_url(
                    "https://invalid.com/market.yml", "test"
                )


class TestMarketplaceValidate:
    """Tests for Marketplace.validate()."""

    @pytest.mark.parametrize(
        "marketplace_data,expected_valid,expected_error",
        [
            (
                {"name": "test", "url": "https://example.com"},
                True,
                None,
            ),
            (
                {"name": "", "url": "https://example.com"},
                False,
                "Missing required field: name",
            ),
            (
                {"name": "test", "url": ""},
                False,
                "Missing required field: url",
            ),
            (
                {
                    "name": "test",
                    "url": "https://example.com",
                    "modules": [{"name": "mod"}],
                },
                False,
                "Missing version for marketplace catalog",
            ),
            (
                {
                    "name": "test",
                    "url": "https://example.com",
                    "version": "1.0.0",
                    "modules": [{"name": "test-module"}],
                },
                False,
                "missing 'description'",
            ),
        ],
    )
    def test_validate(
        self, marketplace_data, expected_valid, expected_error
    ):
        """Validate marketplace with various scenarios."""
        marketplace = Marketplace(**marketplace_data)
        is_valid, errors = marketplace.validate()
        assert is_valid == expected_valid
        if expected_error:
            assert any(expected_error in e for e in errors)

    def test_validate_complete(self):
        """Validate complete marketplace with modules."""
        marketplace = Marketplace(
            name="official",
            url="https://example.com/market.yml",
            version="1.0.0",
            description="Official marketplace",
            modules=[
                {
                    "name": "git-tools",
                    "description": "Git automation",
                    "version": "1.2.0",
                    "repository": "https://github.com/test/git.git",
                }
            ],
        )
        is_valid, errors = marketplace.validate()
        assert is_valid is True
        assert errors == []


class TestMarketplaceSerialization:
    """Tests for to_reference_dict() and to_cache_dict()."""

    def test_to_reference_dict(self):
        """Convert marketplace to reference dict."""
        marketplace = Marketplace(
            name="test",
            url="https://example.com/market.yml",
            enabled=False,
        )
        ref_dict = marketplace.to_reference_dict()
        assert ref_dict == {
            "name": "test",
            "url": "https://example.com/market.yml",
            "enabled": False,
        }

    @pytest.mark.parametrize(
        "description,expected_name",
        [
            ("Test marketplace", "Test marketplace"),
            ("", "fallback"),
        ],
    )
    def test_to_cache_dict(self, description, expected_name):
        """Convert marketplace to cache dict."""
        marketplace = Marketplace(
            name="fallback",
            url="https://example.com/market.yml",
            description=description,
            version="1.0.0",
        )
        cache_dict = marketplace.to_cache_dict()
        assert cache_dict["name"] == expected_name
        assert cache_dict["url"] == "https://example.com/market.yml"
