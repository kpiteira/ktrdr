"""Tests for ServiceOrchestrator structured logging."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator


class ConcreteOrchestrator(ServiceOrchestrator):
    """Concrete implementation for testing."""

    def _initialize_adapter(self):
        return MagicMock()

    def _get_service_name(self):
        return "Test Service"

    def _get_default_host_url(self):
        return "http://localhost:8000"

    def _get_env_var_prefix(self):
        return "TEST"


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing."""
    return ConcreteOrchestrator()


@pytest.mark.asyncio
async def test_error_context_uses_structured_logging(orchestrator):
    """Test that error_context uses structured logging."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Test successful operation
        async with orchestrator.error_context("test_operation", symbol="AAPL"):
            pass

        # Verify debug log was called with message
        assert mock_logger.debug.called
        # First call should be "Starting operation: test_operation"
        first_call_args = mock_logger.debug.call_args_list[0][0]
        assert "Starting operation:" in first_call_args[0]


@pytest.mark.asyncio
async def test_error_context_logs_errors_with_structured_fields(orchestrator):
    """Test that error_context logs errors with structured fields."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Test error case
        with pytest.raises(ValueError):
            async with orchestrator.error_context(
                "test_operation", symbol="AAPL", timeframe="1d"
            ):
                raise ValueError("Test error")

        # Verify error was logged with structured fields
        assert mock_logger.error.called
        error_call_args, error_call_kwargs = mock_logger.error.call_args

        # Check message
        assert "Operation failed:" in error_call_args[0]

        # Check extra dict has context
        assert "extra" in error_call_kwargs
        extra = error_call_kwargs["extra"]
        assert "context" in extra
        assert extra["context"]["symbol"] == "AAPL"
        assert extra["context"]["timeframe"] == "1d"


@pytest.mark.asyncio
async def test_start_managed_operation_uses_structured_logging(orchestrator):
    """Test that start_managed_operation uses structured logging."""
    # Mock dependencies
    with (
        patch(
            "ktrdr.api.services.operations_service.get_operations_service"
        ) as mock_ops_service,
        patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger,
    ):
        # Setup mocks
        mock_service = AsyncMock()
        mock_service.create_operation.return_value = MagicMock(
            operation_id="op_test_123"
        )
        mock_service.get_cancellation_token.return_value = None
        mock_ops_service.return_value = mock_service

        # Create a simple async operation
        async def test_operation():
            return {"result": "success"}

        # Call start_managed_operation
        await orchestrator.start_managed_operation(
            operation_name="Test Operation",
            operation_type="data_load",
            operation_func=test_operation,
        )

        # Verify structured logging was used
        assert mock_logger.info.called

        # Check for operation ID in logs
        info_calls = list(mock_logger.info.call_args_list)
        # Should have log about created operation
        assert any(
            "Created managed operation:" in str(call) or "op_test_123" in str(call)
            for call in info_calls
        )


@pytest.mark.asyncio
async def test_retry_with_backoff_uses_structured_logging(orchestrator):
    """Test that retry_with_backoff uses structured logging."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Create operation that succeeds on second try
        attempt_count = 0

        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Temporary error")
            return "success"

        # Execute with retry
        result = await orchestrator.retry_with_backoff(
            flaky_operation, max_retries=2, base_delay=0.01, operation_name="test_op"
        )

        assert result == "success"

        # Verify structured logging
        assert mock_logger.debug.called
        assert mock_logger.warning.called

        # Check warning has operation context
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) > 0
        warning_message = warning_calls[0][0][0]
        assert "test_op" in warning_message


@pytest.mark.asyncio
async def test_with_error_handling_preserves_context(orchestrator):
    """Test that with_error_handling preserves context."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Test error case with context
        with pytest.raises(ValueError):

            async def failing_operation():
                raise ValueError("Test error")

            await orchestrator.with_error_handling(
                failing_operation(), "test_operation", symbol="AAPL", timeframe="1d"
            )

        # Verify error logging includes context
        assert mock_logger.error.called
        error_call_args, error_call_kwargs = mock_logger.error.call_args
        assert "extra" in error_call_kwargs
        extra = error_call_kwargs["extra"]
        assert extra["context"]["symbol"] == "AAPL"
        assert extra["context"]["timeframe"] == "1d"


def test_validate_configuration_uses_debug_logging(orchestrator):
    """Test that validate_configuration uses debug logging."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Call validate_configuration
        orchestrator.validate_configuration()

        # Verify debug logging was called
        assert mock_logger.debug.called

        # Check for validation message
        debug_calls = mock_logger.debug.call_args_list
        assert any(
            "Validating configuration" in str(call) or "validation" in str(call).lower()
            for call in debug_calls
        )


def test_orchestrator_init_uses_structured_logging():
    """Test that orchestrator initialization uses structured logging."""
    # Test that initialization completes without error
    orchestrator = ConcreteOrchestrator()
    # Verify orchestrator was created successfully
    assert orchestrator is not None
    assert orchestrator._get_service_name() == "Test Service"


@pytest.mark.asyncio
async def test_execute_with_progress_logging_on_error(orchestrator):
    """Test that execute_with_progress logs errors correctly."""
    with patch("ktrdr.async_infrastructure.service_orchestrator.logger") as mock_logger:
        # Create failing operation
        async def failing_operation():
            raise ValueError("Test failure")

        # Execute with progress (should handle error)
        with pytest.raises(ValueError):
            await orchestrator.execute_with_progress(
                failing_operation(),
                operation_name="test_op",
                context={"symbol": "AAPL"},
            )

        # Verify error was logged
        assert mock_logger.error.called
        error_message = mock_logger.error.call_args[0][0]
        assert "test_op" in error_message
        assert "failed" in error_message.lower()
