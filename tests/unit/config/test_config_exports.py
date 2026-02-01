"""
Unit tests for ktrdr.config public API exports.

Tests verify that all expected symbols can be imported from ktrdr.config,
ensuring the public API is complete and backward compatible.
"""


class TestNewConfigSystemExports:
    """Test M1 new config system exports from ktrdr.config."""

    def test_can_import_database_settings(self):
        """DatabaseSettings class should be importable from ktrdr.config."""
        from ktrdr.config import DatabaseSettings

        assert DatabaseSettings is not None

    def test_can_import_get_db_settings(self):
        """get_db_settings getter should be importable from ktrdr.config."""
        from ktrdr.config import get_db_settings

        assert callable(get_db_settings)

    def test_can_import_clear_settings_cache(self):
        """clear_settings_cache should be importable from ktrdr.config."""
        from ktrdr.config import clear_settings_cache

        assert callable(clear_settings_cache)

    def test_can_import_deprecated_field(self):
        """deprecated_field helper should be importable from ktrdr.config."""
        from ktrdr.config import deprecated_field

        assert callable(deprecated_field)


class TestValidationExports:
    """Test validation module exports from ktrdr.config."""

    def test_can_import_validate_all(self):
        """validate_all should be importable from ktrdr.config."""
        from ktrdr.config import validate_all

        assert callable(validate_all)

    def test_can_import_detect_insecure_defaults(self):
        """detect_insecure_defaults should be importable from ktrdr.config."""
        from ktrdr.config import detect_insecure_defaults

        assert callable(detect_insecure_defaults)


class TestDeprecationExports:
    """Test deprecation module exports from ktrdr.config."""

    def test_can_import_warn_deprecated_env_vars(self):
        """warn_deprecated_env_vars should be importable from ktrdr.config."""
        from ktrdr.config import warn_deprecated_env_vars

        assert callable(warn_deprecated_env_vars)

    def test_can_import_deprecated_names(self):
        """DEPRECATED_NAMES should be importable from ktrdr.config."""
        from ktrdr.config import DEPRECATED_NAMES

        assert isinstance(DEPRECATED_NAMES, dict)


class TestBackwardCompatibilityExports:
    """Test that existing exports still work (backward compatibility)."""

    # Note: metadata was removed in M7 cleanup - it's no longer exported

    def test_can_import_config_loader(self):
        """ConfigLoader should still be importable from ktrdr.config."""
        from ktrdr.config import ConfigLoader

        assert ConfigLoader is not None

    def test_can_import_input_validator(self):
        """InputValidator should still be importable from ktrdr.config."""
        from ktrdr.config import InputValidator

        assert InputValidator is not None

    def test_can_import_sanitize_parameter(self):
        """sanitize_parameter should still be importable from ktrdr.config."""
        from ktrdr.config import sanitize_parameter

        assert callable(sanitize_parameter)

    def test_can_import_sanitize_parameters(self):
        """sanitize_parameters should still be importable from ktrdr.config."""
        from ktrdr.config import sanitize_parameters

        assert callable(sanitize_parameters)

    def test_can_import_strategy_validator(self):
        """StrategyValidator should still be importable from ktrdr.config."""
        from ktrdr.config import StrategyValidator

        assert StrategyValidator is not None
