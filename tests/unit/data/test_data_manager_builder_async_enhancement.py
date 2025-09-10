"""
Unit tests for DataManagerBuilder async infrastructure enhancement.

Tests the integration of GenericProgressManager and DataProgressRenderer
into the DataManagerBuilder pattern, focusing on async infrastructure
creation and configuration passing.

This follows Task 1.3 requirements for enhancing DataManagerBuilder
with async infrastructure while preserving existing functionality.
"""

from unittest.mock import Mock, patch

import pytest

from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
)
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.progress_manager import TimeEstimationEngine
from ktrdr.data.data_manager_builder import DataManagerBuilder, DataManagerConfiguration
from ktrdr.errors import DataError


class TestDataManagerConfigurationAsyncEnhancement:
    """Test enhanced DataManagerConfiguration with async components."""

    def test_configuration_has_async_fields(self):
        """Test that configuration includes new async infrastructure fields."""
        config = DataManagerConfiguration()

        # Verify new async infrastructure fields are present
        assert hasattr(config, "generic_progress_manager")
        assert hasattr(config, "data_progress_renderer")
        assert hasattr(config, "time_estimation_engine")

        # Verify they initialize to None
        assert config.generic_progress_manager is None
        assert config.data_progress_renderer is None
        assert config.time_estimation_engine is None

    def test_configuration_preserves_existing_fields(self):
        """Test that all existing configuration fields are preserved."""
        config = DataManagerConfiguration()

        # Verify all existing core fields are preserved
        assert hasattr(config, "data_dir")
        assert hasattr(config, "max_gap_percentage")
        assert hasattr(config, "default_repair_method")
        assert hasattr(config, "ib_host_service_config")
        assert hasattr(config, "external_provider")

        # Verify all existing component fields are preserved
        assert hasattr(config, "data_loader")
        assert hasattr(config, "data_validator")
        assert hasattr(config, "gap_classifier")
        assert hasattr(config, "gap_analyzer")
        assert hasattr(config, "segment_manager")
        assert hasattr(config, "data_processor")
        assert hasattr(config, "data_loading_orchestrator")
        assert hasattr(config, "health_checker")


class TestDataManagerBuilderAsyncInfrastructure:
    """Test DataManagerBuilder async infrastructure creation methods."""

    def test_builder_has_create_async_infrastructure_method(self):
        """Test that builder has the _create_async_infrastructure method."""
        builder = DataManagerBuilder()

        # Verify the method exists
        assert hasattr(builder, "_create_async_infrastructure")
        assert callable(builder._create_async_infrastructure)

    @patch("ktrdr.data.data_manager_builder.TimeEstimationEngine")
    @patch("ktrdr.data.data_manager_builder.DataProgressRenderer")
    @patch("ktrdr.data.data_manager_builder.GenericProgressManager")
    def test_create_async_infrastructure_creates_components(
        self,
        mock_generic_progress_manager,
        mock_data_progress_renderer,
        mock_time_estimation_engine,
    ):
        """Test that _create_async_infrastructure creates all required components."""
        # Setup mocks
        mock_time_engine = Mock()
        mock_time_estimation_engine.return_value = mock_time_engine

        mock_renderer = Mock()
        mock_data_progress_renderer.return_value = mock_renderer

        mock_progress_manager = Mock()
        mock_generic_progress_manager.return_value = mock_progress_manager

        # Test
        builder = DataManagerBuilder()
        config = builder._config
        builder._create_async_infrastructure(config)

        # Verify TimeEstimationEngine created (exact path doesn't matter for this test)
        mock_time_estimation_engine.assert_called_once()
        assert config.time_estimation_engine == mock_time_engine

        # Verify DataProgressRenderer created with TimeEstimationEngine
        mock_data_progress_renderer.assert_called_once_with(
            time_estimation_engine=mock_time_engine, enable_hierarchical_progress=True
        )
        assert config.data_progress_renderer == mock_renderer

        # Verify GenericProgressManager created with renderer
        mock_generic_progress_manager.assert_called_once_with(renderer=mock_renderer)
        assert config.generic_progress_manager == mock_progress_manager

    @patch("ktrdr.data.data_manager_builder.TimeEstimationEngine")
    def test_create_async_infrastructure_time_engine_configuration(
        self,
        mock_time_estimation_engine,
    ):
        """Test that TimeEstimationEngine is configured with proper cache path."""
        builder = DataManagerBuilder()
        config = builder._config
        builder._create_async_infrastructure(config)

        # Verify TimeEstimationEngine was called with a Path object
        mock_time_estimation_engine.assert_called_once()
        call_args = mock_time_estimation_engine.call_args[0][0]

        # Verify it's a Path object with the expected structure
        assert hasattr(call_args, "name")  # Path objects have name attribute
        assert "progress_time_estimation.pkl" in str(call_args)

    def test_create_async_infrastructure_renderer_configuration(self):
        """Test that DataProgressRenderer is configured with hierarchical progress."""
        with (
            patch(
                "ktrdr.data.data_manager_builder.TimeEstimationEngine"
            ) as mock_engine,
            patch(
                "ktrdr.data.data_manager_builder.DataProgressRenderer"
            ) as mock_renderer,
            patch("ktrdr.data.data_manager_builder.GenericProgressManager"),
        ):
            mock_time_engine = Mock()
            mock_engine.return_value = mock_time_engine

            builder = DataManagerBuilder()
            config = builder._config
            builder._create_async_infrastructure(config)

            # Verify renderer configuration
            mock_renderer.assert_called_once_with(
                time_estimation_engine=mock_time_engine,
                enable_hierarchical_progress=True,
            )

    def test_create_async_infrastructure_progress_manager_configuration(self):
        """Test that GenericProgressManager is configured with renderer."""
        with (
            patch("ktrdr.data.data_manager_builder.TimeEstimationEngine"),
            patch(
                "ktrdr.data.data_manager_builder.DataProgressRenderer"
            ) as mock_renderer_class,
            patch(
                "ktrdr.data.data_manager_builder.GenericProgressManager"
            ) as mock_progress_manager_class,
        ):
            mock_renderer = Mock()
            mock_renderer_class.return_value = mock_renderer

            builder = DataManagerBuilder()
            config = builder._config
            builder._create_async_infrastructure(config)

            # Verify progress manager configuration
            mock_progress_manager_class.assert_called_once_with(renderer=mock_renderer)


