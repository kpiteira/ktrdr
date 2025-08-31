"""
Unit tests for DataManagerBuilder pattern.

Tests the builder pattern implementation for DataManager initialization,
focusing on configuration, validation, and component construction.
"""

from unittest.mock import Mock, patch

import pytest

from ktrdr.config.models import IbHostServiceConfig
from ktrdr.data.data_manager_builder import (
    DataManagerBuilder,
    DataManagerConfiguration,
    IbConfigurationLoader,
    create_datamanager_builder_for_testing,
    create_default_datamanager_builder,
)
from ktrdr.errors import DataError


class TestDataManagerConfiguration:
    """Test DataManagerConfiguration container."""

    def test_initialization(self):
        """Test configuration container initialization with defaults."""
        config = DataManagerConfiguration()

        assert config.data_dir is None
        assert config.max_gap_percentage == 5.0
        assert config.default_repair_method == "ffill"
        assert config.ib_host_service_config is None
        assert config.external_provider is None


class TestIbConfigurationLoader:
    """Test IB configuration loading logic."""

    @patch("ktrdr.data.data_manager_builder.Path")
    @patch("ktrdr.data.data_manager_builder.ConfigLoader")
    def test_load_configuration_from_file(
        self, mock_config_loader_class, mock_path_class
    ):
        """Test loading configuration from settings file."""
        # Setup mocks
        mock_config_loader = Mock()
        mock_config_loader_class.return_value = mock_config_loader

        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path

        mock_config = Mock()
        mock_ib_config = IbHostServiceConfig(enabled=True, url="http://test:5001")
        mock_config.ib_host_service = mock_ib_config
        mock_config_loader.load.return_value = mock_config

        # Test
        result = IbConfigurationLoader.load_configuration()

        # Verify
        assert result.enabled
        assert result.url == "http://test:5001"
        mock_config_loader.load.assert_called()

    @patch.dict("os.environ", {}, clear=True)  # Clear all environment variables
    @patch("ktrdr.data.data_manager_builder.Path")
    def test_load_configuration_no_file(self, mock_path_class):
        """Test default configuration when no settings file exists."""
        # Setup mocks
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        # Test
        result = IbConfigurationLoader.load_configuration()

        # Verify defaults
        assert not result.enabled
        assert result.url == "http://localhost:5001"

    @patch.dict(
        "os.environ",
        {"USE_IB_HOST_SERVICE": "true", "IB_HOST_SERVICE_URL": "http://env:6001"},
    )
    @patch("ktrdr.data.data_manager_builder.Path")
    def test_environment_variable_overrides(self, mock_path_class):
        """Test environment variable overrides."""
        # Setup mocks
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        # Test
        result = IbConfigurationLoader.load_configuration()

        # Verify environment overrides
        assert result.enabled
        assert result.url == "http://env:6001"


