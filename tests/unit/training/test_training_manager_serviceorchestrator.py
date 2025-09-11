"""
Unit tests for TrainingManager ServiceOrchestrator integration.

This module tests the SLICE-3 Task 3.1 implementation where TrainingManager inherits
from ServiceOrchestrator[TrainingAdapter] to provide structured progress and
cancellation support like DataManager.

Tests are written first (TDD) to ensure proper ServiceOrchestrator integration.
"""

import os
from unittest.mock import Mock, patch

import pytest

from ktrdr.managers.base import ServiceOrchestrator
from ktrdr.training.training_adapter import TrainingAdapter
from ktrdr.training.training_manager import TrainingManager


class TestTrainingManagerServiceOrchestrator:
    """Test TrainingManager ServiceOrchestrator inheritance and patterns."""

    def test_training_manager_inherits_serviceorchestrator(self):
        """TrainingManager should inherit from ServiceOrchestrator[TrainingAdapter]."""
        # This test will fail initially - that's the point of TDD
        training_manager = TrainingManager()

        # Test inheritance
        assert isinstance(training_manager, ServiceOrchestrator)

        # Test generic type (adapter should be TrainingAdapter)
        assert isinstance(training_manager.adapter, TrainingAdapter)

    def test_training_manager_implements_abstract_methods(self):
        """TrainingManager should implement all ServiceOrchestrator abstract methods."""
        training_manager = TrainingManager()

        # Test abstract method implementations exist
        assert hasattr(training_manager, "_initialize_adapter")
        assert hasattr(training_manager, "_get_service_name")
        assert hasattr(training_manager, "_get_default_host_url")
        assert hasattr(training_manager, "_get_env_var_prefix")

        # Test they return appropriate values
        service_name = training_manager._get_service_name()
        assert service_name == "Training"

        default_url = training_manager._get_default_host_url()
        assert default_url == "http://localhost:5002"

        env_prefix = training_manager._get_env_var_prefix()
        assert env_prefix == "TRAINING"

    @patch.dict(os.environ, {"USE_TRAINING_HOST_SERVICE": "false"}, clear=False)
    def test_initialize_adapter_local_mode(self):
        """_initialize_adapter should create local mode adapter based on environment."""
        training_manager = TrainingManager()
        adapter = training_manager.adapter

        assert isinstance(adapter, TrainingAdapter)
        assert adapter.use_host_service is False
        assert adapter.host_service_url == "http://localhost:5002"  # default

    @patch.dict(
        os.environ,
        {
            "USE_TRAINING_HOST_SERVICE": "true",
            "TRAINING_HOST_SERVICE_URL": "http://localhost:8002",
        },
        clear=False,
    )
    def test_initialize_adapter_host_service_mode(self):
        """_initialize_adapter should create host service adapter when enabled."""
        training_manager = TrainingManager()
        adapter = training_manager.adapter

        assert isinstance(adapter, TrainingAdapter)
        assert adapter.use_host_service is True
        assert adapter.host_service_url == "http://localhost:8002"

    def test_serviceorchestrator_capabilities_available(self):
        """TrainingManager should inherit ServiceOrchestrator capabilities."""
        training_manager = TrainingManager()

        # Test ServiceOrchestrator methods are available
        assert hasattr(training_manager, "execute_with_progress")
        assert hasattr(training_manager, "execute_with_cancellation")
        assert hasattr(training_manager, "get_current_cancellation_token")
        assert hasattr(training_manager, "get_configuration_info")
        assert hasattr(training_manager, "get_adapter_statistics")
        assert hasattr(training_manager, "is_using_host_service")

    def test_configuration_info_includes_training_details(self):
        """get_configuration_info should include training-specific information."""
        training_manager = TrainingManager()
        config = training_manager.get_configuration_info()

        # Test structure matches ServiceOrchestrator pattern
        assert config["service"] == "Training"
        assert "mode" in config
        assert "host_service_url" in config
        assert "environment_variables" in config
        assert "USE_TRAINING_HOST_SERVICE" in config["environment_variables"]
        assert "TRAINING_HOST_SERVICE_URL" in config["environment_variables"]

    def test_preserves_existing_training_manager_interface(self):
        """All existing TrainingManager methods should still work."""
        training_manager = TrainingManager()

        # Test existing methods are preserved
        assert hasattr(training_manager, "train_multi_symbol_strategy")
        assert hasattr(training_manager, "get_training_status")
        assert hasattr(training_manager, "stop_training")
        assert hasattr(training_manager, "get_adapter_statistics")
        assert hasattr(training_manager, "is_using_host_service")
        assert hasattr(training_manager, "get_host_service_url")
        assert hasattr(training_manager, "get_configuration_info")

    @pytest.mark.asyncio
    async def test_train_multi_symbol_strategy_passes_cancellation_token(self):
        """train_multi_symbol_strategy should pass cancellation token to adapter."""
        from unittest.mock import AsyncMock

        with patch("ktrdr.training.training_manager.TrainingAdapter") as MockAdapter:
            mock_adapter = Mock(spec=TrainingAdapter)
            mock_adapter.train_multi_symbol_strategy = AsyncMock(
                return_value={"success": True}
            )
            MockAdapter.return_value = mock_adapter

            training_manager = TrainingManager()

            # Mock ServiceOrchestrator to provide cancellation token
            mock_token = Mock()
            training_manager._current_cancellation_token = mock_token

            # Call with typical parameters
            result = await training_manager.train_multi_symbol_strategy(
                strategy_config_path="/path/to/config",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

            # Verify result was returned
            assert result == {"success": True}

            # Verify cancellation token was passed to adapter
            mock_adapter.train_multi_symbol_strategy.assert_called_once()
            call_kwargs = mock_adapter.train_multi_symbol_strategy.call_args[1]
            assert "cancellation_token" in call_kwargs
            assert call_kwargs["cancellation_token"] == mock_token

    @pytest.mark.asyncio
    async def test_training_operations_use_serviceorchestrator_patterns(self):
        """Training operations should use ServiceOrchestrator execution patterns."""
        from unittest.mock import AsyncMock

        with patch("ktrdr.training.training_manager.TrainingAdapter") as MockAdapter:
            mock_adapter = Mock(spec=TrainingAdapter)
            mock_adapter.train_multi_symbol_strategy = AsyncMock(
                return_value={"success": True}
            )
            MockAdapter.return_value = mock_adapter

            training_manager = TrainingManager()

            # Call train_multi_symbol_strategy to test direct ServiceOrchestrator integration
            result = await training_manager.train_multi_symbol_strategy(
                strategy_config_path="/path/to/config",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

            # Verify result was returned and ServiceOrchestrator methods available
            assert result == {"success": True}
            assert hasattr(training_manager, "execute_with_cancellation")
            assert hasattr(training_manager, "get_current_cancellation_token")

    def test_training_manager_follows_datamanager_pattern(self):
        """TrainingManager should follow the exact same pattern as DataManager."""

        training_manager = TrainingManager()

        # Both should inherit from ServiceOrchestrator
        assert isinstance(training_manager, ServiceOrchestrator)

        # Both should have the same base capabilities
        training_attrs = set(dir(training_manager))

        # Test key ServiceOrchestrator methods are present (like DataManager has)
        expected_methods = {
            "execute_with_progress",
            "execute_with_cancellation",
            "get_current_cancellation_token",
            "get_configuration_info",
            "get_adapter_statistics",
            "is_using_host_service",
        }

        assert expected_methods.issubset(training_attrs)

    @pytest.mark.asyncio
    async def test_health_check_includes_adapter_health(self):
        """health_check should include adapter health like DataManager does."""
        from unittest.mock import AsyncMock

        training_manager = TrainingManager()

        # Mock adapter health check method
        training_manager.adapter.health_check = AsyncMock(
            return_value={"status": "healthy"}
        )

        health_info = await training_manager.health_check()

        assert "orchestrator" in health_info
        assert "service" in health_info
        assert health_info["service"] == "Training"

    def test_environment_variable_handling_matches_datamanager(self):
        """Environment variable handling should match DataManager pattern."""
        # Test default (no env vars)
        with patch.dict(os.environ, {}, clear=True):
            training_manager = TrainingManager()
            assert training_manager.adapter.use_host_service is False

        # Test enabled
        with patch.dict(os.environ, {"USE_TRAINING_HOST_SERVICE": "true"}, clear=False):
            training_manager = TrainingManager()
            assert training_manager.adapter.use_host_service is True

        # Test disabled explicitly
        with patch.dict(
            os.environ, {"USE_TRAINING_HOST_SERVICE": "false"}, clear=False
        ):
            training_manager = TrainingManager()
            assert training_manager.adapter.use_host_service is False

    def test_adapter_statistics_integration(self):
        """get_adapter_statistics should integrate with ServiceOrchestrator pattern."""
        training_manager = TrainingManager()
        stats = training_manager.get_adapter_statistics()

        # Should return adapter statistics
        assert isinstance(stats, dict)
        # TrainingAdapter provides these statistics
        expected_keys = {"requests_made", "errors_encountered", "error_rate", "mode"}
        assert expected_keys.issubset(set(stats.keys()))


class TestTrainingManagerCancellationIntegration:
    """Test cancellation token integration in TrainingManager operations."""

    @pytest.mark.asyncio
    async def test_cancellation_token_passed_to_adapter_methods(self):
        """All training operations should pass cancellation tokens to adapter."""
        from unittest.mock import AsyncMock

        with patch("ktrdr.training.training_manager.TrainingAdapter") as MockAdapter:
            mock_adapter = Mock(spec=TrainingAdapter)
            mock_adapter.train_multi_symbol_strategy = AsyncMock(
                return_value={"success": True}
            )
            mock_adapter.get_training_status = AsyncMock(
                return_value={"status": "running"}
            )
            mock_adapter.stop_training = AsyncMock(return_value={"stopped": True})
            MockAdapter.return_value = mock_adapter

            training_manager = TrainingManager()
            mock_token = Mock()
            training_manager._current_cancellation_token = mock_token

            # Test train_multi_symbol_strategy
            await training_manager.train_multi_symbol_strategy(
                strategy_config_path="/path",
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )

            # Verify cancellation token passed
            call_kwargs = mock_adapter.train_multi_symbol_strategy.call_args[1]
            assert "cancellation_token" in call_kwargs

    def test_cancellation_token_protocol_compliance(self):
        """TrainingManager should use unified CancellationToken protocol."""
        training_manager = TrainingManager()

        # Test that get_current_cancellation_token follows protocol
        token = training_manager.get_current_cancellation_token()
        # Should be None initially or implement CancellationToken protocol
        if token is not None:
            assert hasattr(token, "is_cancelled")

    @pytest.mark.asyncio
    async def test_execute_with_cancellation_integration(self):
        """TrainingManager should properly integrate with execute_with_cancellation."""
        training_manager = TrainingManager()

        # Test that execute_with_cancellation is available and works
        async def test_operation():
            return {"test": "result"}

        result = await training_manager.execute_with_cancellation(
            test_operation(), operation_name="test_operation"
        )

        assert result == {"test": "result"}


class TestTrainingManagerBackwardCompatibility:
    """Test that TrainingManager changes don't break existing functionality."""

    def test_existing_interface_preserved(self):
        """All existing TrainingManager methods should work exactly as before."""
        training_manager = TrainingManager()

        # Test that we can still call existing methods
        assert callable(getattr(training_manager, "train_multi_symbol_strategy", None))
        assert callable(getattr(training_manager, "get_training_status", None))
        assert callable(getattr(training_manager, "stop_training", None))
        assert callable(getattr(training_manager, "get_adapter_statistics", None))

        # Test configuration methods still work
        config = training_manager.get_configuration_info()
        assert isinstance(config, dict)

        # Test adapter access still works
        adapter = training_manager.adapter
        assert isinstance(adapter, TrainingAdapter)

    @pytest.mark.asyncio
    async def test_training_operations_still_work(self):
        """Training operations should work with same signatures as before."""
        from unittest.mock import AsyncMock

        with patch("ktrdr.training.training_manager.TrainingAdapter") as MockAdapter:
            mock_adapter = Mock(spec=TrainingAdapter)
            mock_adapter.train_multi_symbol_strategy = AsyncMock(
                return_value={"success": True}
            )
            mock_adapter.get_training_status = AsyncMock(
                return_value={"status": "running"}
            )
            mock_adapter.stop_training = AsyncMock(return_value={"stopped": True})
            MockAdapter.return_value = mock_adapter

            training_manager = TrainingManager()

            # Test train_multi_symbol_strategy with original signature
            result = await training_manager.train_multi_symbol_strategy(
                strategy_config_path="/path/to/config",
                symbols=["AAPL", "MSFT"],
                timeframes=["1h", "4h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                validation_split=0.2,
                data_mode="local",
            )
            assert result == {"success": True}

            # Test get_training_status
            status = await training_manager.get_training_status("session_123")
            assert status == {"status": "running"}

            # Test stop_training
            stop_result = await training_manager.stop_training("session_123")
            assert stop_result == {"stopped": True}

    def test_construction_with_no_parameters(self):
        """TrainingManager should construct with no parameters like before."""
        # This should work exactly as it did before ServiceOrchestrator
        training_manager = TrainingManager()
        assert training_manager is not None
        assert isinstance(training_manager.adapter, TrainingAdapter)

    def test_adapter_initialization_logic_preserved(self):
        """The adapter initialization logic should be preserved from original."""
        # Test with environment variables like the original did
        with patch.dict(
            os.environ,
            {
                "USE_TRAINING_HOST_SERVICE": "true",
                "TRAINING_HOST_SERVICE_URL": "http://custom:8888",
            },
            clear=False,
        ):
            training_manager = TrainingManager()

            # Should initialize adapter with same logic as original
            assert training_manager.adapter.use_host_service is True
            assert training_manager.adapter.host_service_url == "http://custom:8888"
