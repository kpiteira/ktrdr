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
import asyncio
import time
from datetime import datetime, timezone, timedelta

# THESE IMPORTS CREATE COMPETING IB CONNECTIONS - DO NOT USE IN E2E TESTS
# from ktrdr.data.ib_connection_pool import get_connection_pool, acquire_ib_connection
# from ktrdr.data.ib_client_id_registry import ClientIdPurpose
# from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
# from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
# from ktrdr.data.data_manager import DataManager


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

            # Any errors should be graceful, not async/coroutine errors
            for error in errors:
                error_str = str(error).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

            # Check pace manager handled violations
            metrics = validator.get_metrics()
            # Should have some pace handling activity if limits were hit
            assert metrics["pace_requests"] > 0

        except Exception as e:
            # Should not have async/await errors
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str

    @pytest.mark.asyncio
    async def test_real_connection_pool_exhaustion_recovery(
        self, real_ib_connection_test
    ):
        """Test connection pool behavior under stress."""
        pool = await get_connection_pool()

        # Try to acquire multiple connections rapidly
        connections = []
        try:
            # Acquire several connections
            for i in range(5):
                try:
                    conn_ctx = await acquire_ib_connection(
                        purpose=ClientIdPurpose.API_POOL,
                        requested_by=f"stress_test_{i}",
                    )
                    # Enter the async context manager
                    conn = await conn_ctx.__aenter__()
                    connections.append((conn_ctx, conn))

                except Exception as e:
                    # Pool exhaustion should be handled gracefully
                    error_str = str(e).lower()
                    assert "runtimewarning" not in error_str
                    assert "coroutine" not in error_str
                    break

            # Verify connections work
            for conn_ctx, conn in connections:
                assert conn.client_id is not None
                assert conn.ib is not None

        finally:
            # Clean up connections
            for conn_ctx, conn in connections:
                try:
                    await conn_ctx.__aexit__(None, None, None)
                except:
                    pass

    @pytest.mark.asyncio
    async def test_real_invalid_symbol_error_handling(self, real_ib_connection_test):
        """Test handling of invalid symbols with real IB validation."""
        invalid_symbols = ["INVALID_XYZ123", "NONEXISTENT_STOCK", "FAKE.FOREX.PAIR"]

        validator = IbSymbolValidatorUnified(component_name="invalid_symbol_test")

        for symbol in invalid_symbols:
            try:
                is_valid = await validator.validate_symbol_async(symbol)

                # Invalid symbols should return False, not crash
                assert isinstance(is_valid, bool)
                # Most should be False, but some might coincidentally exist

            except Exception as e:
                # Should handle invalid symbols gracefully
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

                # Should be a meaningful error message
                assert any(
                    word in error_str
                    for word in ["invalid", "symbol", "not found", "error", "failed"]
                )

    @pytest.mark.asyncio
    async def test_real_data_fetching_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test data fetching error scenarios with real IB."""
        symbol = clean_test_symbols[0]  # AAPL
        fetcher = IbDataFetcherUnified(component_name="error_scenario_test")

        # Test 1: Invalid date range (future dates)
        future_start = datetime.now(timezone.utc) + timedelta(days=30)
        future_end = future_start + timedelta(days=1)

        try:
            df = await fetcher.fetch_historical_data(
                symbol=symbol, timeframe="1h", start=future_start, end=future_end
            )
            # Should either handle gracefully or raise appropriate error

        except Exception as e:
            error_str = str(e).lower()
            # Should not be async/coroutine error
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str

            # Should be a meaningful data error
            assert any(
                word in error_str
                for word in ["future", "date", "invalid", "range", "data"]
            )

        # Test 2: Very large date range that might trigger IB limits
        very_old_start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        very_old_end = datetime(2024, 12, 31, tzinfo=timezone.utc)

        try:
            df = await fetcher.fetch_historical_data(
                symbol=symbol,
                timeframe="1m",  # High frequency over long period
                start=very_old_start,
                end=very_old_end,
                max_retries=1,  # Quick failure
            )
            # Might succeed or fail, but should handle gracefully

        except Exception as e:
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str

    @pytest.mark.asyncio
    async def test_real_connection_timeout_recovery(self, real_ib_connection_test):
        """Test connection timeout and recovery scenarios."""
        # Create validator that might experience timeouts
        validator = IbSymbolValidatorUnified(component_name="timeout_test")

        # Test with symbols that might take time to validate
        test_symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]

        start_time = time.time()

        try:
            # Batch validate with potential for timeouts
            results = await validator.batch_validate_async(
                symbols=test_symbols, max_concurrent=3
            )

            elapsed = time.time() - start_time

            # Should complete in reasonable time or handle timeouts gracefully
            assert elapsed < 60, "Batch validation took too long"

            # Should get results for all symbols (True/False)
            assert len(results) == len(test_symbols)
            for symbol, result in results.items():
                assert isinstance(result, bool)

        except Exception as e:
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str

            # Timeout errors should be graceful
            assert any(
                word in error_str
                for word in ["timeout", "connection", "error", "failed"]
            )

    @pytest.mark.asyncio
    async def test_real_head_timestamp_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test head timestamp fetching error scenarios."""
        validator = IbSymbolValidatorUnified(component_name="head_timestamp_error_test")

        # Test with symbol that might not support head timestamps
        symbol = clean_test_symbols[0]

        try:
            head_timestamp = await validator.fetch_head_timestamp_async(
                symbol=symbol, force_refresh=True, max_retries=2
            )

            # Might be None if not supported, which is OK
            if head_timestamp:
                assert isinstance(head_timestamp, str)
                # Should be valid ISO format
                datetime.fromisoformat(head_timestamp.replace("Z", "+00:00"))

        except Exception as e:
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str


