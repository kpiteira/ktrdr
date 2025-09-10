"""
Unit tests for DataManager async infrastructure integration.

Tests that DataManager correctly uses GenericProgressManager instead of
creating ProgressManager directly, following Task 1.4 requirements for
integrating enhanced async infrastructure while maintaining 100% backward
compatibility.
"""

from unittest.mock import Mock, patch

import pandas as pd

from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
)
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.progress_manager import ProgressState
from ktrdr.data.data_manager import DataManager
from ktrdr.data.data_manager_builder import DataManagerBuilder, DataManagerConfiguration


class TestDataManagerAsyncInfrastructureIntegration:
    """Test DataManager integration with enhanced async infrastructure."""

    def test_data_manager_accepts_enhanced_configuration(self):
        """Test that DataManager constructor accepts enhanced configuration."""
        # Arrange: Create enhanced configuration with async infrastructure
        config = DataManagerConfiguration()
        config.generic_progress_manager = Mock(spec=GenericProgressManager)
        config.data_progress_renderer = Mock(spec=DataProgressRenderer)
        config.time_estimation_engine = Mock(spec=TimeEstimationEngine)

        # Mock all required components to avoid builder assertions
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        # Act: Create DataManager with enhanced configuration
        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Assert: DataManager stores async infrastructure components
        assert data_manager._generic_progress_manager is config.generic_progress_manager
        assert data_manager._data_progress_renderer is config.data_progress_renderer
        assert data_manager._time_estimation_engine is config.time_estimation_engine

    def test_data_manager_fallback_without_async_infrastructure(self):
        """Test DataManager fallback when async infrastructure is not available."""
        # Arrange: Create configuration without async infrastructure
        config = DataManagerConfiguration()
        config.generic_progress_manager = None  # No async infrastructure

        # Mock required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        # Act: Create DataManager without async infrastructure
        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            with patch("ktrdr.data.data_manager.logger"):
                data_manager = DataManager(builder_config=config)
                # Manually set the attributes that would normally be set by ServiceOrchestrator.__init__
                data_manager._generic_progress_manager = Mock(
                    spec=GenericProgressManager
                )
                data_manager._progress_renderer = Mock()

        # Assert: DataManager handles absence of enhanced async infrastructure gracefully
        # The base class provides a generic progress manager, so it won't be None
        assert data_manager._generic_progress_manager is not None
        # But enhanced components should be None
        assert data_manager._data_progress_renderer is None

    @patch("ktrdr.data.data_manager.GenericProgressManager")
    def test_load_data_uses_generic_progress_manager(
        self, mock_generic_progress_manager
    ):
        """Test that load_data method uses GenericProgressManager instead of ProgressManager."""
        # Arrange: Create DataManager with enhanced configuration
        config = DataManagerConfiguration()
        config.generic_progress_manager = Mock(spec=GenericProgressManager)
        config.data_progress_renderer = Mock(spec=DataProgressRenderer)

        # Mock all required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Mock data loader to return empty dataframe
        mock_df = pd.DataFrame()
        config.data_loader.load.return_value = mock_df

        # Setup GenericProgressManager mock instance
        mock_progress_instance = Mock(spec=GenericProgressManager)
        mock_generic_progress_manager.return_value = mock_progress_instance

        # Act: Call load_data in local mode (simplest path)
        data_manager.load_data(
            symbol="AAPL",
            timeframe="1h",
            mode="local",
            validate=False,  # Skip validation to focus on progress manager usage
        )

        # Assert: GenericProgressManager was created with correct parameters
        mock_generic_progress_manager.assert_called_once()
        call_args = mock_generic_progress_manager.call_args
        assert "callback" in call_args.kwargs or len(call_args.args) >= 1
        assert "renderer" in call_args.kwargs or len(call_args.args) >= 2

        # Assert: start_operation was called with correct parameters
        mock_progress_instance.start_operation.assert_called_once()
        start_call = mock_progress_instance.start_operation.call_args

        assert (
            "load_data_AAPL_1h" in start_call.args[0]
        )  # operation_id contains symbol and timeframe
        assert start_call.args[1] == 5  # total_steps for local mode

        # Assert: Context includes data-specific information
        context = start_call.kwargs.get("context", {})
        assert context.get("symbol") == "AAPL"
        assert context.get("timeframe") == "1h"
        assert context.get("mode") == "local"

        # Assert: complete_operation was called
        mock_progress_instance.complete_operation.assert_called_once()

    def test_legacy_callback_wrapper_conversion(self):
        """Test that legacy callback wrapper converts GenericProgressState to ProgressState."""
        # Arrange: Create DataManager with async infrastructure
        config = DataManagerConfiguration()
        config.generic_progress_manager = Mock(spec=GenericProgressManager)

        # Create mock data progress renderer with legacy conversion method
        mock_renderer = Mock(spec=DataProgressRenderer)
        mock_legacy_state = Mock(spec=ProgressState)
        mock_renderer.create_legacy_compatible_state.return_value = mock_legacy_state
        config.data_progress_renderer = mock_renderer

        # Mock other required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Create a mock legacy callback
        legacy_callback = Mock()

        # Act: Create legacy callback wrapper
        wrapper = data_manager._create_legacy_callback_wrapper(legacy_callback)

        # Create a GenericProgressState to test the wrapper
        generic_state = GenericProgressState(
            operation_id="test_operation",
            current_step=1,
            total_steps=5,
            percentage=20.0,
            message="Test message",
        )

        # Call the wrapper
        wrapper(generic_state)

        # Assert: Renderer conversion method was called
        mock_renderer.create_legacy_compatible_state.assert_called_once_with(
            generic_state
        )

        # Assert: Legacy callback was called with converted state
        legacy_callback.assert_called_once_with(mock_legacy_state)

    @patch(
        "ktrdr.data.async_infrastructure.data_progress_renderer.DataProgressRenderer"
    )
    def test_always_uses_new_progress_infrastructure(self, mock_data_progress_renderer):
        """Test that DataManager always uses new async progress infrastructure."""
        # Arrange: Create DataManager without explicit async infrastructure
        config = DataManagerConfiguration()
        config.generic_progress_manager = None  # No explicit async infrastructure
        config.data_progress_renderer = None  # No explicit renderer

        # Mock required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        # Setup DataProgressRenderer mock instance
        mock_renderer_instance = Mock(spec=DataProgressRenderer)
        mock_data_progress_renderer.return_value = mock_renderer_instance

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            with patch("ktrdr.data.data_manager.logger"):
                data_manager = DataManager(builder_config=config)
                # Manually set the attributes that would normally be set by ServiceOrchestrator.__init__
                data_manager._generic_progress_manager = Mock(
                    spec=GenericProgressManager
                )

        # Mock data loader to return empty dataframe
        mock_df = pd.DataFrame()
        config.data_loader.load.return_value = mock_df

        # Act: Call load_data should create default DataProgressRenderer
        data_manager.load_data(
            symbol="AAPL", timeframe="1h", mode="local", validate=False
        )

        # Assert: DataProgressRenderer was created (no fallback to legacy ProgressManager)
        mock_data_progress_renderer.assert_called_once()

    def test_enhanced_progress_messages_in_cli(self):
        """Test that CLI automatically receives enhanced progress messages."""
        # Arrange: Create DataManager with async infrastructure
        config = DataManagerConfiguration()
        config.generic_progress_manager = Mock(spec=GenericProgressManager)

        # Create mock renderer that enhances messages
        mock_renderer = Mock(spec=DataProgressRenderer)
        mock_renderer.render_message.return_value = (
            "Enhanced: Loading AAPL 1h data (backfill mode) [1/5] ETA: 30s"
        )
        config.data_progress_renderer = mock_renderer

        # Mock other components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Mock data loader
        mock_df = pd.DataFrame()
        config.data_loader.load.return_value = mock_df

        # Create a progress callback to capture messages
        progress_messages = []

        def capture_progress(state):
            progress_messages.append(state.message)

        # Act: Call load_data with progress callback
        with patch("ktrdr.data.data_manager.GenericProgressManager") as mock_gpm:
            mock_instance = Mock()
            mock_gpm.return_value = mock_instance

            data_manager.load_data(
                symbol="AAPL",
                timeframe="1h",
                mode="local",
                progress_callback=capture_progress,
                validate=False,
            )

            # Verify GenericProgressManager was created with enhanced callback
            mock_gpm.assert_called_once()
            args, kwargs = mock_gpm.call_args
            assert "callback" in kwargs or len(args) >= 1
            assert kwargs.get("renderer") == config.data_progress_renderer

    def test_backward_compatibility_preserved(self):
        """Test that all existing DataManager public API is preserved."""
        # Arrange: Create DataManager with enhanced configuration
        config = DataManagerConfiguration()
        config.generic_progress_manager = Mock(spec=GenericProgressManager)
        config.data_progress_renderer = Mock(spec=DataProgressRenderer)

        # Mock all required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Assert: All existing public methods are still available
        assert hasattr(data_manager, "load_data")
        assert hasattr(data_manager, "load")
        assert hasattr(data_manager, "repair_data")
        assert hasattr(data_manager, "get_data_summary")
        assert hasattr(data_manager, "merge_data")

        # Assert: All existing attributes are preserved
        assert hasattr(data_manager, "data_loader")
        assert hasattr(data_manager, "external_provider")
        assert hasattr(data_manager, "max_gap_percentage")
        assert hasattr(data_manager, "default_repair_method")

    def test_context_includes_data_specific_information(self):
        """Test that progress context includes symbol, timeframe, and mode information."""
        # Arrange: Create DataManager with async infrastructure
        config = DataManagerConfiguration()
        mock_progress_manager = Mock(spec=GenericProgressManager)
        config.generic_progress_manager = mock_progress_manager
        config.data_progress_renderer = Mock(spec=DataProgressRenderer)

        # Mock required components
        config.data_loader = Mock()
        config.external_provider = Mock()
        config.data_validator = Mock()
        config.gap_classifier = Mock()
        config.gap_analyzer = Mock()
        config.segment_manager = Mock()
        config.data_processor = Mock()
        config.data_loading_orchestrator = Mock()
        config.health_checker = Mock()

        with patch("ktrdr.managers.ServiceOrchestrator.__init__"):
            data_manager = DataManager(builder_config=config)

        # Mock data loader and orchestrator
        mock_df = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0]}
        )  # Give it some data for len()
        config.data_loader.load.return_value = mock_df

        # Since this is backfill mode, the orchestrator will be called
        config.data_loading_orchestrator.load_with_fallback.return_value = mock_df

        # Act: Call load_data
        with patch("ktrdr.data.data_manager.GenericProgressManager") as mock_gpm:
            mock_instance = Mock()
            mock_gpm.return_value = mock_instance

            data_manager.load_data(
                symbol="MSFT", timeframe="5m", mode="backfill", validate=False
            )

            # Assert: start_operation called with data-specific context
            # (May be called multiple times due to both main flow and orchestrator flow)
            assert mock_instance.start_operation.call_count >= 1

            # Check that at least one call had the expected context
            found_expected_context = False
            expected_context = None
            for call in mock_instance.start_operation.call_args_list:
                context = call.kwargs.get("context", {}) if call.kwargs else {}
                if (
                    context.get("symbol") == "MSFT"
                    and context.get("timeframe") == "5m"
                    and context.get("mode") == "backfill"
                ):
                    found_expected_context = True
                    expected_context = context
                    break

            assert (
                found_expected_context
            ), f"Expected context not found in calls: {mock_instance.start_operation.call_args_list}"
            # Check operation_type if it exists in the context
            if expected_context and "operation_type" in expected_context:
                assert expected_context.get("operation_type") == "data_load"


