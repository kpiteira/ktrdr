"""
Real Data Pipeline End-to-End Tests

These tests exercise the complete data pipeline with real IB operations:
Symbol Validation → Data Fetching → CSV Writing → Local Loading

These tests would catch integration bugs where individual components
work in isolation but fail when chained together.
"""

import pytest
import asyncio
import pandas as pd
from pathlib import Path
import tempfile
import os

from ktrdr.data.data_manager import DataManager
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.data.local_data_loader import LocalDataLoader


@pytest.mark.real_ib
@pytest.mark.real_pipeline
class TestRealDataPipeline:
    """Test complete data pipeline with real IB operations."""

    @pytest.mark.asyncio
    async def test_complete_symbol_validation_to_data_loading_pipeline(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test complete pipeline: validate symbol → fetch data → write file → load locally."""
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        # Step 1: Real symbol validation
        validator = IbSymbolValidatorUnified(component_name="e2e_pipeline_test")

        is_valid = await validator.validate_symbol_async(symbol)
        assert is_valid, f"Symbol {symbol} should be valid"

        # Get contract details
        contract_info = await validator.get_contract_details_async(symbol)
        assert contract_info is not None, f"Should get contract info for {symbol}"
        assert contract_info.symbol == symbol
        assert contract_info.asset_type in ["STK", "CASH", "FUT"]

        # Step 2: Real data fetching
        fetcher = IbDataFetcherUnified(component_name="e2e_pipeline_test")

        from datetime import datetime, timezone, timedelta

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=2)  # 2 days of data

        df = await fetcher.fetch_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
            instrument_type="stock" if contract_info.asset_type == "STK" else "forex",
        )

        # Verify data was fetched
        assert df is not None, "Should fetch data from IB"
        if not df.empty:  # Data might be empty for weekends/holidays
            assert len(df) > 0
            assert list(df.columns) == ["open", "high", "low", "close", "volume"]

            # Step 3: Write to CSV file (simulate data manager behavior)
            csv_file = temp_data_dir / f"{symbol}_{timeframe}.csv"

            # Add timestamp column (like real data manager does)
            df_with_timestamp = df.copy()
            df_with_timestamp.reset_index(inplace=True)
            df_with_timestamp.rename(columns={"index": "timestamp"}, inplace=True)

            df_with_timestamp.to_csv(csv_file, index=False)

            # Verify file was written
            assert csv_file.exists(), "CSV file should be created"
            assert csv_file.stat().st_size > 0, "CSV file should not be empty"

            # Step 4: Load data locally (verify round-trip)
            loader = LocalDataLoader(data_dir=str(temp_data_dir))

            loaded_df = loader.load(symbol, timeframe)
            assert loaded_df is not None, "Should load data from local file"
            assert not loaded_df.empty, "Loaded data should not be empty"

            # Verify data integrity through pipeline
            assert len(loaded_df) == len(
                df
            ), "Loaded data should match fetched data length"

    @pytest.mark.asyncio
    async def test_data_manager_full_integration_with_ib(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test DataManager with real IB integration end-to-end."""
        symbol = clean_test_symbols[1]  # MSFT
        timeframe = "1h"

        # Initialize DataManager with real IB enabled
        dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

        # Test full data loading pipeline with IB fallback
        # Use a date range that likely doesn't exist locally to trigger IB fetch
        from datetime import datetime, timezone, timedelta

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=1)

        try:
            df = dm.load_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                mode="full",  # Force comprehensive loading
            )

            # If successful, verify data quality
            if df is not None and not df.empty:
                assert len(df) > 0
                assert all(
                    col in df.columns
                    for col in ["open", "high", "low", "close", "volume"]
                )

                # Verify data file was created
                expected_file = temp_data_dir / f"{symbol}_{timeframe}.csv"
                assert expected_file.exists(), "Data file should be created"

            # If no data returned, that's OK (might be weekend/holiday)
            # The important thing is no async/coroutine errors occurred

        except Exception as e:
            # Should not have async/await related errors
            error_str = str(e).lower()
            assert "runtimewarning" not in error_str
            assert "coroutine" not in error_str
            assert "was never awaited" not in error_str

            # Re-raise if it's not an expected data-related error
            if (
                "data not found" not in error_str
                and "no data available" not in error_str
            ):
                raise

    @pytest.mark.asyncio
    async def test_forex_symbol_complete_pipeline(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test complete pipeline with forex symbol (different from stocks)."""
        forex_symbol = clean_test_symbols[2]  # EURUSD
        timeframe = "1h"

        # Step 1: Validate forex symbol
        validator = IbSymbolValidatorUnified(component_name="forex_e2e_test")

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

    @pytest.mark.asyncio
    async def test_gap_filling_pipeline_with_real_ib(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test gap filling pipeline with real IB data."""
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

    @pytest.mark.asyncio
    async def test_head_timestamp_integration_pipeline(
        self, clean_test_symbols, real_ib_connection_test
    ):
        """Test head timestamp fetching integrated with data validation."""
        symbol = clean_test_symbols[0]  # AAPL
        timeframe = "1h"

        # Step 1: Get contract info and head timestamp
        validator = IbSymbolValidatorUnified(component_name="head_timestamp_e2e")

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

    @pytest.mark.asyncio
    async def test_concurrent_pipeline_operations(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test multiple pipeline operations running concurrently."""
        symbols = clean_test_symbols[:2]  # AAPL, MSFT
        timeframe = "1h"

        async def run_pipeline(symbol):
            """Run complete pipeline for one symbol."""
            try:
                # Validation
                validator = IbSymbolValidatorUnified(
                    component_name=f"concurrent_{symbol}"
                )
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

    @pytest.mark.asyncio
    async def test_pipeline_handles_ib_disconnection_gracefully(
        self, clean_test_symbols, real_ib_connection_test, temp_data_dir
    ):
        """Test pipeline graceful handling when IB connection issues occur."""
        symbol = clean_test_symbols[0]

        dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

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

    @pytest.mark.asyncio
    async def test_pipeline_handles_invalid_symbols_gracefully(
        self, real_ib_connection_test, temp_data_dir
    ):
        """Test pipeline handles invalid symbols without async errors."""
        invalid_symbol = "INVALID_XYZ123"

        dm = DataManager(enable_ib=True, data_dir=str(temp_data_dir))

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
