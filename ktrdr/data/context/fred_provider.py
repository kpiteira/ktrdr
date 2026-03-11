"""FRED (Federal Reserve Economic Data) context data provider.

Fetches yield curve data, interest rates, and other economic indicators
from the FRED API. Supports single series and multi-series with automatic
spread computation for yield differentials.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import httpx
import pandas as pd

from ktrdr.config import get_fred_settings

from .base import ContextDataProvider, ContextDataResult

logger = logging.getLogger(__name__)


class _RedactApiKeyFilter(logging.Filter):
    """Filter that redacts api_key query parameter from httpx log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg") and isinstance(record.msg, str):
            import re

            record.msg = re.sub(r"api_key=[^&\s\"']+", "api_key=***", record.msg)
        return True


# Install filter once at module load — concurrency-safe unlike level mutation
_httpx_filter = _RedactApiKeyFilter()
logging.getLogger("httpx").addFilter(_httpx_filter)


class FredDataProvider(ContextDataProvider):
    """Fetches economic data from FRED API with local caching.

    Handles:
    - Single series fetch (e.g., DGS2 → US 2Y yield)
    - Multi-series with spread computation (e.g., [DGS2, IRLTLT01DEM156N]
      → individual series + yield_spread_DGS2_IRLTLT01DEM156N)
    - Local CSV caching with metadata tracking
    - FRED's "." missing value convention (treated as NaN, forward-filled)
    """

    def __init__(self) -> None:
        self._settings = get_fred_settings()

    def get_source_ids(self, config: Any) -> list[str]:
        """Return source IDs this config will produce.

        Single series: ["fred_{id}"]
        Multi-series: ["fred_{s1}", "fred_{s2}", "yield_spread_{s1}_{s2}"]
        """
        series_list = self._normalize_series(config.series)
        ids = [f"fred_{s}" for s in series_list]
        if len(series_list) >= 2:
            ids.append(f"yield_spread_{series_list[0]}_{series_list[1]}")
        return ids

    async def validate(self, config: Any, **kwargs: Any) -> list[str]:
        """Validate FRED config entry.

        Checks:
        - series field is present and non-empty
        - API key is configured
        """
        errors: list[str] = []

        series = getattr(config, "series", None)
        if series is None:
            errors.append("FRED provider requires 'series' field")
            return errors

        if isinstance(series, str):
            if series.strip() == "":
                errors.append("FRED provider 'series' string must be non-empty")
                return errors
        elif isinstance(series, list):
            if len(series) == 0:
                errors.append("FRED provider 'series' list must not be empty")
                return errors
            if not all(isinstance(s, str) and s.strip() != "" for s in series):
                errors.append(
                    "FRED provider 'series' list must contain only non-empty strings"
                )
                return errors
        else:
            errors.append("FRED provider 'series' must be a string or list of strings")
            return errors

        if not self._settings.has_api_key:
            errors.append(
                "FRED API key not configured. Set KTRDR_FRED_API_KEY or "
                "register at https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        return errors

    async def fetch(
        self,
        config: Any,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ContextDataResult]:
        """Fetch FRED series data, using cache when available.

        For multi-series configs, also computes the spread (series[0] - series[1]).
        """
        series_list = self._normalize_series(config.series)
        results: list[ContextDataResult] = []

        for series_id in series_list:
            df = self._load_from_cache(series_id, start_date, end_date)
            if df is None:
                response = await self._fetch_series(series_id, start_date, end_date)
                df = self._parse_observations(response)
                self._save_to_cache(series_id, df, start_date, end_date)

            results.append(
                ContextDataResult(
                    source_id=f"fred_{series_id}",
                    data=df,
                    frequency="daily",
                    provider="fred",
                    metadata={"series_id": series_id},
                )
            )

        # Compute spread for multi-series
        if len(series_list) >= 2:
            spread_df = self._compute_spread(
                results[0].data, results[1].data, series_list[0], series_list[1]
            )
            spread_id = f"yield_spread_{series_list[0]}_{series_list[1]}"
            results.append(
                ContextDataResult(
                    source_id=spread_id,
                    data=spread_df,
                    frequency="daily",
                    provider="fred",
                    metadata={
                        "type": "spread",
                        "series_a": series_list[0],
                        "series_b": series_list[1],
                    },
                )
            )

        return results

    async def _fetch_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Fetch a single series from the FRED API.

        Args:
            series_id: FRED series identifier (e.g., "DGS2").
            start_date: Start of observation range.
            end_date: End of observation range.

        Returns:
            Raw JSON response dict from FRED API.
        """
        params = {
            "series_id": series_id,
            "observation_start": start_date.strftime("%Y-%m-%d"),
            "observation_end": end_date.strftime("%Y-%m-%d"),
            "file_type": "json",
            "api_key": self._settings.api_key,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._settings.base_url,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def _parse_observations(self, response: dict) -> pd.DataFrame:
        """Parse FRED API response into a DataFrame.

        Handles FRED's "." convention for missing values (holidays):
        treated as NaN, then forward-filled.
        """
        observations = response.get("observations", [])
        if not observations:
            return pd.DataFrame(columns=["close"])

        dates = []
        values = []
        for obs in observations:
            dates.append(pd.Timestamp(obs["date"]))
            raw_value = obs["value"]
            if raw_value == ".":
                values.append(float("nan"))
            else:
                values.append(float(raw_value))

        df = pd.DataFrame({"value": values}, index=pd.DatetimeIndex(dates))
        # Forward-fill NaN from FRED's "." missing data convention
        df = df.ffill()
        # Rename to 'close' — indicators compute on 'close' by default
        df = df.rename(columns={"value": "close"})
        return df

    def _compute_spread(
        self,
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        series_a: str,
        series_b: str,
    ) -> pd.DataFrame:
        """Compute yield spread: series_a - series_b.

        Aligns on shared dates, computes difference, drops any NaN.
        """
        # Align on common index
        combined = pd.DataFrame({"a": df_a["close"], "b": df_b["close"]}).dropna()

        spread = pd.DataFrame(
            {"close": combined["a"] - combined["b"]},
            index=combined.index,
        )
        return spread

    # -- Caching --

    def _cache_dir(self) -> Path:
        """Get or create cache directory."""
        cache_path = Path(self._settings.cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _metadata_path(self) -> Path:
        """Path to cache metadata file."""
        return self._cache_dir() / "metadata.json"

    def _load_metadata(self) -> dict:
        """Load cache metadata from disk."""
        path = self._metadata_path()
        if path.exists():
            return json.loads(path.read_text())
        return {}

    def _save_metadata(self, metadata: dict) -> None:
        """Save cache metadata to disk."""
        self._metadata_path().write_text(json.dumps(metadata, indent=2))

    def _load_from_cache(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Union[pd.DataFrame, None]:
        """Load cached data if it covers the requested range."""
        cache_file = self._cache_dir() / f"{series_id}.csv"
        if not cache_file.exists():
            return None

        metadata = self._load_metadata()
        series_meta = metadata.get(series_id)
        if series_meta is None:
            return None

        # Compare as date strings to avoid tz-aware vs tz-naive mismatch
        cached_start = series_meta["start_date"][:10]  # YYYY-MM-DD
        cached_end = series_meta["end_date"][:10]
        req_start = start_date.strftime("%Y-%m-%d")
        req_end = end_date.strftime("%Y-%m-%d")
        if cached_start <= req_start and cached_end >= req_end:
            logger.debug("Cache hit for FRED series %s", series_id)
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return df

        return None

    def _save_to_cache(
        self,
        series_id: str,
        df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Save fetched data to local cache."""
        cache_file = self._cache_dir() / f"{series_id}.csv"
        df.to_csv(cache_file)

        metadata = self._load_metadata()
        metadata[series_id] = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "rows": len(df),
        }
        self._save_metadata(metadata)
        logger.debug("Cached FRED series %s (%d rows)", series_id, len(df))

    @staticmethod
    def _normalize_series(series: Any) -> list[str]:
        """Normalize series field to a list of strings."""
        if isinstance(series, str):
            return [series]
        if isinstance(series, list):
            return list(series)
        return []