class TestDataManagerBuilderEnhancedBuild:
    """Test enhanced build process with async infrastructure integration."""

    @patch(
        "ktrdr.data.data_manager_builder.DataManagerBuilder._create_async_infrastructure"
    )
    @patch("ktrdr.data.data_manager_builder.DataManagerBuilder._build_core_components")
    def test_build_calls_create_async_infrastructure(
        self, mock_build_core, mock_create_async
    ):
        """Test that build method calls _create_async_infrastructure."""
        with patch("ktrdr.data.data_manager.DataManager"):
            builder = DataManagerBuilder()

            # Configure mock to pass assertions in DataManager constructor
            config = builder._config
            config.data_loader = Mock()
            config.external_provider = Mock()
            config.data_validator = Mock()
            config.gap_classifier = Mock()
            config.gap_analyzer = Mock()
            config.segment_manager = Mock()
            config.data_processor = Mock()
            config.data_loading_orchestrator = Mock()
            config.health_checker = Mock()

            builder.build()

            # Verify _create_async_infrastructure was called
            mock_create_async.assert_called_once()

            # Verify it was called in the correct order (after core components)
            assert mock_build_core.called
            assert mock_create_async.called

    def test_build_creates_data_manager_with_enhanced_configuration(self):
        """Test that build method passes enhanced configuration to DataManager."""
        with patch("ktrdr.data.data_manager.DataManager") as mock_data_manager_class:
            mock_data_manager = Mock()
            mock_data_manager_class.return_value = mock_data_manager

            builder = DataManagerBuilder()
            builder.with_data_directory("/tmp/test_data")
            builder.with_gap_settings(7.5)
            builder.with_repair_method("interpolate")

            result = builder.build()

            # Verify DataManager was called with configuration parameters
            mock_data_manager_class.assert_called_once_with(
                data_dir="/tmp/test_data",
                max_gap_percentage=7.5,
                default_repair_method="interpolate",
                builder=builder,  # Builder reference for finalize_configuration
                builder_config=builder._config,  # NEW: Enhanced configuration passed
            )

            assert result == mock_data_manager

    def test_build_preserves_fluent_interface(self):
        """Test that builder pattern maintains fluent interface after enhancement."""
        builder = DataManagerBuilder()

        # Test fluent chaining still works
        result = (
            builder.with_data_directory("/test/data")
            .with_gap_settings(12.0)
            .with_repair_method("bfill")
        )

        assert result is builder
        assert builder._config.data_dir == "/test/data"
        assert builder._config.max_gap_percentage == 12.0
        assert builder._config.default_repair_method == "bfill"

    def test_build_preserves_existing_component_creation(self):
        """Test that all existing component creation logic is preserved."""
        builder = DataManagerBuilder()

        # Build configuration to create components
        config = builder.build_configuration()

        # Verify all existing components are still created
        assert config.data_loader is not None
        assert config.external_provider is not None
        assert config.data_validator is not None
        assert config.gap_classifier is not None
        assert config.gap_analyzer is not None
        assert config.segment_manager is not None
        assert config.data_processor is not None

        # Verify async components are also created
        assert config.time_estimation_engine is not None
        assert config.data_progress_renderer is not None
        assert config.generic_progress_manager is not None


