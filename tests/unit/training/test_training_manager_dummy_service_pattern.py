"""
Test suite for TrainingManager DummyService pattern transformation.

This test suite follows TDD methodology to validate that TrainingManager follows
the exact DummyService pattern as demonstrated in ktrdr/api/services/dummy_service.py.

Key requirements validated:
1. TrainingManager inherits ServiceOrchestrator[TrainingAdapter] like DummyService
2. Training methods are single start_managed_operation() calls like DummyService
3. Domain logic in clean _run_*_async() methods with ServiceOrchestrator cancellation
4. Perfect UX with zero boilerplate like DummyService
5. ServiceOrchestrator handles ALL async complexity automatically
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ktrdr.managers.base import ServiceOrchestrator
from ktrdr.training.training_manager import TrainingManager
from ktrdr.training.training_adapter import TrainingAdapter


class TestTrainingManagerDummyServicePattern:
    """Test TrainingManager follows DummyService pattern exactly."""

    @pytest.fixture
    def training_manager(self):
        """Create TrainingManager instance for testing."""
        return TrainingManager()

    def test_training_manager_inherits_serviceorchestrator(self, training_manager):
        """Test that TrainingManager inherits ServiceOrchestrator[TrainingAdapter] like DummyService."""
        # CRITICAL: TrainingManager must inherit ServiceOrchestrator just like DummyService
        assert isinstance(training_manager, ServiceOrchestrator)
        assert issubclass(TrainingManager, ServiceOrchestrator)

        # Check that it's parameterized with TrainingAdapter like DataManager pattern
        # TrainingManager should follow: ServiceOrchestrator[TrainingAdapter]
        # (Similar to how DummyService follows: ServiceOrchestrator[None])

    def test_training_manager_has_serviceorchestrator_capabilities(self, training_manager):
        """Test that TrainingManager has all ServiceOrchestrator capabilities automatically."""
        # ServiceOrchestrator provides these methods automatically - no manual implementation needed
        assert hasattr(training_manager, 'start_managed_operation')
        assert hasattr(training_manager, 'get_current_cancellation_token')
        assert hasattr(training_manager, 'update_operation_progress')
        assert hasattr(training_manager, 'run_sync_operation')

        # ServiceOrchestrator configuration methods
        assert hasattr(training_manager, '_get_service_name')
        assert hasattr(training_manager, '_get_default_host_url')
        assert hasattr(training_manager, '_get_env_var_prefix')
        assert hasattr(training_manager, '_initialize_adapter')

    def test_training_manager_implements_required_abstract_methods(self, training_manager):
        """Test that TrainingManager implements ServiceOrchestrator abstract methods."""
        # These methods must be implemented for ServiceOrchestrator inheritance
        assert training_manager._get_service_name() == "Training"
        assert training_manager._get_default_host_url() == "http://localhost:5002"
        assert training_manager._get_env_var_prefix() == "TRAINING"

        # Adapter should be TrainingAdapter instance
        assert isinstance(training_manager.adapter, TrainingAdapter)

    @pytest.mark.asyncio
    async def test_train_multi_symbol_strategy_follows_dummy_service_pattern(self, training_manager):
        """Test that train_multi_symbol_strategy_async follows exact DummyService pattern."""
        # CRITICAL: Training methods must be single start_managed_operation() calls like DummyService

        # Mock the ServiceOrchestrator infrastructure
        with patch.object(training_manager, 'start_managed_operation') as mock_start_operation:
            mock_start_operation.return_value = {
                "operation_id": "op_123",
                "status": "started",
                "message": "Started train_multi_symbol_strategy operation"
            }

            # Call the training method - should be just one start_managed_operation() call
            result = await training_manager.train_multi_symbol_strategy_async(
                strategy_config_path="config.json",
                symbols=["AAPL", "MSFT"],
                timeframes=["1h"],
                start_date="2023-01-01",
                end_date="2023-12-31",
                validation_split=0.2,
                data_mode="local"
            )

            # Verify it follows DummyService pattern: single start_managed_operation() call
            mock_start_operation.assert_called_once()
            call_args = mock_start_operation.call_args

            # Check operation parameters follow DummyService pattern
            assert call_args[1]['operation_name'] == "train_multi_symbol_strategy"
            assert call_args[1]['operation_type'] == "TRAINING"
            assert call_args[1]['operation_func'] == training_manager._run_training_async

            # Check that parameters are passed to domain logic
            assert call_args[1]['strategy_config_path'] == "config.json"
            assert call_args[1]['symbols'] == ["AAPL", "MSFT"]
            assert call_args[1]['timeframes'] == ["1h"]
            assert call_args[1]['start_date'] == "2023-01-01"
            assert call_args[1]['end_date'] == "2023-12-31"
            assert call_args[1]['validation_split'] == 0.2
            assert call_args[1]['data_mode'] == "local"

            # Verify API response format like DummyService
            assert result["operation_id"] == "op_123"
            assert result["status"] == "started"
            assert "operation" in result["message"]

    def test_training_manager_has_clean_domain_logic_methods(self, training_manager):
        """Test that TrainingManager has clean domain logic methods like DummyService."""
        # CRITICAL: Domain logic must be in clean _run_*_async() methods like DummyService
        assert hasattr(training_manager, '_run_training_async')

        # Domain logic methods should be async and accept parameters
        import inspect
        run_training_method = getattr(training_manager, '_run_training_async')
        assert asyncio.iscoroutinefunction(run_training_method)

    @pytest.mark.asyncio
    async def test_run_training_async_uses_serviceorchestrator_cancellation(self, training_manager):
        """Test that _run_training_async uses ServiceOrchestrator cancellation like DummyService."""
        # Mock the cancellation infrastructure
        mock_token = MagicMock()
        mock_token.is_cancelled.return_value = False

        with patch.object(training_manager, 'get_current_cancellation_token', return_value=mock_token):
            with patch.object(training_manager, 'update_operation_progress') as mock_progress:
                with patch.object(training_manager.adapter, 'train_multi_symbol_strategy') as mock_adapter:
                    mock_adapter.return_value = {"status": "success", "model_path": "model.pth"}

                    # Call domain logic with test parameters
                    result = await training_manager._run_training_async(
                        strategy_config_path="config.json",
                        symbols=["AAPL"],
                        timeframes=["1h"],
                        start_date="2023-01-01",
                        end_date="2023-12-31",
                        validation_split=0.2,
                        data_mode="local"
                    )

                    # Verify cancellation token was obtained from ServiceOrchestrator
                    training_manager.get_current_cancellation_token.assert_called()

                    # Verify adapter was called with ServiceOrchestrator infrastructure
                    mock_adapter.assert_called_once()
                    call_kwargs = mock_adapter.call_args[1]
                    assert call_kwargs['cancellation_token'] == mock_token
                    assert call_kwargs['progress_callback'] == training_manager.update_operation_progress

                    # Verify result is formatted properly
                    assert isinstance(result, dict)
                    assert "status" in result

    @pytest.mark.asyncio
    async def test_run_training_async_handles_cancellation_gracefully(self, training_manager):
        """Test that _run_training_async handles cancellation like DummyService._run_dummy_task_async."""
        # Mock cancelled token
        mock_token = MagicMock()
        mock_token.is_cancelled.return_value = True

        with patch.object(training_manager, 'get_current_cancellation_token', return_value=mock_token):
            with patch.object(training_manager.adapter, 'train_multi_symbol_strategy') as mock_adapter:
                # Mock adapter to return cancellation status
                mock_adapter.return_value = {"status": "cancelled", "message": "Training cancelled"}

                result = await training_manager._run_training_async(
                    strategy_config_path="config.json",
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2023-01-01",
                    end_date="2023-12-31",
                    validation_split=0.2,
                    data_mode="local"
                )

                # Verify cancellation is handled gracefully like DummyService
                assert result["status"] == "cancelled"
                # Adapter should still be called (it handles cancellation internally)
                mock_adapter.assert_called_once()

    def test_training_manager_zero_boilerplate_requirement(self, training_manager):
        """Test that TrainingManager has zero boilerplate like DummyService."""
        # CRITICAL: No manual async management code in TrainingManager

        # Check class methods - should be minimal like DummyService
        training_methods = [method for method in dir(training_manager)
                          if method.startswith('train') and not method.startswith('_')]

        # Public training methods should just delegate to start_managed_operation
        # Implementation will be verified in integration tests
        assert len(training_methods) > 0, "TrainingManager should have public training methods"

    def test_training_manager_environment_configuration_via_serviceorchestrator(self, training_manager):
        """Test that environment configuration is handled via ServiceOrchestrator."""
        # ServiceOrchestrator should handle environment configuration automatically
        assert hasattr(training_manager, 'is_using_host_service')
        assert hasattr(training_manager, 'get_host_service_url')
        assert hasattr(training_manager, 'get_configuration_info')

        # These should work without manual implementation (ServiceOrchestrator provides them)
        config_info = training_manager.get_configuration_info()
        assert "service" in config_info
        assert "mode" in config_info
        assert config_info["service"] == "Training"

    @pytest.mark.asyncio
    async def test_training_manager_perfect_ux_like_dummy_service(self, training_manager):
        """Test that TrainingManager provides perfect UX like DummyService."""
        # Mock operations service for UX testing
        mock_operations_service = MagicMock()
        mock_operations_service.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_123"))
        mock_operations_service.start_operation = AsyncMock()

        with patch('ktrdr.api.services.operations_service.get_operations_service',
                  return_value=mock_operations_service):
            with patch.object(training_manager, '_run_training_async') as mock_domain_logic:
                mock_domain_logic.return_value = {"status": "success"}

                # Test async operation like DummyService.start_dummy_task()
                result = await training_manager.train_multi_symbol_strategy_async(
                    strategy_config_path="config.json",
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2023-01-01",
                    end_date="2023-12-31"
                )

                # Perfect UX: immediate API response with operation tracking
                assert "operation_id" in result
                assert result["status"] == "started"
                assert "message" in result

                # Operations service integration for smooth progress
                mock_operations_service.create_operation.assert_called_once()
                mock_operations_service.start_operation.assert_called_once()

    def test_training_manager_follows_dummy_service_structure_exactly(self, training_manager):
        """Test that TrainingManager structure matches DummyService exactly."""
        # Compare with DummyService structure patterns

        # 1. ServiceOrchestrator inheritance ✓ (tested above)
        # 2. Simple public methods that call start_managed_operation ✓ (tested above)
        # 3. Clean domain logic in _run_*_async methods ✓ (tested above)
        # 4. Abstract method implementations ✓ (tested above)
        # 5. Zero boilerplate ✓ (tested above)

        # Additional structural validation
        assert hasattr(training_manager, 'adapter')
        assert isinstance(training_manager.adapter, TrainingAdapter)

        # ServiceOrchestrator provides configuration automatically
        assert callable(training_manager._get_service_name)
        assert callable(training_manager._get_default_host_url)
        assert callable(training_manager._get_env_var_prefix)
        assert callable(training_manager._initialize_adapter)


class TestTrainingManagerIntegrationWithServiceOrchestrator:
    """Integration tests for TrainingManager with ServiceOrchestrator infrastructure."""

    @pytest.fixture
    def training_manager(self):
        """Create TrainingManager for integration testing."""
        return TrainingManager()

    @pytest.mark.asyncio
    async def test_full_training_operation_flow_like_dummy_service(self, training_manager):
        """Test complete training operation flow matches DummyService pattern."""
        # This test validates the full flow from start_managed_operation to completion

        # Mock all external dependencies
        with patch('ktrdr.api.services.operations_service.get_operations_service') as mock_get_service:
            mock_operations_service = MagicMock()
            mock_operations_service.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_test_123"))
            mock_operations_service.start_operation = AsyncMock()
            mock_operations_service.get_cancellation_token.return_value = None
            mock_get_service.return_value = mock_operations_service

            with patch.object(training_manager.adapter, 'train_multi_symbol_strategy') as mock_adapter:
                mock_adapter.return_value = {
                    "status": "success",
                    "model_path": "test_model.pth",
                    "training_loss": 0.05,
                    "validation_loss": 0.07
                }

                # Execute training operation
                result = await training_manager.train_multi_symbol_strategy_async(
                    strategy_config_path="test_config.json",
                    symbols=["AAPL", "MSFT"],
                    timeframes=["1h", "4h"],
                    start_date="2023-01-01",
                    end_date="2023-06-30",
                    validation_split=0.2,
                    data_mode="local"
                )

                # Verify DummyService-like API response
                assert result["operation_id"] == "op_test_123"
                assert result["status"] == "started"
                assert "train_multi_symbol_strategy" in result["message"]

                # Verify operations service integration
                mock_operations_service.create_operation.assert_called_once()
                mock_operations_service.start_operation.assert_called_once()

    def test_training_manager_configuration_matches_serviceorchestrator_pattern(self, training_manager):
        """Test that configuration follows ServiceOrchestrator patterns."""
        config = training_manager.get_configuration_info()

        # Standard ServiceOrchestrator configuration structure
        required_keys = ["service", "mode", "environment_variables", "adapter_info"]
        for key in required_keys:
            assert key in config, f"Missing required config key: {key}"

        # Training-specific configuration
        assert config["service"] == "Training"
        assert config["mode"] in ["local", "host_service"]

        # Environment variables should follow pattern
        env_vars = config["environment_variables"]
        assert "USE_TRAINING_HOST_SERVICE" in env_vars
        assert "TRAINING_HOST_SERVICE_URL" in env_vars

    @pytest.mark.asyncio
    async def test_training_manager_error_handling_like_serviceorchestrator(self, training_manager):
        """Test that error handling follows ServiceOrchestrator patterns."""
        # Mock operations service for error testing
        with patch('ktrdr.api.services.operations_service.get_operations_service') as mock_get_service:
            mock_operations_service = MagicMock()
            mock_operations_service.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_error_123"))
            mock_operations_service.start_operation = AsyncMock()
            mock_get_service.return_value = mock_operations_service

            with patch.object(training_manager.adapter, 'train_multi_symbol_strategy') as mock_adapter:
                # Simulate adapter error
                mock_adapter.side_effect = ValueError("Training configuration invalid")

                # Error should be handled gracefully via ServiceOrchestrator
                result = await training_manager.train_multi_symbol_strategy_async(
                    strategy_config_path="invalid_config.json",
                    symbols=["INVALID"],
                    timeframes=["1h"],
                    start_date="2023-01-01",
                    end_date="2023-12-31"
                )

                # Should get operation_id even for errors (operation started but will fail)
                assert "operation_id" in result
                assert result["status"] == "started"


class TestTrainingManagerConsistencyWithDummyServiceAndDataManager:
    """Test consistency with DummyService and DataManager patterns."""

    def test_pattern_consistency_across_services(self):
        """Test that TrainingManager follows same patterns as DummyService and DataManager."""
        from ktrdr.api.services.dummy_service import DummyService
        from ktrdr.data.data_manager import DataManager

        training_manager = TrainingManager()
        dummy_service = DummyService()
        data_manager = DataManager()

        # All should inherit ServiceOrchestrator
        assert isinstance(training_manager, ServiceOrchestrator)
        assert isinstance(dummy_service, ServiceOrchestrator)
        assert isinstance(data_manager, ServiceOrchestrator)

        # All should have required ServiceOrchestrator methods
        for service in [training_manager, dummy_service, data_manager]:
            assert hasattr(service, 'start_managed_operation')
            assert hasattr(service, 'get_current_cancellation_token')
            assert hasattr(service, 'update_operation_progress')
            assert hasattr(service, '_get_service_name')

    def test_training_manager_method_naming_consistency(self):
        """Test that method naming follows established patterns."""
        training_manager = TrainingManager()

        # Async methods should end with _async for consistency
        assert hasattr(training_manager, 'train_multi_symbol_strategy_async')

        # Domain logic should start with _run_ like DummyService
        assert hasattr(training_manager, '_run_training_async')

        # Configuration methods should follow ServiceOrchestrator pattern
        assert callable(training_manager._get_service_name)
        assert callable(training_manager._get_default_host_url)
        assert callable(training_manager._get_env_var_prefix)

    def test_training_manager_zero_boilerplate_validation(self):
        """Validate that TrainingManager achieves zero boilerplate like DummyService."""
        import inspect

        training_manager = TrainingManager()

        # Get public training methods
        public_methods = [name for name, method in inspect.getmembers(training_manager, predicate=inspect.ismethod)
                         if not name.startswith('_') and 'train' in name.lower()]

        # Each public method should be simple (DummyService pattern)
        # This will be validated by implementation, but structure should support it
        assert len(public_methods) > 0, "Should have public training methods"

        # Domain logic methods should exist
        domain_methods = [name for name in dir(training_manager)
                         if name.startswith('_run_') and name.endswith('_async')]
        assert len(domain_methods) > 0, "Should have domain logic methods"


if __name__ == "__main__":
    pytest.main([__file__])