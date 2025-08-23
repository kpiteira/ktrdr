"""
Real Data Pipeline End-to-End Tests

These tests exercise the complete data pipeline with real IB operations:
Symbol Validation → Data Fetching → CSV Writing → Local Loading

IMPORTANT: These tests MUST use API endpoints only, never direct module imports.
Direct usage of DataManager, IbDataFetcherUnified, or IbSymbolValidatorUnified
creates competing IB connections with the backend, causing client ID conflicts
and potentially breaking IB Gateway.

✅ SAFE: API calls (api_client.get/post)
❌ UNSAFE: Direct module imports and instantiation
"""

import asyncio

import pytest


@pytest.mark.real_ib
@pytest.mark.real_pipeline
class TestRealDataPipeline:
    """Test complete data pipeline with real IB operations."""

    @pytest.mark.asyncio
    async def test_complete_symbol_validation_to_data_loading_pipeline(
        self, clean_test_symbols, api_client, real_ib_connection_test, e2e_helper
    ):
        """Test complete pipeline via API: validate symbol → fetch data → verify loading."""
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        # Step 1: Symbol validation via API
        discover_response = api_client.post(
            "/api/v1/ib/symbols/discover",
            json={"symbol": symbol, "force_refresh": True},
        )
        assert discover_response.status_code == 200
        discover_data = discover_response.json()
        assert discover_data["success"], f"Symbol discovery failed: {discover_data}"

        symbol_info = discover_data["data"]["symbol_info"]
        assert symbol_info is not None, f"Should get symbol info for {symbol}"
        assert symbol_info["symbol"] == symbol

        # Step 2: Data loading via API
        load_response = api_client.post(
            "/api/v1/data/load",
            json={
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": "tail",
                "async_mode": False,  # Synchronous for test simplicity
            },
        )
        assert load_response.status_code == 200
        load_data = load_response.json()
        assert load_data["success"], f"Data loading failed: {load_data}"

        # Step 3: Verify data was loaded
        fetched_bars = load_data["data"].get("fetched_bars", 0)
        assert fetched_bars > 0, f"Should have fetched some data bars for {symbol}"

        # Step 4: Verify we can retrieve the loaded data
        get_response = api_client.get(
            f"/api/v1/data/load?symbol={symbol}&timeframe={timeframe}&mode=local"
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["success"], f"Failed to retrieve cached data: {get_data}"

    @pytest.mark.asyncio
    async def test_pipeline_with_async_data_loading(
        self, clean_test_symbols, api_client, real_ib_connection_test
    ):
        """Test pipeline with async data loading and status monitoring."""
        symbol = clean_test_symbols[1]  # Should be MSFT
        timeframe = "1d"

        # Start async data loading
        load_response = api_client.post(
            "/api/v1/data/load",
            json={
                "symbol": symbol,
                "timeframe": timeframe,
                "mode": "tail",
                "async_mode": True,
            },
        )
        assert load_response.status_code == 200
        load_data = load_response.json()
        assert load_data["success"], f"Async data loading failed: {load_data}"

        operation_id = load_data["data"]["operation_id"]
        assert operation_id, "Should get operation ID for async operation"

        # Monitor operation status
        max_polls = 30  # 30 seconds timeout
        for i in range(max_polls):
            status_response = api_client.get(f"/api/v1/operations/{operation_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()
            assert status_data[
                "success"
            ], f"Failed to get operation status: {status_data}"

            operation = status_data["data"]
            status = operation["status"]

            if status in ["completed", "failed", "cancelled"]:
                assert (
                    status == "completed"
                ), f"Operation should complete successfully, got: {status}"

                # Verify we got some data
                result_summary = operation.get("result_summary", {})
                fetched_bars = result_summary.get("fetched_bars", 0)
                assert fetched_bars > 0, f"Should have fetched some data for {symbol}"
                break

            await asyncio.sleep(1)  # Wait 1 second between polls
        else:
            pytest.fail(
                f"Operation {operation_id} did not complete within {max_polls} seconds"
            )

    @pytest.mark.asyncio
    async def test_pipeline_error_handling_via_api(
        self, api_client, real_ib_connection_test
    ):
        """Test pipeline error handling for invalid symbols via API."""
        invalid_symbol = "INVALID_XYZ_123"

        # Test symbol validation fails gracefully
        discover_response = api_client.post(
            "/api/v1/ib/symbols/discover",
            json={"symbol": invalid_symbol, "force_refresh": True},
        )
        assert discover_response.status_code == 200
        discover_data = discover_response.json()

        # Should succeed but return no symbol info for invalid symbols
        if discover_data["success"]:
            symbol_info = discover_data["data"]["symbol_info"]
            # symbol_info might be None for invalid symbols, which is fine

        # Test data loading handles invalid symbols gracefully
        load_response = api_client.post(
            "/api/v1/data/load",
            json={
                "symbol": invalid_symbol,
                "timeframe": "1h",
                "mode": "tail",
                "async_mode": False,
            },
        )

        # Should either succeed with no data or fail gracefully
        if load_response.status_code == 200:
            load_data = load_response.json()
            # Success with 0 bars is acceptable for invalid symbols
        else:
            # 400/422 errors are also acceptable for invalid symbols
            assert load_response.status_code in [
                400,
                422,
            ], f"Unexpected error code: {load_response.status_code}"

    @pytest.mark.skip(
        reason="DISABLED: Uses old architecture that creates competing IB connections"
    )
    @pytest.mark.asyncio
    async def test_concurrent_pipeline_operations(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test multiple pipeline operations running concurrently."""
        pass

    @pytest.mark.skip(
        reason="DISABLED: Uses old architecture that creates competing IB connections"
    )
    @pytest.mark.asyncio
    async def test_pipeline_data_quality_validation(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test pipeline includes data quality validation."""
        pass

    @pytest.mark.skip(
        reason="DISABLED: Uses old architecture that creates competing IB connections"
    )
    @pytest.mark.asyncio
    async def test_pipeline_handles_ib_connection_errors(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test pipeline gracefully handles IB connection errors."""
        pass

    @pytest.mark.skip(
        reason="DISABLED: Uses old architecture that creates competing IB connections"
    )
    @pytest.mark.asyncio
    async def test_pipeline_handles_invalid_symbols_gracefully(
        self, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test pipeline handles invalid symbols without async errors."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
