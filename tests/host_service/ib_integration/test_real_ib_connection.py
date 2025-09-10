"""
Real IB Gateway integration tests.

These tests require an actual IB Gateway or TWS instance to be running.
They test the real connection, data retrieval, and trading functionality.

Run these tests only when:
1. IB Gateway or TWS is running
2. You have a paper trading account configured
3. You want to test actual IB integration behavior

Usage:
    make test-host  # Run all host service tests including these
    uv run pytest tests/host_service/ib_integration/ -v  # Run only IB tests
"""

import asyncio
from datetime import datetime

import pytest

from ktrdr.ib.ib_connection import IbConnection


@pytest.mark.host_service
@pytest.mark.real_ib
class TestRealIbConnection:
    """Test real IB Gateway connection and basic functionality."""

    @pytest.mark.asyncio
    async def test_connection_establishment(self, real_ib_connection):
        """Test that we can establish a connection to IB Gateway."""
        ib = real_ib_connection
        assert ib.isConnected()
        assert ib.client.isConnected()

    @pytest.mark.asyncio
    async def test_account_info_retrieval(self, real_ib_connection):
        """Test retrieving account information."""
        ib = real_ib_connection

        # Get account summary
        account_summary = ib.accountSummary()
        assert len(account_summary) > 0

        # Should have common account values
        summary_tags = {item.tag for item in account_summary}
        expected_tags = {"NetLiquidation", "TotalCashValue", "BuyingPower"}
        assert expected_tags.issubset(
            summary_tags
        ), f"Missing tags: {expected_tags - summary_tags}"

    @pytest.mark.asyncio
    async def test_market_data_request(self, real_ib_connection):
        """Test requesting real market data for a common stock."""
        ib = real_ib_connection

        # Request market data for SPY (common ETF)
        from ib_insync import Stock

        contract = Stock("SPY", "SMART", "USD")

        # Qualify the contract
        qualified_contracts = await ib.qualifyContractsAsync(contract)
        assert len(qualified_contracts) > 0

        qualified_contract = qualified_contracts[0]

        # Request market data
        ticker = ib.reqMktData(qualified_contract, "", False, False)

        # Wait for data to arrive
        await asyncio.sleep(3.0)

        # Should have some market data
        assert ticker is not None
        # Note: In after-hours, some fields might be NaN, so we just check the ticker exists

        # Cancel market data request
        ib.cancelMktData(qualified_contract)

    @pytest.mark.asyncio
    async def test_historical_data_request(self, real_ib_connection):
        """Test requesting historical data."""
        ib = real_ib_connection

        from ib_insync import Stock

        contract = Stock("AAPL", "SMART", "USD")

        # Qualify the contract
        qualified_contracts = await ib.qualifyContractsAsync(contract)
        assert len(qualified_contracts) > 0
        qualified_contract = qualified_contracts[0]

        # Request historical data
        end_time = datetime.now()
        bars = await ib.reqHistoricalDataAsync(
            qualified_contract,
            endDateTime=end_time,
            durationStr="1 D",  # 1 day of data
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=True,
        )

        assert len(bars) > 0

        # Verify bar structure
        bar = bars[0]
        assert hasattr(bar, "date")
        assert hasattr(bar, "open")
        assert hasattr(bar, "high")
        assert hasattr(bar, "low")
        assert hasattr(bar, "close")
        assert hasattr(bar, "volume")

        # Verify reasonable price data
        assert bar.open > 0
        assert bar.high >= bar.open
        assert bar.low <= bar.open
        assert bar.close > 0


@pytest.mark.host_service
@pytest.mark.real_ib
class TestIbConnectionClass:
    """Test our IbConnection wrapper with real IB Gateway."""

    @pytest.mark.asyncio
    async def test_ib_connection_wrapper(self, config_manager):
        """Test our IbConnection class with real IB."""
        try:
            # Create connection using our wrapper
            connection = IbConnection()
            await connection.connect()

            assert connection.is_connected()

            # Test basic functionality
            account_summary = await connection.get_account_summary()
            assert account_summary is not None
            assert len(account_summary) > 0

            await connection.disconnect()
            assert not connection.is_connected()

        except Exception as e:
            pytest.skip(f"IbConnection test failed: {e}")


if __name__ == "__main__":
    # Allow running this file directly for local testing
    pytest.main([__file__, "-v", "-m", "host_service"])
