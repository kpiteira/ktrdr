"""Tests for INDICATOR_REGISTRY package export.

Task 1.5: Verify INDICATOR_REGISTRY is exported from ktrdr.indicators package.
"""


class TestIndicatorRegistryExport:
    """Tests for INDICATOR_REGISTRY package-level export."""

    def test_indicator_registry_importable_from_package(self) -> None:
        """INDICATOR_REGISTRY should be importable from ktrdr.indicators."""
        from ktrdr.indicators import INDICATOR_REGISTRY

        assert INDICATOR_REGISTRY is not None

    def test_rsi_in_registry_from_package_import(self) -> None:
        """RSI should be in INDICATOR_REGISTRY when imported from package."""
        from ktrdr.indicators import INDICATOR_REGISTRY

        assert "rsi" in INDICATOR_REGISTRY

    def test_registry_has_expected_methods(self) -> None:
        """Exported INDICATOR_REGISTRY should have expected API."""
        from ktrdr.indicators import INDICATOR_REGISTRY

        # Core methods should be available
        assert hasattr(INDICATOR_REGISTRY, "get")
        assert hasattr(INDICATOR_REGISTRY, "list_types")
        assert hasattr(INDICATOR_REGISTRY, "get_params_schema")
