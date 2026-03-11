"""Tests for FredDataProvider."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from ktrdr.data.context.fred_provider import FredDataProvider

# -- Fixtures and helpers --


@pytest.fixture
def provider(tmp_path):
    """Create a FredDataProvider with a temp cache dir."""
    with patch("ktrdr.data.context.fred_provider.get_fred_settings") as mock_settings:
        settings = MagicMock()
        settings.api_key = "test-key"
        settings.base_url = "https://api.stlouisfed.org/fred/series/observations"
        settings.rate_limit = 120
        settings.cache_dir = str(tmp_path / "fred_cache")
        settings.has_api_key = True
        mock_settings.return_value = settings
        yield FredDataProvider()


@pytest.fixture
def mock_config_single():
    """Config for a single FRED series."""
    config = MagicMock()
    config.series = "DGS2"
    config.provider = "fred"
    return config


@pytest.fixture
def mock_config_multi():
    """Config for multiple FRED series (yield spread)."""
    config = MagicMock()
    config.series = ["DGS2", "IRLTLT01DEM156N"]
    config.provider = "fred"
    return config


def _make_fred_response(observations: list[dict]) -> dict:
    """Create a FRED API JSON response."""
    return {"observations": observations}


SAMPLE_OBSERVATIONS = [
    {"date": "2024-01-02", "value": "4.38"},
    {"date": "2024-01-03", "value": "4.35"},
    {"date": "2024-01-04", "value": "."},  # FRED missing value
    {"date": "2024-01-05", "value": "4.40"},
]

SAMPLE_OBSERVATIONS_2 = [
    {"date": "2024-01-02", "value": "2.10"},
    {"date": "2024-01-03", "value": "2.08"},
    {"date": "2024-01-04", "value": "2.12"},
    {"date": "2024-01-05", "value": "2.15"},
]


# -- get_source_ids tests --


class TestGetSourceIds:
    """Test source ID generation."""

    def test_single_series(self, provider, mock_config_single):
        """Single series should produce one fred_ prefixed ID."""
        ids = provider.get_source_ids(mock_config_single)
        assert ids == ["fred_DGS2"]

    def test_multi_series(self, provider, mock_config_multi):
        """Multi-series should produce individual IDs plus spread."""
        ids = provider.get_source_ids(mock_config_multi)
        assert "fred_DGS2" in ids
        assert "fred_IRLTLT01DEM156N" in ids
        assert "yield_spread_DGS2_IRLTLT01DEM156N" in ids
        assert len(ids) == 3


# -- validate tests --


class TestValidate:
    """Test config validation."""

    @pytest.mark.asyncio
    async def test_valid_series_string(self, provider):
        """String series ID should validate."""
        config = MagicMock()
        config.series = "DGS2"
        errors = await provider.validate(config)
        assert errors == []

    @pytest.mark.asyncio
    async def test_valid_series_list(self, provider):
        """List of series IDs should validate."""
        config = MagicMock()
        config.series = ["DGS2", "IRLTLT01DEM156N"]
        errors = await provider.validate(config)
        assert errors == []

    @pytest.mark.asyncio
    async def test_missing_series(self, provider):
        """Missing series field should produce error."""
        config = MagicMock()
        config.series = None
        errors = await provider.validate(config)
        assert len(errors) > 0
        assert "series" in errors[0].lower()

    @pytest.mark.asyncio
    async def test_empty_series_list(self, provider):
        """Empty series list should produce error."""
        config = MagicMock()
        config.series = []
        errors = await provider.validate(config)
        assert len(errors) > 0

    @pytest.mark.asyncio
    async def test_missing_api_key(self, tmp_path):
        """Missing API key should produce error."""
        with patch(
            "ktrdr.data.context.fred_provider.get_fred_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.api_key = ""
            settings.has_api_key = False
            settings.cache_dir = str(tmp_path)
            mock_settings.return_value = settings
            prov = FredDataProvider()

        config = MagicMock()
        config.series = "DGS2"
        errors = await prov.validate(config)
        assert len(errors) > 0
        assert "api_key" in errors[0].lower() or "key" in errors[0].lower()


# -- fetch tests --


class TestFetch:
    """Test data fetching with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_single_series_fetch(self, provider, mock_config_single):
        """Should fetch a single series and return DataFrame."""
        response = _make_fred_response(SAMPLE_OBSERVATIONS)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.return_value = response
            results = await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        assert len(results) == 1
        assert results[0].source_id == "fred_DGS2"
        assert results[0].frequency == "daily"
        assert results[0].provider == "fred"
        assert isinstance(results[0].data, pd.DataFrame)

    @pytest.mark.asyncio
    async def test_fred_dot_values_are_nan(self, provider, mock_config_single):
        """FRED '.' values should be treated as NaN and forward-filled."""
        response = _make_fred_response(SAMPLE_OBSERVATIONS)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.return_value = response
            results = await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        df = results[0].data
        # "." on Jan 4 should be forward-filled to 4.35 (Jan 3 value)
        assert not df["close"].isna().any()

    @pytest.mark.asyncio
    async def test_multi_series_produces_spread(self, provider, mock_config_multi):
        """Multi-series fetch should produce individual series plus spread."""
        resp1 = _make_fred_response(SAMPLE_OBSERVATIONS)
        resp2 = _make_fred_response(SAMPLE_OBSERVATIONS_2)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.side_effect = [resp1, resp2]
            results = await provider.fetch(
                mock_config_multi,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        assert len(results) == 3
        source_ids = [r.source_id for r in results]
        assert "fred_DGS2" in source_ids
        assert "fred_IRLTLT01DEM156N" in source_ids
        assert "yield_spread_DGS2_IRLTLT01DEM156N" in source_ids

    @pytest.mark.asyncio
    async def test_spread_computation_correct(self, provider, mock_config_multi):
        """Spread should be series[0] - series[1]."""
        obs1 = [{"date": "2024-01-02", "value": "4.38"}]
        obs2 = [{"date": "2024-01-02", "value": "2.10"}]

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.side_effect = [
                _make_fred_response(obs1),
                _make_fred_response(obs2),
            ]
            results = await provider.fetch(
                mock_config_multi,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        spread = next(r for r in results if "yield_spread" in r.source_id)
        assert spread.data["close"].iloc[0] == pytest.approx(4.38 - 2.10)


# -- cache tests --


class TestCache:
    """Test local file caching."""

    @pytest.mark.asyncio
    async def test_cache_written_after_fetch(self, provider, mock_config_single):
        """Cache file should be written after successful fetch."""
        response = _make_fred_response(SAMPLE_OBSERVATIONS)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.return_value = response
            await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        cache_dir = Path(provider._settings.cache_dir)
        assert (cache_dir / "DGS2.csv").exists()

    @pytest.mark.asyncio
    async def test_cache_read_on_subsequent_fetch(self, provider, mock_config_single):
        """Second fetch should use cache, not call API again."""
        response = _make_fred_response(SAMPLE_OBSERVATIONS)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.return_value = response
            # First fetch — calls API
            await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
            assert mock.call_count == 1

            # Second fetch with same range — should use cache
            results = await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )
            # Should still be 1 call (cache hit)
            assert mock.call_count == 1

        assert len(results) == 1
        assert len(results[0].data) > 0

    @pytest.mark.asyncio
    async def test_cache_metadata_tracks_range(self, provider, mock_config_single):
        """Metadata file should track fetched date range."""
        response = _make_fred_response(SAMPLE_OBSERVATIONS)

        with patch.object(provider, "_fetch_series", new_callable=AsyncMock) as mock:
            mock.return_value = response
            await provider.fetch(
                mock_config_single,
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
            )

        cache_dir = Path(provider._settings.cache_dir)
        metadata_path = cache_dir / "metadata.json"
        assert metadata_path.exists()

        metadata = json.loads(metadata_path.read_text())
        assert "DGS2" in metadata
        assert "start_date" in metadata["DGS2"]
        assert "end_date" in metadata["DGS2"]
