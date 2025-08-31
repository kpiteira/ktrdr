"""
Test cases for ServiceOrchestrator enhancements (TASK-1.4).

This module tests the new async execution patterns, improved error handling,
and enhanced configuration management added to ServiceOrchestrator.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, Optional

import pytest

from ktrdr.managers.base import ServiceOrchestrator


class MockServiceOrchestrator(ServiceOrchestrator):
    """Mock implementation of ServiceOrchestrator for testing."""

    def __init__(self, **kwargs):
        self._service_name = kwargs.get("service_name", "TestService")
        self._default_host_url = kwargs.get("default_host_url", "http://localhost:8000")
        self._env_var_prefix = kwargs.get("env_var_prefix", "TEST")
        
        # Create a mock adapter
        self.adapter = MagicMock()
        self.adapter.use_host_service = kwargs.get("use_host_service", False)
        self.adapter.host_service_url = kwargs.get("host_service_url", None)

    def _initialize_adapter(self):
        return self.adapter

    def _get_service_name(self) -> str:
        return self._service_name

    def _get_default_host_url(self) -> str:
        return self._default_host_url

    def _get_env_var_prefix(self) -> str:
        return self._env_var_prefix


class TestAsyncExecutionPatterns:
    """Test new async execution patterns."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.mark.asyncio
    async def test_execute_with_progress_success(self, orchestrator):
        """Test execute_with_progress with successful execution."""
        # Mock progress callback
        progress_callback = MagicMock()
        
        # Mock async function
        async def mock_operation():
            await asyncio.sleep(0.01)  # Simulate work
            return "success"

        # Now should work since method exists
        result = await orchestrator.execute_with_progress(
            mock_operation(), 
            progress_callback=progress_callback,
            timeout=1.0
        )
        
        assert result == "success"
        # Should have called progress callback twice (start and end)
        assert progress_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_cancellation_success(self, orchestrator):
        """Test execute_with_cancellation with successful execution."""
        # Mock cancellation token
        cancellation_token = MagicMock()
        cancellation_token.is_cancelled_requested = False
        
        async def mock_operation():
            await asyncio.sleep(0.01)
            return "success"

        # Now should work since method exists
        result = await orchestrator.execute_with_cancellation(
            mock_operation(),
            cancellation_token=cancellation_token
        )
        
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_cancellation_cancelled(self, orchestrator):
        """Test execute_with_cancellation when operation is cancelled."""
        # Mock cancellation token that is already cancelled
        cancellation_token = MagicMock()
        cancellation_token.is_cancelled_requested = True
        
        async def mock_operation():
            await asyncio.sleep(0.1)  # This should be cancelled
            return "should not reach here"

        # Should raise CancelledError since cancellation is requested before start
        with pytest.raises(asyncio.CancelledError):
            await orchestrator.execute_with_cancellation(
                mock_operation(),
                cancellation_token=cancellation_token
            )


class TestEnhancedErrorHandling:
    """Test improved error handling integration points."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.mark.asyncio
    async def test_error_context_manager(self, orchestrator):
        """Test error context manager functionality."""
        # Test successful operation
        async with orchestrator.error_context("test_operation", symbol="AAPL"):
            # Should not raise any exceptions
            pass

    @pytest.mark.asyncio
    async def test_with_error_handling_success(self, orchestrator):
        """Test with_error_handling method with successful operation."""
        async def mock_operation():
            return "success"

        result = await orchestrator.with_error_handling(
            mock_operation(), "test_operation", symbol="AAPL"
        )
        
        assert result == "success"


class TestEnhancedHealthCheck:
    """Test standardized health check interface."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    @pytest.mark.asyncio
    async def test_standardized_health_check_format(self, orchestrator):
        """Test that health check follows standardized format."""
        health_status = await orchestrator.health_check()
        
        # Should have standardized fields
        assert "orchestrator" in health_status
        assert "service" in health_status
        assert "mode" in health_status
        assert "adapter" in health_status

    @pytest.mark.asyncio
    async def test_health_check_with_custom_checks(self, orchestrator):
        """Test enhanced health check with custom checks."""
        health_status = await orchestrator.health_check_with_custom_checks(["db_connection"])
        
        # Should have standard health check fields plus enhancements
        assert "orchestrator" in health_status
        assert "configuration" in health_status
        assert "custom_checks" in health_status
        assert "db_connection" in health_status["custom_checks"]


class TestEnhancedConfiguration:
    """Test enhanced configuration management with validation."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    def test_validate_configuration(self, orchestrator):
        """Test configuration validation functionality."""
        validation_result = orchestrator.validate_configuration()
        
        # Should have expected structure
        assert isinstance(validation_result, dict)
        assert "service" in validation_result
        assert "valid" in validation_result
        assert "issues" in validation_result
        assert "warnings" in validation_result

    def test_get_configuration_schema(self, orchestrator):
        """Test configuration schema generation."""
        schema = orchestrator.get_configuration_schema()
        
        # Should have expected structure
        assert isinstance(schema, dict)
        assert "service" in schema
        assert "environment_variables" in schema

    def test_current_configuration_info_exists(self, orchestrator):
        """Test that current configuration method exists and works."""
        config_info = orchestrator.get_configuration_info()
        
        # Should have expected structure
        assert isinstance(config_info, dict)
        assert "service" in config_info
        assert "mode" in config_info
        assert "environment_variables" in config_info
        assert "adapter_info" in config_info


class TestManagerOperationPatterns:
    """Test reusable patterns for manager operations."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    def test_operation_wrapper(self, orchestrator):
        """Test operation wrapper functionality."""
        # Test that wrapper can be created
        wrapper = orchestrator.wrap_operation("test_op")
        
        # Should return a decorator function
        assert callable(wrapper)

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self, orchestrator):
        """Test retry with backoff with successful operation."""
        async def mock_operation():
            return "success"

        result = await orchestrator.retry_with_backoff(mock_operation, max_retries=3)
        assert result == "success"


class TestBackwardCompatibility:
    """Test that existing functionality is preserved."""

    @pytest.fixture
    def orchestrator(self):
        return MockServiceOrchestrator()

    def test_existing_methods_still_work(self, orchestrator):
        """Test that all existing methods still function."""
        # Test existing methods
        assert orchestrator.is_using_host_service() == False
        assert orchestrator.get_host_service_url() is None
        
        config_info = orchestrator.get_configuration_info()
        assert isinstance(config_info, dict)
        
        # Mock the adapter to return a proper dict for get_adapter_statistics
        orchestrator.adapter.get_statistics = MagicMock(return_value={"test": "stats"})
        adapter_stats = orchestrator.get_adapter_statistics()
        assert isinstance(adapter_stats, dict)

    @pytest.mark.asyncio
    async def test_existing_health_check_still_works(self, orchestrator):
        """Test that existing health check method still works."""
        health_status = await orchestrator.health_check()
        assert isinstance(health_status, dict)
        assert "orchestrator" in health_status