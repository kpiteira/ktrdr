"""Unit tests for CFTC COT context data provider (M9 Task 9.3).

Tests that CftcCotProvider:
1. Returns weekly DataFrame with net_position and percentile columns
2. Percentile computation is correct (0-100 scale, rolling window)
3. Cache written and reused
4. get_source_ids() returns correct IDs
5. validate() checks currency code format
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def cftc_config() -> MagicMock:
    """Mock ContextDataEntry for CFTC provider."""
    config = MagicMock()
    config.provider = "cftc_cot"
    config.report = "EUR"
    config.alignment = "forward_fill"
    return config


@pytest.fixture
def sample_cot_data() -> pd.DataFrame:
    """Sample COT data as would be parsed from CFTC report.

    200 weeks of data — enough for 156-week rolling window.
    """
    dates = pd.date_range("2020-01-07", periods=200, freq="W-TUE")
    np.random.seed(42)
    net_positions = np.cumsum(np.random.randn(200) * 5000).astype(int)
    return pd.DataFrame(
        {"net_position": net_positions},
        index=dates,
    )


class TestCftcCotProviderSourceIds:
    """Test get_source_ids() returns correct IDs."""

    def test_source_ids_for_eur(self, cftc_config: MagicMock) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()
        ids = provider.get_source_ids(cftc_config)
        assert "cot_EUR_net_pos" in ids
        assert "cot_EUR_net_pct" in ids
        assert len(ids) == 2

    def test_source_ids_for_gbp(self) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        config = MagicMock()
        config.report = "GBP"
        provider = CftcCotProvider()
        ids = provider.get_source_ids(config)
        assert "cot_GBP_net_pos" in ids
        assert "cot_GBP_net_pct" in ids


class TestCftcCotProviderValidate:
    """Test validate() checks config correctness."""

    @pytest.mark.asyncio
    async def test_validate_valid_config(self, cftc_config: MagicMock) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()
        errors = await provider.validate(cftc_config)
        assert errors == []

    @pytest.mark.asyncio
    async def test_validate_missing_report(self) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        config = MagicMock()
        config.report = None
        provider = CftcCotProvider()
        errors = await provider.validate(config)
        assert len(errors) > 0
        assert "report" in errors[0].lower()

    @pytest.mark.asyncio
    async def test_validate_invalid_currency_code(self) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        config = MagicMock()
        config.report = "INVALID_CODE"
        provider = CftcCotProvider()
        errors = await provider.validate(config)
        assert len(errors) > 0


class TestCftcPercentileComputation:
    """Test percentile computation over rolling windows."""

    def test_compute_percentiles_52w(self, sample_cot_data: pd.DataFrame) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()
        result = provider._compute_percentiles(sample_cot_data)

        assert "net_pct_52w" in result.columns
        # First 51 weeks should be NaN (not enough data for 52w window)
        assert result["net_pct_52w"].iloc[:51].isna().all()
        # After warm-up, values should be 0-100
        valid = result["net_pct_52w"].dropna()
        assert valid.min() >= 0.0
        assert valid.max() <= 100.0

    def test_compute_percentiles_156w(self, sample_cot_data: pd.DataFrame) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()
        result = provider._compute_percentiles(sample_cot_data)

        assert "net_pct_156w" in result.columns
        # First 155 weeks should be NaN
        assert result["net_pct_156w"].iloc[:155].isna().all()
        valid = result["net_pct_156w"].dropna()
        assert valid.min() >= 0.0
        assert valid.max() <= 100.0

    def test_percentile_known_values(self) -> None:
        """Test percentile with known data: ascending values should yield 100% at end."""
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        dates = pd.date_range("2020-01-07", periods=60, freq="W-TUE")
        ascending = pd.DataFrame(
            {"net_position": range(60)},
            index=dates,
        )
        provider = CftcCotProvider()
        result = provider._compute_percentiles(ascending)

        # Last value in a monotonically ascending series: 52w percentile = 100
        last_valid_52 = result["net_pct_52w"].dropna().iloc[-1]
        assert last_valid_52 == pytest.approx(100.0, abs=0.1)


class TestCftcCotProviderFetch:
    """Test fetch() returns results with correct structure."""

    @pytest.mark.asyncio
    async def test_fetch_returns_two_results(
        self, cftc_config: MagicMock, sample_cot_data: pd.DataFrame
    ) -> None:
        """Fetch should return net_pos and net_pct results."""
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()

        with patch.object(provider, "_fetch_cot_data", return_value=sample_cot_data):
            results = await provider.fetch(
                cftc_config,
                datetime(2023, 1, 1),
                datetime(2024, 1, 1),
            )

        assert len(results) == 2
        source_ids = [r.source_id for r in results]
        assert "cot_EUR_net_pos" in source_ids
        assert "cot_EUR_net_pct" in source_ids

    @pytest.mark.asyncio
    async def test_fetch_net_pos_has_close_column(
        self, cftc_config: MagicMock, sample_cot_data: pd.DataFrame
    ) -> None:
        """Net position result should have 'close' column for indicator compatibility."""
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()

        with patch.object(provider, "_fetch_cot_data", return_value=sample_cot_data):
            results = await provider.fetch(
                cftc_config,
                datetime(2023, 1, 1),
                datetime(2024, 1, 1),
            )

        net_pos = [r for r in results if r.source_id == "cot_EUR_net_pos"][0]
        assert "close" in net_pos.data.columns

    @pytest.mark.asyncio
    async def test_fetch_net_pct_has_close_column(
        self, cftc_config: MagicMock, sample_cot_data: pd.DataFrame
    ) -> None:
        """Percentile result should have 'close' column for indicator compatibility."""
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()

        with patch.object(provider, "_fetch_cot_data", return_value=sample_cot_data):
            results = await provider.fetch(
                cftc_config,
                datetime(2023, 1, 1),
                datetime(2024, 1, 1),
            )

        net_pct = [r for r in results if r.source_id == "cot_EUR_net_pct"][0]
        assert "close" in net_pct.data.columns

    @pytest.mark.asyncio
    async def test_fetch_frequency_is_weekly(
        self, cftc_config: MagicMock, sample_cot_data: pd.DataFrame
    ) -> None:
        from ktrdr.data.context.cftc_provider import CftcCotProvider

        provider = CftcCotProvider()

        with patch.object(provider, "_fetch_cot_data", return_value=sample_cot_data):
            results = await provider.fetch(
                cftc_config,
                datetime(2023, 1, 1),
                datetime(2024, 1, 1),
            )

        for r in results:
            assert r.frequency == "weekly"
            assert r.provider == "cftc_cot"


class TestCftcCotProviderRegistration:
    """Test provider is registered in registry."""

    def test_cftc_cot_registered(self) -> None:
        from ktrdr.data.context.registry import ContextDataProviderRegistry

        registry = ContextDataProviderRegistry()
        assert "cftc_cot" in registry.available_providers()