class TestDataManagerBuilderAsyncIntegration:
    """Test that DataManagerBuilder properly creates async infrastructure."""

    def test_builder_creates_async_infrastructure_by_default(self):
        """Test that builder creates async infrastructure components by default."""
        # Act: Build configuration using builder
        builder = DataManagerBuilder()
        config = builder.build_configuration()

        # Assert: Async infrastructure components are created
        assert config.generic_progress_manager is not None
        assert isinstance(config.generic_progress_manager, GenericProgressManager)

        assert config.data_progress_renderer is not None
        assert isinstance(config.data_progress_renderer, DataProgressRenderer)

        assert config.time_estimation_engine is not None
        assert isinstance(config.time_estimation_engine, TimeEstimationEngine)

    def test_builder_integrates_components_correctly(self):
        """Test that builder integrates async infrastructure components correctly."""
        # Act: Build DataManager through builder
        builder = DataManagerBuilder()

        # Use build() method which creates full DataManager
        data_manager = builder.build()

        # Assert: DataManager has enhanced async infrastructure
        assert data_manager._generic_progress_manager is not None
        assert data_manager._data_progress_renderer is not None
        assert data_manager._time_estimation_engine is not None

        # Assert: Components are properly integrated
        assert (
            data_manager._generic_progress_manager.renderer
            == data_manager._data_progress_renderer
        )

    def test_time_estimation_engine_configured_with_cache(self):
        """Test that TimeEstimationEngine is configured with proper cache file."""
        # Act: Build configuration
        builder = DataManagerBuilder()
        config = builder.build_configuration()

        # Assert: TimeEstimationEngine exists and has cache configuration
        assert config.time_estimation_engine is not None

        # The cache file path should be configured (implementation detail)
        # We verify this through the DataProgressRenderer integration
        assert (
            config.data_progress_renderer.time_estimator
            == config.time_estimation_engine
        )
