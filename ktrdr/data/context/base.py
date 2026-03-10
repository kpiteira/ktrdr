"""Base classes for context data providers.

Defines the abstract interface that all external data providers implement,
the result container for fetched data, and the aligner for mixed-frequency
data alignment via forward-fill.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class ContextDataResult:
    """Result from a context data provider fetch.

    Each fetch may produce multiple results (e.g., FRED entry with two series
    produces individual series plus a computed spread).

    Attributes:
        source_id: Unique identifier for this data source (e.g., "fred_DGS2",
            "yield_spread_DGS2_IRLTLT01DEM156N"). Used by indicators to
            reference context data via the data_source field.
        data: DataFrame with DatetimeIndex containing the fetched values.
        frequency: Data frequency ("hourly", "daily", "weekly").
        provider: Provider name that produced this result.
        metadata: Provider-specific metadata (series info, fetch timestamps, etc.).
    """

    source_id: str
    data: pd.DataFrame
    frequency: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ContextDataProvider(ABC):
    """Abstract interface for external data providers.

    All context data sources (FRED, CFTC, IB cross-pair, calendars) implement
    this interface. The provider handles fetching, caching, and basic validation.
    Alignment to the primary timeframe is handled separately by ContextDataAligner.
    """

    @abstractmethod
    async def fetch(
        self,
        config: Any,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ContextDataResult]:
        """Fetch data for a context_data entry.

        Returns a list because one entry may produce multiple series
        (e.g., FRED entry with series: [DGS2, IRLTLT01DEM156N] produces
        two individual series plus a computed spread).

        Args:
            config: Provider-specific configuration (ContextDataEntry).
            start_date: Start of date range to fetch.
            end_date: End of date range to fetch.

        Returns:
            List of ContextDataResult, one per produced series.
        """
        ...

    @abstractmethod
    async def validate(self, config: Any, **kwargs: Any) -> list[str]:
        """Validate that this config entry is fetchable.

        Called during strategy validation to catch configuration errors
        before training begins.

        Args:
            config: Provider-specific configuration (ContextDataEntry).

        Returns:
            List of error messages (empty = valid).
        """
        ...

    @abstractmethod
    def get_source_ids(self, config: Any) -> list[str]:
        """Return the source_id values this entry will produce.

        Used by strategy validation to check that indicator data_source
        references resolve to declared context_data entries.

        Args:
            config: Provider-specific configuration (ContextDataEntry).

        Returns:
            List of source IDs that fetch() will produce.
        """
        ...


class ContextDataAligner:
    """Aligns lower-frequency context data to the primary instrument's datetime index.

    Uses forward-fill: yesterday's yield close IS the current yield until the
    market updates it. This is semantically correct for daily/weekly economic
    data aligned to hourly trading bars.
    """

    def align(
        self,
        context_data: pd.DataFrame,
        primary_index: pd.DatetimeIndex,
        method: str = "forward_fill",
    ) -> pd.DataFrame:
        """Align context data to the primary timeframe index.

        Steps:
            1. Reindex context data to primary's datetime index
            2. Forward-fill NaN values (last known value carries forward)
            3. Drop leading NaN rows (before first context observation)

        Args:
            context_data: Lower-frequency context DataFrame (e.g., daily yields).
            primary_index: The primary instrument's datetime index (e.g., hourly bars).
            method: Alignment method. Currently only "forward_fill" is supported.

        Returns:
            DataFrame aligned to primary_index with no NaN values.
            May be shorter than primary_index if context data starts later.
        """
        if context_data.empty:
            return context_data

        # Normalize context index to tz-naive for merging with primary index.
        # FRED returns date-only index; primary is hourly with timezone.
        ctx = context_data.copy()
        if ctx.index.tz is not None:
            ctx.index = ctx.index.tz_localize(None)

        primary = primary_index
        if hasattr(primary, "tz") and primary.tz is not None:
            primary = primary.tz_localize(None)

        # Combine context and primary indices, reindex, then forward-fill
        combined_index = ctx.index.union(primary).sort_values()
        aligned = ctx.reindex(combined_index)

        # Forward-fill: carry last known value forward through gaps
        if method == "forward_fill":
            aligned = aligned.ffill()

        # Keep only the primary index timestamps
        aligned = aligned.reindex(primary)

        # Drop leading NaN rows (before first context observation)
        aligned = aligned.dropna(how="any")

        # Restore original timezone if primary had one
        if hasattr(primary_index, "tz") and primary_index.tz is not None:
            aligned.index = aligned.index.tz_localize(primary_index.tz)

        return aligned