class TestDataManagerBuilder:
    """Test DataManagerBuilder fluent interface and validation."""

    def test_builder_initialization(self):
        """Test builder initializes with default configuration."""
        builder = DataManagerBuilder()

        assert builder._config is not None
        assert builder._config.max_gap_percentage == 5.0
        assert builder._config.default_repair_method == "ffill"

    def test_with_data_directory(self):
        """Test data directory configuration."""
        builder = DataManagerBuilder()
        result = builder.with_data_directory("/test/path")

        assert result is builder  # Fluent interface
        assert builder._config.data_dir == "/test/path"

    def test_with_gap_settings_valid(self):
        """Test valid gap percentage configuration."""
        builder = DataManagerBuilder()
        result = builder.with_gap_settings(10.0)

        assert result is builder  # Fluent interface
        assert builder._config.max_gap_percentage == 10.0

    def test_with_gap_settings_invalid_low(self):
        """Test invalid gap percentage (too low)."""
        builder = DataManagerBuilder()

        with pytest.raises(DataError) as exc_info:
            builder.with_gap_settings(-1.0)

        assert "max_gap_percentage" in str(exc_info.value)
        assert "Must be between 0 and 100" in str(exc_info.value)

    def test_with_gap_settings_invalid_high(self):
        """Test invalid gap percentage (too high)."""
        builder = DataManagerBuilder()

        with pytest.raises(DataError) as exc_info:
            builder.with_gap_settings(101.0)

        assert "max_gap_percentage" in str(exc_info.value)
        assert "Must be between 0 and 100" in str(exc_info.value)

    def test_with_repair_method_valid(self):
        """Test valid repair method configuration."""
        builder = DataManagerBuilder()
        result = builder.with_repair_method("interpolate")

        assert result is builder  # Fluent interface
        assert builder._config.default_repair_method == "interpolate"

    def test_with_repair_method_invalid(self):
        """Test invalid repair method."""
        builder = DataManagerBuilder()

        with pytest.raises(DataError) as exc_info:
            builder.with_repair_method("invalid_method")

        assert "Invalid repair method" in str(exc_info.value)
        assert "invalid_method" in str(exc_info.value)

    def test_with_ib_configuration(self):
        """Test IB configuration setting."""
        builder = DataManagerBuilder()
        config = IbHostServiceConfig(enabled=True, url="http://custom:7001")

        result = builder.with_ib_configuration(config)

        assert result is builder  # Fluent interface
        assert builder._config.ib_host_service_config == config

    def test_fluent_interface_chaining(self):
        """Test that all builder methods support chaining."""
        ib_config = IbHostServiceConfig(enabled=True, url="http://test:8001")

        builder = (
            DataManagerBuilder()
            .with_data_directory("/custom/path")
            .with_gap_settings(15.0)
            .with_repair_method("bfill")
            .with_ib_configuration(ib_config)
        )

        config = builder._config
        assert config.data_dir == "/custom/path"
        assert config.max_gap_percentage == 15.0
        assert config.default_repair_method == "bfill"
        assert config.ib_host_service_config == ib_config


class TestDataManagerBuilderComponentConstruction:
    """Test builder component construction methods."""

    @patch("ktrdr.data.data_manager_builder.LocalDataLoader")
    def test_build_data_loader(self, mock_loader_class):
        """Test data loader construction."""
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader

        builder = DataManagerBuilder().with_data_directory("/test/data")
        loader = builder._build_data_loader()

        assert loader == mock_loader
        mock_loader_class.assert_called_with(data_dir="/test/data")

    @patch("ktrdr.data.data_manager_builder.IbDataAdapter")
    @patch("ktrdr.data.data_manager_builder.IbConfigurationLoader")
    def test_build_ib_adapter_with_config(self, mock_loader, mock_adapter_class):
        """Test IB adapter construction with configuration."""
        # Setup mocks
        mock_config = IbHostServiceConfig(enabled=True, url="http://test:5001")
        mock_loader.load_configuration.return_value = mock_config
        mock_adapter = Mock()
        mock_adapter_class.return_value = mock_adapter

        builder = DataManagerBuilder()
        adapter = builder._build_ib_adapter()

        # Verify adapter created with configuration
        mock_adapter_class.assert_called_with(
            use_host_service=True, host_service_url="http://test:5001"
        )
        assert adapter == mock_adapter

    @patch("ktrdr.data.data_manager_builder.IbDataAdapter")
    def test_build_ib_adapter_fallback(self, mock_adapter_class):
        """Test IB adapter construction with fallback on error."""
        # Setup mocks - first call raises exception, second succeeds
        mock_adapter_class.side_effect = [Exception("Config error"), Mock()]

        builder = DataManagerBuilder()
        builder._build_ib_adapter()

        # Verify fallback was used
        assert mock_adapter_class.call_count == 2
        # First call with config, second call without args (fallback)

    def test_build_core_components(self):
        """Test core components construction."""
        builder = DataManagerBuilder()
        builder._build_core_components()

        config = builder._config
        assert config.data_loader is not None
        assert config.external_provider is not None
        assert config.data_validator is not None
        assert config.gap_classifier is not None
        assert config.gap_analyzer is not None
        assert config.segment_manager is not None
        assert config.data_processor is not None

    def test_build_orchestration_components(self):
        """Test orchestration components that need DataManager reference."""
        builder = DataManagerBuilder()
        builder._build_core_components()  # Prerequisites

        mock_data_manager = Mock()
        builder._build_orchestration_components(mock_data_manager)

        config = builder._config
        assert config.data_loading_orchestrator is not None
        assert config.health_checker is not None

        # Verify orchestrator got DataManager reference
        assert config.data_loading_orchestrator.data_manager == mock_data_manager