@pytest.mark.real_ib
@pytest.mark.real_error_scenarios
class TestRealSystemErrorRecovery:
    """Test system-level error recovery with real IB."""

    @pytest.mark.asyncio
    async def test_datamanager_ib_fallback_error_recovery(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test DataManager IB fallback error recovery."""
        symbol = clean_test_symbols[0]

        # Create DataManager with IB enabled
        dm = DataManager(enable_ib=True)

        # Test scenarios that might trigger various errors
        error_scenarios = [
            {
                "name": "future_dates",
                "params": {
                    "symbol": symbol,
                    "timeframe": "1h",
                    "start_date": datetime.now(timezone.utc) + timedelta(days=1),
                    "end_date": datetime.now(timezone.utc) + timedelta(days=2),
                    "mode": "full",
                },
            },
            {
                "name": "invalid_symbol",
                "params": {
                    "symbol": "INVALID_SYMBOL_XYZ",
                    "timeframe": "1h",
                    "mode": "tail",
                },
            },
        ]

        for scenario in error_scenarios:
            try:
                df = dm.load_data(**scenario["params"])
                # Might succeed or fail, but should handle gracefully

            except Exception as e:
                error_str = str(e).lower()

                # Should not have async/coroutine errors
                assert (
                    "runtimewarning" not in error_str
                ), f"Async error in {scenario['name']}: {e}"
                assert (
                    "coroutine" not in error_str
                ), f"Coroutine error in {scenario['name']}: {e}"
                assert (
                    "was never awaited" not in error_str
                ), f"Await error in {scenario['name']}: {e}"

                # Should be meaningful error message
                assert len(error_str) > 0, f"Empty error message in {scenario['name']}"

    @pytest.mark.asyncio
    async def test_api_endpoint_error_propagation(
        self, api_client, real_ib_connection_test
    ):
        """Test that API endpoints properly handle and propagate IB errors."""

        # Test symbol discovery with potentially problematic symbol
        request_data = {"symbol": "VERY_INVALID_SYMBOL_XYZ123", "force_refresh": True}

        response = api_client.post("/api/v1/ib/symbols/discover", json=request_data)

        # Should handle gracefully (200 with error details or 400)
        assert response.status_code in [200, 400]

        data = response.json()

        if response.status_code == 200:
            # Should have proper structure even for errors
            assert "data" in data
            discovery_result = data["data"]
            assert "symbol_info" in discovery_result
            # symbol_info might be null for invalid symbols

        else:  # 400 error
            assert "error" in data
            error_msg = data["error"].lower()
            # Should not contain async/coroutine error messages
            assert "runtimewarning" not in error_msg
            assert "coroutine" not in error_msg

    @pytest.mark.asyncio
    async def test_concurrent_error_scenarios(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test concurrent operations with various error conditions."""

        async def operation_with_errors(symbol, operation_type):
            """Run operation that might encounter errors."""
            try:
                if operation_type == "validate":
                    validator = IbSymbolValidatorUnified(
                        component_name=f"concurrent_error_{symbol}"
                    )
                    return await validator.validate_symbol_async(symbol)

                elif operation_type == "fetch":
                    fetcher = IbDataFetcherUnified(
                        component_name=f"concurrent_error_{symbol}"
                    )
                    end_date = datetime.now(timezone.utc)
                    start_date = end_date - timedelta(hours=1)

                    df = await fetcher.fetch_historical_data(
                        symbol=symbol, timeframe="1h", start=start_date, end=end_date
                    )
                    return df is not None

            except Exception as e:
                return f"error: {str(e)}"

        # Mix of valid and invalid symbols/operations
        operations = [
            (clean_test_symbols[0], "validate"),  # Valid
            ("INVALID_XYZ", "validate"),  # Invalid
            (clean_test_symbols[1], "fetch"),  # Valid
            ("INVALID_ABC", "fetch"),  # Invalid
        ]

        # Run concurrently
        tasks = [
            operation_with_errors(symbol, op_type) for symbol, op_type in operations
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no async/coroutine errors in any concurrent operation
        for i, result in enumerate(results):
            operation_desc = f"Operation {i}: {operations[i]}"

            if isinstance(result, Exception):
                error_str = str(result).lower()
                assert (
                    "runtimewarning" not in error_str
                ), f"Async error in {operation_desc}"
                assert (
                    "coroutine" not in error_str
                ), f"Coroutine error in {operation_desc}"
                assert (
                    "was never awaited" not in error_str
                ), f"Await error in {operation_desc}"

            elif isinstance(result, str) and result.startswith("error:"):
                error_str = result.lower()
                assert (
                    "runtimewarning" not in error_str
                ), f"Async error in {operation_desc}"
                assert (
                    "coroutine" not in error_str
                ), f"Coroutine error in {operation_desc}"


@pytest.mark.real_ib
@pytest.mark.real_error_scenarios
class TestRealPerformanceUnderStress:
    """Test system performance and stability under stress with real IB."""

    @pytest.mark.asyncio
    async def test_rapid_sequential_operations(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test rapid sequential operations don't cause async errors."""
        symbol = clean_test_symbols[0]
        validator = IbSymbolValidatorUnified(component_name="rapid_sequential_test")

        # Perform rapid sequential validations
        for i in range(20):
            try:
                result = await validator.validate_symbol_async(symbol)
                assert isinstance(result, bool)

                # Small delay to avoid overwhelming IB
                await asyncio.sleep(0.1)

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str

    @pytest.mark.asyncio
    async def test_memory_stability_under_load(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test memory stability during extended operations."""
        symbols = clean_test_symbols * 3  # Repeat symbols for more operations

        validator = IbSymbolValidatorUnified(component_name="memory_stability_test")

        # Run batch operations that might reveal memory leaks
        batch_size = 5
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            try:
                results = await validator.batch_validate_async(batch, max_concurrent=2)

                # Verify results structure
                assert isinstance(results, dict)
                assert len(results) == len(batch)

                # Small delay between batches
                await asyncio.sleep(1)

            except Exception as e:
                error_str = str(e).lower()
                assert "runtimewarning" not in error_str
                assert "coroutine" not in error_str
                assert "was never awaited" not in error_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
