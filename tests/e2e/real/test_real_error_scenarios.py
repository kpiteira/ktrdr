"""
Real Error Scenario End-to-End Tests

DISABLED: These tests create competing IB connections with the backend.

These tests were designed to exercise error conditions with real IB connections,
but they directly import and use backend modules, which creates competing IB
connections that interfere with the backend's connection pool management.

This can cause:
- Client ID conflicts
- Multiple IB objects per client ID (confuses IB Gateway)
- Connection pool corruption
- IB Gateway instability

All tests in this file are disabled. Error scenarios should be tested via
API endpoints instead of direct module usage.
"""

import pytest


@pytest.mark.real_ib
@pytest.mark.real_error_scenarios
class TestRealIBErrorHandling:
    """DISABLED: All tests in this class create competing IB connections."""

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_pace_limiting_handling(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_connection_pool_exhaustion_recovery(
        self, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_invalid_symbol_error_handling(self, real_ib_connection_test):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_data_fetching_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_connection_timeout_recovery(self, real_ib_connection_test):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_real_head_timestamp_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass


@pytest.mark.real_ib
@pytest.mark.real_error_scenarios
class TestRealSystemErrorRecovery:
    """DISABLED: All tests in this class create competing IB connections."""

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_datamanager_ib_fallback_error_recovery(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_api_endpoint_error_propagation(
        self, api_client, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_concurrent_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass


@pytest.mark.real_ib
@pytest.mark.real_error_scenarios
class TestRealPerformanceUnderStress:
    """DISABLED: All tests in this class create competing IB connections."""

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_rapid_sequential_operations(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass

    @pytest.mark.skip(reason="DISABLED: Creates competing IB connections with backend")
    async def test_memory_stability_under_load(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: This test creates its own IB connections that compete with backend."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
