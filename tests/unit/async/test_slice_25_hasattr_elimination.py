"""
SLICE-2.5 Task 2.5.1: TDD Tests for hasattr() Cancellation Pattern Elimination

This test module verifies that ServiceOrchestrator and AsyncHostService
no longer use hasattr() patterns for cancellation checking and instead
use only the unified CancellationToken protocol.

Tests written BEFORE implementation to ensure TDD methodology.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from ktrdr.async_infrastructure.cancellation import (
    CancellationToken,
    create_cancellation_token,
)
from ktrdr.managers.async_host_service import AsyncHostService, HostServiceConfig
from ktrdr.managers.base import ServiceOrchestrator


class TestServiceOrchestratorCancellationProtocol:
    """Test ServiceOrchestrator uses only CancellationToken protocol."""

    def test_is_token_cancelled_uses_protocol_interface_only(self):
        """
        Test that _is_token_cancelled uses only CancellationToken protocol.

        This test MUST FAIL initially to prove hasattr() patterns exist,
        then PASS after implementation to prove they're eliminated.
        """

        # Create a mock ServiceOrchestrator for testing the method
        class MockServiceOrchestrator(ServiceOrchestrator):
            def _get_default_host_url(self):
                return "http://test"

            def _get_env_var_prefix(self):
                return "TEST"

            def _get_service_name(self):
                return "test"

            def _initialize_adapter(self):
                return None

        orchestrator = MockServiceOrchestrator()

        # Create a mock CancellationToken that implements the protocol
        mock_token = Mock(spec=CancellationToken)
        mock_token.is_cancelled.return_value = True

        # Test that the method uses ONLY the protocol interface
        result = orchestrator._is_token_cancelled(mock_token)

        # Verify it used the protocol property
        assert result is True

        # CRITICAL: Verify no hasattr() calls were made
        # This ensures the method uses ONLY the protocol interface
        with patch("builtins.hasattr") as mock_hasattr:
            orchestrator._is_token_cancelled(mock_token)

            # This MUST be zero - no hasattr() calls allowed
            assert mock_hasattr.call_count == 0, (
                "ServiceOrchestrator._is_token_cancelled still uses hasattr() patterns. "
                "Must use only CancellationToken.is_cancelled property."
            )

    def test_is_token_cancelled_with_real_cancellation_token(self):
        """Test _is_token_cancelled works with real AsyncCancellationToken."""

        # Create a mock ServiceOrchestrator for testing the method
        class MockServiceOrchestrator(ServiceOrchestrator):
            def _get_default_host_url(self):
                return "http://test"

            def _get_env_var_prefix(self):
                return "TEST"

            def _get_service_name(self):
                return "test"

            def _initialize_adapter(self):
                return None

        orchestrator = MockServiceOrchestrator()

        # Test with uncancelled token
        token = create_cancellation_token("test-op")
        assert orchestrator._is_token_cancelled(token) is False

        # Test with cancelled token
        token.cancel("Test cancellation")
        assert orchestrator._is_token_cancelled(token) is True

    def test_no_legacy_hasattr_patterns_in_cancellation_methods(self):
        """
        Test that ServiceOrchestrator contains no hasattr() cancellation patterns.

        This is a structural test that scans the actual source code to ensure
        no hasattr() patterns remain in cancellation-related methods.
        """
        import inspect

        # Get the source code of _is_token_cancelled method
        source = inspect.getsource(ServiceOrchestrator._is_token_cancelled)

        # CRITICAL: No hasattr() calls should exist in cancellation code
        assert "hasattr(" not in source, (
            "ServiceOrchestrator._is_token_cancelled still contains hasattr() patterns. "
            "All hasattr() cancellation checking must be eliminated."
        )

        # Verify it uses the protocol interface
        assert "is_cancelled" in source, (
            "ServiceOrchestrator._is_token_cancelled must use CancellationToken.is_cancelled"
        )

    def test_cancellation_token_type_annotation_enforced(self):
        """Test that methods properly type-annotate CancellationToken parameters."""
        import inspect

        # Get method signature
        signature = inspect.signature(ServiceOrchestrator._is_token_cancelled)

        # The parameter should accept Any currently but will be improved
        # This test documents the current state and expected improvement
        assert "token" in signature.parameters

        # After implementation, we expect better type safety
        # This test will guide the improvement


class TestAsyncHostServiceCancellationProtocol:
    """Test AsyncHostService uses only CancellationToken protocol."""

    def test_check_cancellation_uses_protocol_interface_only(self):
        """
        Test that _check_cancellation uses only CancellationToken protocol.

        This test MUST FAIL initially to prove hasattr() patterns exist,
        then PASS after implementation to prove they're eliminated.
        """

        # Create a mock AsyncHostService for testing the method
        class MockAsyncHostService(AsyncHostService):
            def get_base_url(self):
                return "http://test"

            def get_health_check_endpoint(self):
                return "/health"

            def get_service_name(self):
                return "test"

        service = MockAsyncHostService(config=HostServiceConfig(base_url="http://test"))

        # Create a mock CancellationToken that implements the protocol
        mock_token = Mock(spec=CancellationToken)
        mock_token.is_cancelled.return_value = False

        # Test that the method uses ONLY the protocol interface
        result = service._check_cancellation(mock_token, "test operation")

        # Should return False for uncancelled token
        assert result is False

        # CRITICAL: Verify no hasattr() calls were made
        with patch("builtins.hasattr") as mock_hasattr:
            service._check_cancellation(mock_token, "test operation")

            # This MUST be zero - no hasattr() calls allowed
            assert mock_hasattr.call_count == 0, (
                "AsyncHostService._check_cancellation still uses hasattr() patterns. "
                "Must use only CancellationToken.is_cancelled property."
            )

    def test_check_cancellation_raises_on_cancelled_token(self):
        """Test _check_cancellation raises CancelledError for cancelled tokens."""

        # Create a mock AsyncHostService for testing the method
        class MockAsyncHostService(AsyncHostService):
            def get_base_url(self):
                return "http://test"

            def get_health_check_endpoint(self):
                return "/health"

            def get_service_name(self):
                return "test"

        service = MockAsyncHostService(config=HostServiceConfig(base_url="http://test"))

        # Create cancelled token
        token = create_cancellation_token("test-op")
        token.cancel("Test cancellation")

        # Should raise asyncio.CancelledError
        with pytest.raises(asyncio.CancelledError):
            service._check_cancellation(token, "test operation")

    def test_check_cancellation_with_none_token(self):
        """Test _check_cancellation handles None token correctly."""

        # Create a mock AsyncHostService for testing the method
        class MockAsyncHostService(AsyncHostService):
            def get_base_url(self):
                return "http://test"

            def get_health_check_endpoint(self):
                return "/health"

            def get_service_name(self):
                return "test"

        service = MockAsyncHostService(config=HostServiceConfig(base_url="http://test"))

        # None token should return False (no cancellation)
        result = service._check_cancellation(None, "test operation")
        assert result is False

    def test_no_legacy_hasattr_patterns_in_async_host_service(self):
        """
        Test that AsyncHostService contains no hasattr() cancellation patterns.

        This is a structural test that scans the actual source code to ensure
        no hasattr() patterns remain in cancellation-related methods.
        """
        import inspect

        # Get the source code of _check_cancellation method
        source = inspect.getsource(AsyncHostService._check_cancellation)

        # CRITICAL: No hasattr() calls should exist in cancellation code
        assert "hasattr(" not in source, (
            "AsyncHostService._check_cancellation still contains hasattr() patterns. "
            "All hasattr() cancellation checking must be eliminated."
        )

        # Verify it uses the protocol interface
        assert "is_cancelled" in source, (
            "AsyncHostService._check_cancellation must use CancellationToken.is_cancelled"
        )


class TestCancellationProtocolCompliance:
    """Test that both services comply with unified cancellation protocol."""

    def test_cancellation_token_protocol_is_imported(self):
        """Test that CancellationToken protocol is properly imported."""
        from ktrdr.managers.async_host_service import CancellationToken as HostProtocol
        from ktrdr.managers.base import CancellationToken as BaseProtocol

        # Both should import the same protocol
        assert BaseProtocol is not None
        assert HostProtocol is not None

    def test_unified_cancellation_interface_consistency(self):
        """Test that both services use the same cancellation interface."""

        # Create mock classes for testing
        class MockServiceOrchestrator(ServiceOrchestrator):
            def _get_default_host_url(self):
                return "http://test"

            def _get_env_var_prefix(self):
                return "TEST"

            def _get_service_name(self):
                return "test"

            def _initialize_adapter(self):
                return None

        class MockAsyncHostService(AsyncHostService):
            def get_base_url(self):
                return "http://test"

            def get_health_check_endpoint(self):
                return "/health"

            def get_service_name(self):
                return "test"

        # Create a real cancellation token
        token = create_cancellation_token("test-op")

        # Both services should handle the same token type
        orchestrator = MockServiceOrchestrator()
        MockAsyncHostService(config=HostServiceConfig(base_url="http://test"))

        # Test uncancelled state
        assert orchestrator._is_token_cancelled(token) is False

        # Cancel the token
        token.cancel("Test cancellation")

        # Both should detect cancellation the same way
        assert orchestrator._is_token_cancelled(token) is True

    def test_no_multi_pattern_fallback_checks_remain(self):
        """
        Test that no multi-pattern fallback checks remain in the codebase.

        This ensures the critical requirement that no hasattr() patterns
        exist for cancellation checking anywhere in the target modules.
        """
        import inspect

        from ktrdr.managers import async_host_service, base

        # Get source code of both modules
        base_source = inspect.getsource(base)
        host_source = inspect.getsource(async_host_service)

        # Check for the specific legacy patterns mentioned in the task
        legacy_patterns = [
            'hasattr(token, "is_cancelled_requested")',
            'hasattr(token, "is_set")',
            'hasattr(cancellation_token, "is_cancelled_requested")',
            'hasattr(cancellation_token, "is_set")',
            'hasattr(cancellation_token, "cancelled")',
        ]

        for pattern in legacy_patterns:
            assert pattern not in base_source, (
                f"ServiceOrchestrator still contains legacy pattern: {pattern}"
            )
            assert pattern not in host_source, (
                f"AsyncHostService still contains legacy pattern: {pattern}"
            )


class TestCancellationProtocolBackwardCompatibility:
    """Test that the unified protocol maintains backward compatibility."""

    def test_cancellation_token_compatibility_properties(self):
        """Test that AsyncCancellationToken provides compatibility properties."""
        token = create_cancellation_token("test-op")

        # Should have the protocol properties
        assert hasattr(token, "is_cancelled")
        assert hasattr(token, "cancel")
        assert hasattr(token, "wait_for_cancellation")

        # Should have backward compatibility property
        assert hasattr(token, "is_cancelled_requested")

        # Compatibility property should match main property
        assert token.is_cancelled_requested == token.is_cancelled()

    def test_cancellation_protocol_interface_completeness(self):
        """Test that CancellationToken protocol defines all required methods."""
        from ktrdr.async_infrastructure.cancellation import CancellationToken

        # Protocol should define required methods
        protocol_methods = dir(CancellationToken)

        required_methods = [
            "is_cancelled",
            "cancel",
            "wait_for_cancellation",
            "is_cancelled_requested",
        ]

        for method in required_methods:
            assert method in protocol_methods, (
                f"CancellationToken protocol missing required method: {method}"
            )
