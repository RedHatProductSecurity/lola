"""Tests for marketplace validation."""

import pytest

from lola.market.manager import validate_marketplace_name
from lola.exceptions import MarketplaceNameError


class TestValidateMarketplaceName:
    """Tests for validate_marketplace_name()."""

    def test_valid_names(self):
        """Accept valid marketplace names."""
        assert validate_marketplace_name("official") == "official"
        assert validate_marketplace_name("my-market") == "my-market"
        assert validate_marketplace_name("test123") == "test123"
        assert validate_marketplace_name("my_market") == "my_market"

    def test_empty_name(self):
        """Reject empty name."""
        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name("")

        assert "name cannot be empty" in str(exc_info.value)

    def test_dot_traversal(self):
        """Reject path traversal attempts."""
        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name(".")

        assert "path traversal not allowed" in str(exc_info.value)

        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name("..")

        assert "path traversal not allowed" in str(exc_info.value)

    def test_path_separators(self):
        """Reject names with path separators."""
        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name("foo/bar")

        assert "path separators not allowed" in str(exc_info.value)

        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name("foo\\bar")

        assert "path separators not allowed" in str(exc_info.value)

    def test_starts_with_dot(self):
        """Reject names starting with dot."""
        with pytest.raises(MarketplaceNameError) as exc_info:
            validate_marketplace_name(".hidden")

        assert "cannot start with dot" in str(exc_info.value)
