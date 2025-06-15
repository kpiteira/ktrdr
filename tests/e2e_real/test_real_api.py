"""
Real API End-to-End Tests

These tests make actual HTTP requests to the API that trigger real IB operations.
They test the complete data flow from API request through IB interaction to response.
"""

import pytest
import asyncio
import time
import json


@pytest.mark.real_ib
@pytest.mark.real_api
class TestRealAPIDataFlow:
    """Test API endpoints with real IB data operations."""

    @pytest.mark.asyncio
    async def test_real_ib_status_endpoint(self, api_client, real_ib_connection_test):
        """Test /api/v1/ib/status with real IB connection."""
        response = api_client.get("/api/v1/ib/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        ib_status = data["data"]

        # With real IB connection, should show actual status
        assert "ib_available" in ib_status
        assert "connection" in ib_status

        # Connection should show real details
        connection = ib_status["connection"]
        assert "connected" in connection
        assert "host" in connection
        assert "port" in connection

        # Should be actually connected if IB Gateway is running
        if connection.get("connected"):
            assert connection.get("client_id") is not None
            assert isinstance(connection.get("client_id"), int)

    def test_real_ib_symbol_discovery(
        self, api_client, clean_test_symbols, ib_availability_check
    ):
        """Test /api/v1/ib/symbols/discover with or without real IB connection."""
        symbol = clean_test_symbols[0]  # AAPL

        request_data = {
            "symbol": symbol,
            "force_refresh": True,  # Force real IB lookup if available
        }

        response = api_client.post("/api/v1/ib/symbols/discover", json=request_data)

        assert response.status_code == 200
        data = response.json()

        if ib_availability_check["available"]:
            # With real IB, should succeed
            assert data["success"] is True
            discovery_result = data["data"]
            assert discovery_result is not None
            assert "symbol_info" in discovery_result
            assert "cached" in discovery_result
            assert "discovery_time_ms" in discovery_result

            symbol_info = discovery_result["symbol_info"]
            if symbol_info:  # Might be null if symbol not found
                assert "symbol" in symbol_info
                assert "instrument_type" in symbol_info
                assert "exchange" in symbol_info
                assert symbol_info["symbol"] == symbol
        else:
            # Without IB, should handle gracefully
            # May succeed with cached data or fail with informative error
            if not data["success"]:
                assert "error" in data
                assert data["data"] is None  # Should be null when failed

                error_info = data["error"]
                error_msg = error_info.get("message", "").lower()
                # Should be IB-related error, not async/coroutine error
                assert any(
                    word in error_msg
                    for word in [
                        "ib",
                        "connection",
                        "gateway",
                        "unavailable",
                        "timeout",
                        "discover",
                    ]
                )
                assert "runtimewarning" not in error_msg
                assert "coroutine" not in error_msg
                assert "was never awaited" not in error_msg
            else:
                # If successful, should have cached data
                discovery_result = data["data"]
                assert discovery_result is not None

    @pytest.mark.asyncio
    async def test_real_data_load_api_with_ib_fallback(
        self, api_client, clean_test_symbols, e2e_helper, real_ib_connection_test
    ):
        """Test /api/v1/data/load that falls back to real IB when local data missing."""
        symbol = clean_test_symbols[1]  # MSFT

        request_data = {
            "symbol": symbol,
            "timeframe": "1h",
            "start_date": "2024-12-01",
            "end_date": "2024-12-02",
            "mode": "tail",
            "trading_hours_only": False,
        }

        # Make async request
        response = api_client.post(
            "/api/v1/data/load?async_mode=true", json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Should get operation ID for tracking
        operation_id = data["data"]["operation_id"]
        assert operation_id is not None

        # Wait for completion and check for async errors in logs
        try:
            result = await e2e_helper.wait_for_operation_completion(
                api_client, operation_id, timeout=60
            )

            # Verify operation completed without async/await errors
            assert result["status"] == "completed"

            # Check for data loading results
            assert "fetched_bars" in result
            assert "ib_requests_made" in result
            assert "execution_time_seconds" in result

            # If IB was used, should have made some requests
            if result["ib_requests_made"] > 0:
                assert result["fetched_bars"] >= 0  # Could be 0 if no data in range

        except TimeoutError:
            # Check operation status for debugging
            status_response = api_client.get(f"/api/v1/operations/{operation_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                pytest.fail(f"Operation timed out. Last status: {status_data}")
            else:
                pytest.fail(
                    f"Operation timed out and status check failed: {status_response.status_code}"
                )

    @pytest.mark.asyncio
    async def test_real_ib_load_api_endpoint(
        self, api_client, clean_test_symbols, e2e_helper, real_ib_connection_test
    ):
        """Test /api/v1/ib/load endpoint with real IB data fetching."""
        symbol = clean_test_symbols[2]  # EURUSD

        request_data = {
            "symbol": symbol,
            "timeframe": "1h",
            "mode": "tail",
            "max_bars": 50,  # Limit to avoid long-running test
        }

        response = api_client.post("/api/v1/ib/load?async_mode=true", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        operation_id = data["data"]["operation_id"]

        # Wait for real IB operation to complete
        result = await e2e_helper.wait_for_operation_completion(
            api_client, operation_id, timeout=45
        )

        # Verify IB operation results
        assert result["status"] in [
            "completed",
            "failed",
        ]  # Could fail if IB unavailable

        if result["status"] == "completed":
            assert "bars_fetched" in result or "fetched_bars" in result
            assert "ib_requests_made" in result
            assert result["ib_requests_made"] > 0  # Should have made IB requests

    @pytest.mark.asyncio
    async def test_real_ib_cleanup_api_endpoint(
        self, api_client, real_ib_connection_test
    ):
        """Test /api/v1/ib/cleanup with real connection cleanup."""
        response = api_client.post("/api/v1/ib/cleanup")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        cleanup_result = data["data"]
        assert "connections_closed" in cleanup_result
        assert isinstance(cleanup_result["connections_closed"], int)
        assert cleanup_result["connections_closed"] >= 0

    @pytest.mark.asyncio
    async def test_real_data_endpoint_with_ib_fallback(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test /api/v1/data/{symbol}/{timeframe} with potential IB fallback."""
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        response = api_client.get(f"/api/v1/data/{symbol}/{timeframe}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Should return data structure
        ohlcv_data = data["data"]
        assert "dates" in ohlcv_data
        assert "ohlcv" in ohlcv_data
        assert "metadata" in ohlcv_data

        # Verify metadata
        metadata = ohlcv_data["metadata"]
        assert metadata["symbol"] == symbol
        assert metadata["timeframe"] == timeframe

    @pytest.mark.asyncio
    async def test_real_ib_health_monitoring(self, api_client, real_ib_connection_test):
        """Test /api/v1/ib/health with real IB health checks."""
        response = api_client.get("/api/v1/ib/health")

        # Should return 200 (healthy) or 503 (unhealthy)
        assert response.status_code in [200, 503]

        data = response.json()
        assert "data" in data

        health_data = data["data"]
        assert "healthy" in health_data
        assert isinstance(health_data["healthy"], bool)

        # If unhealthy, should have error details
        if not health_data["healthy"]:
            assert "error_message" in health_data

    @pytest.mark.asyncio
    async def test_real_ib_resilience_endpoint_with_ib_running(
        self, api_client, real_ib_connection_test
    ):
        """Test /api/v1/ib/resilience endpoint with real IB connection."""
        response = api_client.get("/api/v1/ib/resilience")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        resilience_data = data["data"]

        # Verify all phases are reported
        assert "phase_1_systematic_validation" in resilience_data
        assert "phase_2_garbage_collection" in resilience_data
        assert "phase_3_client_id_preference" in resilience_data
        assert "overall_resilience_score" in resilience_data
        assert "connection_pool_health" in resilience_data

        # With real IB, should get higher resilience score
        score = resilience_data["overall_resilience_score"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100

        # Phase 1: Systematic validation should work with real IB
        phase1 = resilience_data["phase_1_systematic_validation"]
        assert phase1["status"] == "working"
        assert phase1["validation_enabled"] is True

        # Phase 2: Garbage collection should be configured
        phase2 = resilience_data["phase_2_garbage_collection"]
        assert phase2["status"] == "working"
        assert phase2["max_idle_time_seconds"] == 300.0  # 5 minutes

        # Phase 3: Client ID preference should work
        phase3 = resilience_data["phase_3_client_id_preference"]
        assert phase3["status"] == "working"

        # Connection pool health should show real connections if any
        pool_health = resilience_data["connection_pool_health"]
        assert "total_connections" in pool_health
        assert "healthy_connections" in pool_health
        assert pool_health["pool_uptime_seconds"] > 0


@pytest.mark.real_ib
@pytest.mark.real_api
class TestRealAPIErrorScenarios:
    """Test API error handling with real IB operations."""

    @pytest.mark.asyncio
    async def test_api_handles_invalid_symbol_discovery(
        self, api_client, real_ib_connection_test
    ):
        """Test symbol discovery with invalid symbol."""
        request_data = {"symbol": "INVALID_SYMBOL_XYZ123", "force_refresh": True}

        response = api_client.post("/api/v1/ib/symbols/discover", json=request_data)

        assert response.status_code == 200  # Should handle gracefully
        data = response.json()

        # Should either succeed with null result or provide error details
        if data.get("success"):
            discovery_result = data["data"]
            # Null symbol_info is OK for invalid symbols
            assert "symbol_info" in discovery_result
        else:
            assert "error" in data

    @pytest.mark.asyncio
    async def test_api_handles_future_date_range(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test data loading with future date range."""
        symbol = clean_test_symbols[0]

        request_data = {
            "symbol": symbol,
            "timeframe": "1h",
            "start_date": "2030-01-01",  # Future date
            "end_date": "2030-01-02",
            "mode": "tail",
        }

        response = api_client.post("/api/v1/data/load", json=request_data)

        # Should handle date validation
        assert response.status_code in [200, 400]

        data = response.json()
        if response.status_code == 400:
            assert "error" in data
            assert "future" in data["error"].lower() or "date" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_api_concurrent_ib_operations(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test concurrent API calls that use IB don't interfere."""
        import asyncio

        symbols = clean_test_symbols[:2]  # AAPL, MSFT

        async def test_ib_status():
            """Async function to test IB status."""
            loop = asyncio.get_event_loop()
            # Use loop.run_in_executor to make sync httpx call in async context
            response = await loop.run_in_executor(
                None, lambda: api_client.get("/api/v1/ib/status")
            )
            return ("status", response.status_code, response.text)

        async def test_symbol_discovery(symbol):
            """Async function to test symbol discovery."""
            loop = asyncio.get_event_loop()
            request_data = {"symbol": symbol, "force_refresh": False}
            response = await loop.run_in_executor(
                None,
                lambda: api_client.post(
                    "/api/v1/ib/symbols/discover", json=request_data
                ),
            )
            return ("discover", symbol, response.status_code, response.text)

        # Run concurrent operations
        tasks = [
            test_ib_status(),
            test_symbol_discovery(symbols[0]),
            test_symbol_discovery(symbols[1]),
            test_ib_status(),  # Duplicate to test concurrency
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all operations completed successfully
        assert len(results) == 4

        for result in results:
            assert not isinstance(result, Exception), f"Operation failed: {result}"

            operation_type = result[0]
            status_code = result[2] if operation_type == "discover" else result[1]

            assert (
                status_code == 200
            ), f"Operation {operation_type} failed with status {status_code}"


@pytest.mark.real_ib
class TestRealAPIWhenIBUnavailable:
    """Test API behavior when IB Gateway is not running."""

    def test_resilience_endpoint_without_ib(self, api_client, ib_availability_check):
        """Test /api/v1/ib/resilience endpoint works even when IB is down."""
        # Skip if IB is actually available
        if ib_availability_check["available"]:
            pytest.skip("IB is available, skipping IB-unavailable tests")

        response = api_client.get("/api/v1/ib/resilience")

        # Should work even without IB (infrastructure scoring)
        assert response.status_code in [200, 503]

        data = response.json()

        if response.status_code == 200:
            assert data["success"] is True
            resilience_data = data["data"]

            # Should still report infrastructure status
            assert "overall_resilience_score" in resilience_data
            score = resilience_data["overall_resilience_score"]
            assert isinstance(score, (int, float))
            assert score >= 0  # Should get infrastructure points even without IB

            # Phases should be reported as "working" for infrastructure
            assert "phase_1_systematic_validation" in resilience_data
            assert "phase_2_garbage_collection" in resilience_data
            assert "phase_3_client_id_preference" in resilience_data

    def test_ib_status_graceful_failure_without_ib(
        self, api_client, ib_availability_check
    ):
        """Test /api/v1/ib/status handles IB unavailability gracefully."""
        if ib_availability_check["available"]:
            pytest.skip("IB is available, skipping IB-unavailable tests")

        response = api_client.get("/api/v1/ib/status")

        # Should handle gracefully
        assert response.status_code in [200, 503]

        data = response.json()
        assert "success" in data

        if response.status_code == 503:
            # Should have error information
            assert not data["success"]
            assert "error" in data
        else:
            # If 200, should show IB as unavailable
            status_data = data["data"]
            assert "ib_available" in status_data
            assert not status_data["ib_available"]

    def test_ib_health_reports_unavailable_without_ib(
        self, api_client, ib_availability_check
    ):
        """Test /api/v1/ib/health correctly reports unavailable when IB is down."""
        if ib_availability_check["available"]:
            pytest.skip("IB is available, skipping IB-unavailable tests")

        response = api_client.get("/api/v1/ib/health")

        # Should return 503 (unhealthy) when IB is down
        assert response.status_code == 503

        data = response.json()
        assert "data" in data

        health_data = data["data"]
        assert "healthy" in health_data
        assert not health_data["healthy"]
        assert "error_message" in health_data

    def test_data_endpoints_graceful_fallback_without_ib(
        self, api_client, clean_test_symbols, ib_availability_check
    ):
        """Test data endpoints handle IB unavailability gracefully."""
        if ib_availability_check["available"]:
            pytest.skip("IB is available, skipping IB-unavailable tests")

        symbol = clean_test_symbols[0]
        timeframe = "1h"

        # Test GET data endpoint
        response = api_client.get(f"/api/v1/data/{symbol}/{timeframe}")

        # Should work with local data only
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Should return empty data structure gracefully
        ohlcv_data = data["data"]
        assert "dates" in ohlcv_data
        assert "ohlcv" in ohlcv_data
        assert "metadata" in ohlcv_data


@pytest.mark.real_ib
@pytest.mark.real_api
class TestRealAPIDataQuality:
    """Test data quality and consistency with real IB operations."""

    @pytest.mark.asyncio
    async def test_real_data_consistency_across_endpoints(
        self, api_client, clean_test_symbols, real_ib_connection_test
    ):
        """Test that data is consistent across different API endpoints."""
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        # Get data via GET endpoint
        get_response = api_client.get(f"/api/v1/data/{symbol}/{timeframe}")
        assert get_response.status_code == 200

        get_data = get_response.json()["data"]
        get_metadata = get_data["metadata"]

        # Verify basic metadata consistency
        assert get_metadata["symbol"] == symbol
        assert get_metadata["timeframe"] == timeframe

        # Data should be properly formatted
        dates = get_data["dates"]
        ohlcv = get_data["ohlcv"]

        if dates and ohlcv:  # If data exists
            assert len(dates) == len(ohlcv)
            assert len(dates) > 0

            # Each OHLCV entry should have 5 values (O,H,L,C,V)
            for entry in ohlcv:
                assert len(entry) == 5
                assert all(isinstance(x, (int, float)) for x in entry)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
