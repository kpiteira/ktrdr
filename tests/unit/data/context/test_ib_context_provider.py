"""Unit tests for IB context data provider (M9 Task 9.2).

Tests that IbContextProvider:
1. Returns OHLCV DataFrame for cached symbols via DataRepository
2. Raises clear error for missing/uncached symbols
3. Returns correct source IDs
4. Validates config correctly
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.data.context.base import ContextDataResult


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Sample OHLCV data as returned by DataRepository."""
    idx = pd.date_range("2024-01-01", periods=100, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "open": range(100),
            "high": range(1, 101),
            "low": range(100),
            "close": range(100),
            "volume": [1000] * 100,
        },
        index=idx,
    )


@pytest.fixture
def ib_config() -> MagicMock:
    """Mock ContextDataEntry for IB provider."""
    config = MagicMock()
    config.provider = "ib"
    config.symbol = "GBPUSD"
    config.timeframe = "1h"
    config.instrument_type = "forex"
    return config


class TestIbContextProviderFetch:
    """Test fetch() returns OHLCV DataFrame from cache."""

    @pytest.mark.asyncio
    async def test_fetch_returns_ohlcv_for_cached_symbol(
        self, ib_config: MagicMock, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Fetch should delegate to DataRepository and return OHLCV data."""
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()

        with patch.object(provider, "_repository") as mock_repo:
            mock_repo.load_from_cache.return_value = sample_ohlcv

            results = await provider.fetch(
                ib_config,
                datetime(2024, 1, 1),
                datetime(2024, 1, 5),
            )

            assert len(results) == 1
            assert isinstance(results[0], ContextDataResult)
            assert results[0].source_id == "GBPUSD"
            assert results[0].provider == "ib"
            assert "close" in results[0].data.columns
            assert len(results[0].data) > 0

    @pytest.mark.asyncio
    async def test_fetch_filters_by_date_range(
        self, ib_config: MagicMock, sample_ohlcv: pd.DataFrame
    ) -> None:
        """Fetch should filter data to requested date range."""
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()

        with patch.object(provider, "_repository") as mock_repo:
            mock_repo.load_from_cache.return_value = sample_ohlcv

            results = await provider.fetch(
                ib_config,
                datetime(2024, 1, 2),
                datetime(2024, 1, 3),
            )

            # Should have data, filtered to range
            assert len(results) == 1
            result_df = results[0].data
            assert result_df.index[0] >= pd.Timestamp("2024-01-02", tz="UTC")
            assert result_df.index[-1] <= pd.Timestamp("2024-01-03", tz="UTC")

    @pytest.mark.asyncio
    async def test_fetch_missing_symbol_raises_error(
        self, ib_config: MagicMock
    ) -> None:
        """Fetch should raise clear error when symbol not in cache."""
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()

        with patch.object(provider, "_repository") as mock_repo:
            mock_repo.load_from_cache.return_value = pd.DataFrame()

            with pytest.raises(RuntimeError, match="not found in cache"):
                await provider.fetch(
                    ib_config,
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 5),
                )


class TestIbContextProviderSourceIds:
    """Test get_source_ids() returns symbol name."""

    def test_source_ids_returns_symbol(self, ib_config: MagicMock) -> None:
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()
        ids = provider.get_source_ids(ib_config)
        assert ids == ["GBPUSD"]


class TestIbContextProviderValidate:
    """Test validate() checks config correctness."""

    @pytest.mark.asyncio
    async def test_validate_valid_config(self, ib_config: MagicMock) -> None:
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()

        with patch.object(provider, "_repository") as mock_repo:
            mock_repo.get_available_symbols.return_value = ["GBPUSD", "EURUSD"]
            errors = await provider.validate(ib_config)
            assert errors == []

    @pytest.mark.asyncio
    async def test_validate_missing_symbol_field(self) -> None:
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()
        config = MagicMock()
        config.symbol = None

        errors = await provider.validate(config)
        assert len(errors) > 0
        assert "symbol" in errors[0].lower()

    @pytest.mark.asyncio
    async def test_validate_symbol_not_cached(self, ib_config: MagicMock) -> None:
        from ktrdr.data.context.ib_context_provider import IbContextProvider

        provider = IbContextProvider()

        with patch.object(provider, "_repository") as mock_repo:
            mock_repo.get_available_symbols.return_value = ["EURUSD"]
            errors = await provider.validate(ib_config)
            assert len(errors) > 0
            assert "ktrdr data load" in errors[0]


class TestIbContextProviderRegistration:
    """Test that IB provider is registered in the registry."""

    def test_ib_registered_in_registry(self) -> None:
        from ktrdr.data.context.registry import ContextDataProviderRegistry

        registry = ContextDataProviderRegistry()
        assert "ib" in registry.available_providers()