class TestDataManagerBuilderIntegration:
    """Test full builder configuration and integration."""

    @patch("ktrdr.data.data_manager_builder.LocalDataLoader")
    def test_build_configuration_complete(self, mock_loader_class):
        """Test complete configuration building."""
        mock_loader_class.return_value = Mock()

        builder = (
            DataManagerBuilder()
            .with_data_directory("/test")
            .with_gap_settings(8.0)
            .with_repair_method("median")
        )

        config = builder.build_configuration()

        # Verify all core components are built
        assert config.data_loader is not None
        assert config.external_provider is not None
        assert config.data_validator is not None
        assert config.gap_classifier is not None
        assert config.gap_analyzer is not None
        assert config.segment_manager is not None
        assert config.data_processor is not None

        # Verify configuration values preserved
        assert config.max_gap_percentage == 8.0
        assert config.default_repair_method == "median"

    def test_finalize_configuration(self):
        """Test configuration finalization with DataManager reference."""
        builder = DataManagerBuilder()
        config = builder.build_configuration()  # Build core first

        mock_data_manager = Mock()
        final_config = builder.finalize_configuration(mock_data_manager)

        # Verify DataManager-dependent components are built
        assert final_config.data_loading_orchestrator is not None
        assert final_config.health_checker is not None

        # Should be same config object
        assert final_config is config


class TestDataManagerBuilderFactories:
    """Test builder factory functions."""

    def test_create_default_datamanager_builder(self):
        """Test default builder factory."""
        builder = create_default_datamanager_builder()

        config = builder._config
        assert config.max_gap_percentage == 5.0
        assert config.default_repair_method == "ffill"

    def test_create_datamanager_builder_for_testing(self):
        """Test testing builder factory."""
        builder = create_datamanager_builder_for_testing()

        config = builder._config
        assert config.max_gap_percentage == 10.0  # More lenient for tests
        assert config.default_repair_method == "interpolate"


class TestDataManagerBuilderValidation:
    """Test builder parameter validation."""

    def test_repair_methods_constant(self):
        """Test that REPAIR_METHODS contains expected methods."""
        expected_methods = {
            "ffill",
            "bfill",
            "interpolate",
            "zero",
            "mean",
            "median",
            "drop",
        }

        assert DataManagerBuilder.REPAIR_METHODS == expected_methods

    def test_validation_error_details(self):
        """Test that validation errors include helpful details."""
        builder = DataManagerBuilder()

        # Test gap percentage error details
        with pytest.raises(DataError) as exc_info:
            builder.with_gap_settings(150.0)

        error = exc_info.value
        assert error.error_code == "DATA-InvalidParameter"
        assert "max_gap_percentage" in error.details["parameter"]
        assert error.details["value"] == 150.0
        assert "0-100" in error.details["valid_range"]

        # Test repair method error details
        with pytest.raises(DataError) as exc_info:
            builder.with_repair_method("unknown")

        error = exc_info.value
        assert error.error_code == "DATA-InvalidParameter"
        assert "default_repair_method" in error.details["parameter"]
        assert error.details["value"] == "unknown"
        assert "ffill" in error.details["valid_options"]