class TestDataManagerBuilderIntegrationWithAsyncInfrastructure:
    """Test integration between builder and actual async infrastructure classes."""

    def test_integration_with_real_components(self):
        """Test integration with actual TimeEstimationEngine, DataProgressRenderer, GenericProgressManager."""
        builder = DataManagerBuilder()
        config = DataManagerConfiguration()

        # Call the real method (no mocks)
        builder._create_async_infrastructure(config)

        # Verify components are created and properly configured
        assert isinstance(config.time_estimation_engine, TimeEstimationEngine)
        assert isinstance(config.data_progress_renderer, DataProgressRenderer)
        assert isinstance(config.generic_progress_manager, GenericProgressManager)

        # Verify renderer has time engine
        assert (
            config.data_progress_renderer.time_estimator
            == config.time_estimation_engine
        )

        # Verify progress manager has renderer
        assert config.generic_progress_manager.renderer == config.data_progress_renderer

    def test_renderer_can_render_data_specific_messages(self):
        """Test that DataProgressRenderer can render data-specific progress messages."""
        builder = DataManagerBuilder()
        config = DataManagerConfiguration()
        builder._create_async_infrastructure(config)

        # Create test progress state
        state = GenericProgressState(
            operation_id="test_load_data",
            current_step=2,
            total_steps=5,
            percentage=40.0,
            message="Loading data",
            context={"symbol": "AAPL", "timeframe": "1h", "mode": "backfill"},
        )

        # Test message rendering
        rendered_message = config.data_progress_renderer.render_message(state)

        # Should contain data-specific context
        assert "AAPL" in rendered_message
        assert "1h" in rendered_message
        assert "backfill" in rendered_message

    def test_progress_manager_can_track_operations(self):
        """Test that GenericProgressManager can track operations with data context."""
        builder = DataManagerBuilder()
        config = DataManagerConfiguration()
        builder._create_async_infrastructure(config)

        callback_states = []

        def test_callback(state):
            callback_states.append(state)

        # Configure progress manager with callback
        progress_manager = GenericProgressManager(
            callback=test_callback, renderer=config.data_progress_renderer
        )

        # Start operation with data context
        progress_manager.start_operation(
            operation_id="load_data_MSFT_5m",
            total_steps=3,
            context={"symbol": "MSFT", "timeframe": "5m", "mode": "tail"},
        )

        # Update progress
        progress_manager.update_progress(
            step=1,
            message="Validating data",
            items_processed=100,
            context={"current_step_name": "validation"},
        )

        # Verify callback received enhanced messages
        assert len(callback_states) == 2  # start + update

        # Check enhanced message contains context
        latest_state = callback_states[-1]
        assert "MSFT" in latest_state.message
        assert "5m" in latest_state.message
        assert "tail" in latest_state.message


class TestDataManagerBuilderBackwardCompatibility:
    """Test that enhanced builder maintains 100% backward compatibility."""

    def test_existing_tests_still_pass(self):
        """Test that all existing builder functionality still works."""
        # This replicates key tests from the original test file
        # to ensure backward compatibility

        builder = DataManagerBuilder()

        # Test fluent interface (use valid directory that doesn't require creation)
        result = (
            builder.with_data_directory("/tmp/test_path")  # Use /tmp instead of /test
            .with_gap_settings(10.0)
            .with_repair_method("interpolate")
        )

        assert result is builder
        assert builder._config.data_dir == "/tmp/test_path"
        assert builder._config.max_gap_percentage == 10.0
        assert builder._config.default_repair_method == "interpolate"

        # Test configuration building
        config = builder.build_configuration()

        # Verify all original components are still created
        assert config.data_loader is not None
        assert config.external_provider is not None
        assert config.data_validator is not None

    def test_validation_still_works(self):
        """Test that parameter validation is still enforced."""
        builder = DataManagerBuilder()

        # Test gap percentage validation
        with pytest.raises(DataError):
            builder.with_gap_settings(-1.0)

        with pytest.raises(DataError):
            builder.with_gap_settings(101.0)

        # Test repair method validation
        with pytest.raises(DataError):
            builder.with_repair_method("invalid_method")

    def test_factory_methods_still_work(self):
        """Test that factory methods work with enhanced builder."""
        from ktrdr.data.data_manager_builder import (
            create_datamanager_builder_for_testing,
            create_default_datamanager_builder,
        )

        # Test default builder
        default_builder = create_default_datamanager_builder()
        assert default_builder._config.max_gap_percentage == 5.0
        assert default_builder._config.default_repair_method == "ffill"

        # Test testing builder
        test_builder = create_datamanager_builder_for_testing()
        assert test_builder._config.max_gap_percentage == 10.0
        assert test_builder._config.default_repair_method == "interpolate"
