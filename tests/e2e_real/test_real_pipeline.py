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

import pytest
import asyncio
import pandas as pd
from pathlib import Path
import tempfile
import os
import json


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
            json={"symbol": symbol, "force_refresh": True}
        )
        assert discover_response.status_code == 200
        discover_data = discover_response.json()
        assert discover_data["success"], f"Symbol discovery failed: {discover_data}"
        
        symbol_info = discover_data["data"]["symbol_info"]
        assert symbol_info is not None, f"Should get symbol info for {symbol}"
        assert symbol_info["symbol"] == symbol

        # Step 2: Data loading via API  
        from datetime import datetime, timezone, timedelta
        end_date = datetime.now(timezone.utc).date()
        start_date = (end_date - timedelta(days=2))

        load_request = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "mode": "tail",
            "trading_hours_only": False,
        }

        load_response = api_client.post(
            "/api/v1/data/load?async_mode=true", json=load_request
        )
        assert load_response.status_code == 200
        load_data = load_response.json()
        assert load_data["success"], f"Data load failed: {load_data}"

        operation_id = load_data["data"]["operation_id"]
        
        # Step 3: Wait for operation completion
        result = await e2e_helper.wait_for_operation_completion(
            api_client, operation_id, timeout=60
        )
        assert result["status"] == "completed", f"Data load operation failed: {result}"

        # Step 4: Verify data is accessible via API
        data_response = api_client.get(f"/api/v1/data/{symbol}/{timeframe}")
        assert data_response.status_code == 200
        
        data_json = data_response.json()
        assert data_json["success"], f"Data retrieval failed: {data_json}"
        
        ohlcv_data = data_json["data"]
        assert "dates" in ohlcv_data
        assert "ohlcv" in ohlcv_data
        assert "metadata" in ohlcv_data
        
        # Verify metadata
        metadata = ohlcv_data["metadata"] 
        assert metadata["symbol"] == symbol
        assert metadata["timeframe"] == timeframe

    @pytest.mark.skip(reason="DISABLED: Direct DataManager usage creates competing IB connections")
    async def test_data_manager_full_integration_with_ib(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test DataManager with real IB integration end-to-end.
        
        This test is disabled because it directly instantiates DataManager,
        which creates its own IB connections that compete with the backend's
        connection pool, potentially causing client ID conflicts and breaking
        IB Gateway. Use API-based tests instead.
        """
        pass

    @pytest.mark.skip(reason="DISABLED: Uses old IbSymbolValidatorUnified that creates competing IB connections")
    @pytest.mark.asyncio
    async def test_forex_symbol_complete_pipeline(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test complete pipeline with forex symbol (different from stocks)."""
        pass

        # Check forex symbol detection
        assert validator.is_forex_symbol(
            forex_symbol
        ), f"{forex_symbol} should be detected as forex"

        # Validate with IB
        is_valid = await validator.validate_symbol_async(forex_symbol)
        assert is_valid, f"Forex symbol {forex_symbol} should be valid"

        contract_info = await validator.get_contract_details_async(forex_symbol)
        assert contract_info is not None
        assert contract_info.asset_type == "CASH", "Forex should have CASH asset type"

        # Step 2: Fetch forex data
        fetcher = IbDataFetcherUnified(component_name="forex_e2e_test")

        from datetime import datetime, timezone, timedelta

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=24)  # 24 hours for forex

        df = await fetcher.fetch_historical_data(
            symbol=forex_symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
            instrument_type="forex",
        )

        # Forex markets are open more hours, more likely to have data
        if df is not None and not df.empty:
            # Step 3: Test DataManager with forex
            dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

            loaded_df = dm.load_data(
                symbol=forex_symbol, timeframe=timeframe, mode="tail"
            )

            # Verify forex data handling
            if loaded_df is not None and not loaded_df.empty:
                assert len(loaded_df) > 0
                assert all(
                    col in loaded_df.columns
                    for col in ["open", "high", "low", "close", "volume"]
                )

    @pytest.mark.skip(reason="DISABLED: Uses old DataManager that creates competing IB connections")
    @pytest.mark.asyncio
    async def test_gap_filling_pipeline_with_real_ib(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test gap filling pipeline with real IB data."""
        pass
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        # Create a partial data file to simulate gaps
        csv_file = temp_data_dir / f"{symbol}_{timeframe}.csv"

        # Create minimal CSV with gaps
        from datetime import datetime, timezone, timedelta

        base_date = datetime(2024, 12, 1, 9, 30, tzinfo=timezone.utc)

        # Create data with intentional gaps
        sample_data = []
        for i in range(0, 10, 3):  # Every 3rd hour to create gaps
            timestamp = base_date + timedelta(hours=i)
            sample_data.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "open": 150.0 + i,
                    "high": 152.0 + i,
                    "low": 149.0 + i,
                    "close": 151.0 + i,
                    "volume": 1000 + i * 100,
                }
            )

        import pandas as pd

        df = pd.DataFrame(sample_data)
        df.to_csv(csv_file, index=False)

        # Test DataManager gap filling with IB
        dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

        try:
            # Request data range that spans the gaps - should trigger IB gap filling
            filled_df = dm.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=base_date,
                end_date=base_date + timedelta(hours=12),
                mode="backfill",  # Should trigger gap analysis and filling
            )

            if filled_df is not None and not filled_df.empty:
                # Should have more data than original (gaps filled)
                assert len(filled_df) >= len(sample_data)

        except Exception as e:
            # Verify no async/coroutine errors in gap filling pipeline
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str

    @pytest.mark.skip(reason="DISABLED: Uses old IbSymbolValidatorUnified that creates competing IB connections")
    @pytest.mark.asyncio
    async def test_head_timestamp_integration_pipeline(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """DISABLED: Test head timestamp fetching integrated with data validation."""
        pass

        contract_info = await validator.get_contract_details_async(symbol)
        assert contract_info is not None

        # Step 2: Fetch head timestamp from IB
        head_timestamp = await validator.fetch_head_timestamp_async(
            symbol=symbol, timeframe=timeframe, force_refresh=True
        )

        if head_timestamp:  # Might be None if IB doesn't support it for this symbol
            # Step 3: Validate date range against head timestamp
            from datetime import datetime, timezone, timedelta

            # Test date validation pipeline
            head_dt = datetime.fromisoformat(head_timestamp.replace("Z", "+00:00"))

            # Request data before head timestamp (should be adjusted)
            early_date = head_dt - timedelta(days=30)

            is_valid, warning_msg, suggested_date = (
                validator.validate_date_range_against_head_timestamp(
                    symbol=symbol, start_date=early_date, timeframe=timeframe
                )
            )

            # Should adjust to valid range
            assert is_valid, "Date validation should succeed with adjustment"
            if suggested_date:
                assert (
                    suggested_date >= head_dt
                ), "Suggested date should be after head timestamp"

    @pytest.mark.skip(reason="DISABLED: Uses old IbSymbolValidatorUnified and DataManager that create competing IB connections")
    @pytest.mark.asyncio
    async def test_concurrent_pipeline_operations(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test multiple pipeline operations running concurrently."""
        pass
                is_valid = await validator.validate_symbol_async(symbol)

                if is_valid:
                    # Data Manager loading
                    dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

                    from datetime import datetime, timezone, timedelta

                    end_date = datetime.now(timezone.utc)
                    start_date = end_date - timedelta(hours=6)

                    df = dm.load_data(
                        symbol=symbol,
                        timeframe=timeframe,
                        start_date=start_date,
                        end_date=end_date,
                        mode="tail",
                    )

                    return {
                        "symbol": symbol,
                        "valid": True,
                        "data_loaded": (
                            df is not None and not df.empty if df is not None else False
                        ),
                    }
                else:
                    return {"symbol": symbol, "valid": False, "data_loaded": False}

            except Exception as e:
                return {"symbol": symbol, "error": str(e)}

        # Run pipelines concurrently
        tasks = [run_pipeline(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify concurrent operations succeeded
        assert len(results) == len(symbols)

        for result in results:
            assert not isinstance(
                result, Exception
            ), f"Concurrent operation failed: {result}"
            assert "error" not in result, f"Pipeline error: {result}"
            assert result["valid"], f"Symbol {result['symbol']} should be valid"


@pytest.mark.real_ib
@pytest.mark.real_pipeline
class TestRealPipelineErrorRecovery:
    """Test pipeline error recovery with real IB operations."""

    @pytest.mark.skip(reason="DISABLED: Uses old DataManager that creates competing IB connections")
    @pytest.mark.asyncio
    async def test_pipeline_handles_ib_disconnection_gracefully(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test pipeline graceful handling when IB connection issues occur."""
        pass

        try:
            # This might fail if IB becomes unavailable, but should not crash with async errors
            df = dm.load_data(symbol=symbol, timeframe="1h", mode="tail")

            # If successful, verify data
            if df is not None and not df.empty:
                assert len(df) > 0

        except Exception as e:
            # Should handle IB errors gracefully
            error_str = str(e).lower()

            # Should NOT have async/coroutine errors
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str

            # Should be a graceful error message
            assert any(
                phrase in error_str
                for phrase in ["connection", "timeout", "data not found", "ib error"]
            ), f"Should be a graceful error, got: {e}"

    @pytest.mark.skip(reason="DISABLED: Uses old DataManager that creates competing IB connections")
    @pytest.mark.asyncio
    async def test_pipeline_handles_invalid_symbols_gracefully(
        self, real_ib_connection_test, temp_data_dir
    ):
        """DISABLED: Test pipeline handles invalid symbols without async errors."""
        pass

        try:
            df = dm.load_data(symbol=invalid_symbol, timeframe="1h", mode="tail")
            # Might succeed with None/empty result or fail gracefully

        except Exception as e:
            # Should handle invalid symbols gracefully
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
