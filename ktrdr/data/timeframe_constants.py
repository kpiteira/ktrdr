"""
Centralized timeframe constants and utilities.

This module provides shared timeframe definitions and utilities used across
the data management system to ensure consistency.
"""

from datetime import timedelta
import pandas as pd


class TimeframeConstants:
    """Centralized timeframe constants and utilities."""

    # Timeframe to minutes mapping
    TIMEFRAME_MINUTES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,  # 24 hours
        "1w": 10080,  # 7 days
    }

    # Timeframe to pandas Timedelta mapping
    TIMEFRAME_DELTAS = {
        "1m": pd.Timedelta(minutes=1),
        "5m": pd.Timedelta(minutes=5),
        "15m": pd.Timedelta(minutes=15),
        "30m": pd.Timedelta(minutes=30),
        "1h": pd.Timedelta(hours=1),
        "4h": pd.Timedelta(hours=4),
        "1d": pd.Timedelta(days=1),
        "1w": pd.Timedelta(weeks=1),
    }

    # Timeframe to timedelta mapping
    TIMEFRAME_TIMEDELTAS = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
    }

    @classmethod
    def get_minutes(cls, timeframe: str) -> int:
        """Get minutes for a timeframe."""
        return cls.TIMEFRAME_MINUTES.get(timeframe, 60)

    @classmethod
    def get_timedelta(cls, timeframe: str) -> timedelta:
        """Get timedelta for a timeframe."""
        return cls.TIMEFRAME_TIMEDELTAS.get(timeframe, timedelta(hours=1))

    @classmethod
    def get_pandas_timedelta(cls, timeframe: str) -> pd.Timedelta:
        """Get pandas Timedelta for a timeframe."""
        return cls.TIMEFRAME_DELTAS.get(timeframe, pd.Timedelta(hours=1))

    @classmethod
    def is_intraday(cls, timeframe: str) -> bool:
        """Check if timeframe is intraday (< 1 day)."""
        return timeframe in ["1m", "5m", "15m", "30m", "1h", "4h"]

    @classmethod
    def get_supported_timeframes(cls) -> list:
        """Get list of supported timeframes."""
        return list(cls.TIMEFRAME_MINUTES.keys())
