"""IB (Interactive Brokers) context data provider for cross-pair data.

Thin wrapper around DataRepository — IB context symbols (e.g., GBPUSD for
cross-pair momentum) must be pre-loaded via `ktrdr data load GBPUSD 1h`.
No new API calls are made; this provider reads from the local data cache.
"""

from datetime import datetime
from typing import Any

import pandas as pd

from ktrdr import get_logger
from ktrdr.data.repository import DataRepository

from .base import ContextDataProvider, ContextDataResult

logger = get_logger(__name__)


class IbContextProvider(ContextDataProvider):
    """Loads cross-pair OHLCV data from local cache as context data.

    IB data is already cached by the standard data loading pipeline
    (`ktrdr data load SYMBOL TIMEFRAME`). This provider simply reads
    from that cache and wraps it as a ContextDataResult.
    """

    def __init__(self) -> None:
        self._repository = DataRepository()

    def get_source_ids(self, config: Any) -> list[str]:
        """Return source IDs — the symbol name.

        Args:
            config: ContextDataEntry with symbol field.

        Returns:
            List containing the symbol (e.g., ["GBPUSD"]).
        """
        return [config.symbol]

    async def validate(self, config: Any, **kwargs: Any) -> list[str]:
        """Validate IB context config.

        Checks that symbol is specified and exists in cache.
        """
        errors: list[str] = []

        symbol = getattr(config, "symbol", None)
        if not symbol:
            errors.append("IB provider requires 'symbol' field")
            return errors

        # Check if symbol data is available in cache
        available = self._repository.get_available_symbols()
        if symbol not in available:
            timeframe = getattr(config, "timeframe", "1h")
            errors.append(
                f"Symbol '{symbol}' not found in data cache. "
                f"Load it first: ktrdr data load {symbol} {timeframe}"
            )

        return errors

    async def fetch(
        self,
        config: Any,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ContextDataResult]:
        """Load cross-pair OHLCV data from local cache.

        Args:
            config: ContextDataEntry with symbol and timeframe fields.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Single-element list with OHLCV ContextDataResult.

        Raises:
            RuntimeError: If symbol data is not in cache.
        """
        symbol = config.symbol
        timeframe = getattr(config, "timeframe", None) or "1h"

        data = self._repository.load_from_cache(
            symbol=symbol,
            timeframe=timeframe,
        )

        if data.empty:
            raise RuntimeError(
                f"IB context data for '{symbol}' ({timeframe}) not found in cache. "
                f"Load it first: ktrdr data load {symbol} {timeframe} "
                f"--start-date {start_date.strftime('%Y-%m-%d')} "
                f"--end-date {end_date.strftime('%Y-%m-%d')}"
            )

        # Filter to requested date range
        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        if hasattr(data.index, "tz") and data.index.tz is not None:
            if start_ts.tz is None:
                start_ts = start_ts.tz_localize("UTC")
            if end_ts.tz is None:
                end_ts = end_ts.tz_localize("UTC")
        data = data[(data.index >= start_ts) & (data.index <= end_ts)]

        logger.info(
            f"IB context '{symbol}' ({timeframe}): {len(data)} bars "
            f"({data.index[0]} to {data.index[-1]})"
        )

        return [
            ContextDataResult(
                source_id=symbol,
                data=data,
                frequency="hourly",
                provider="ib",
                metadata={"symbol": symbol, "timeframe": timeframe},
            )
        ]
