"""
Column naming standardization utilities for multi-timeframe indicators.

This module provides standardized column naming conventions and utilities
for ensuring consistent naming across different timeframes and indicators.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ktrdr import get_logger

logger = get_logger(__name__)


class ColumnType(Enum):
    """Types of columns in the trading data."""

    OHLCV = "ohlcv"  # Open, High, Low, Close, Volume
    TIMESTAMP = "timestamp"  # Time-related columns
    INDICATOR = "indicator"  # Technical indicators
    FUZZY = "fuzzy"  # Fuzzy membership values
    NEURAL = "neural"  # Neural network outputs
    SIGNAL = "signal"  # Trading signals
    METADATA = "metadata"  # Additional metadata


@dataclass
class ColumnInfo:
    """Information about a standardized column."""

    original_name: str
    standardized_name: str
    column_type: ColumnType
    timeframe: Optional[str] = None
    indicator_type: Optional[str] = None
    parameters: Optional[dict] = None


class ColumnStandardizer:
    """
    Utility class for standardizing column names across multi-timeframe data.

    Naming Conventions:
    - OHLCV: preserved as-is (open, high, low, close, volume)
    - Indicators: {indicator_name}_{parameters}_{timeframe}
    - Fuzzy: {indicator}_{fuzzy_set}_{timeframe}
    - Signals: {signal_type}_{timeframe}

    Examples:
    - RSI_14_1h, SMA_20_4h, MACD_line_12_26_9_1d
    - RSI_oversold_1h, SMA_cross_bullish_4h
    - BUY_signal_1h, confidence_1h
    """

    # Reserved OHLCV column names that should not be modified
    OHLCV_COLUMNS = {"open", "high", "low", "close", "volume", "adj_close"}
    TIMESTAMP_COLUMNS = {"timestamp", "datetime", "time", "date"}
    METADATA_COLUMNS = {"symbol", "exchange", "source", "updated_at"}

    def __init__(self):
        """Initialize the column standardizer."""
        self.column_mapping: dict[str, ColumnInfo] = {}
        self.reverse_mapping: dict[str, str] = {}

    def standardize_indicator_name(
        self, indicator_name: str, timeframe: str, parameters: Optional[dict] = None
    ) -> str:
        """
        Create standardized name for an indicator column.

        Args:
            indicator_name: Base name of the indicator
            timeframe: Timeframe identifier
            parameters: Optional parameters to include in name

        Returns:
            Standardized column name
        """
        # Clean the indicator name
        clean_name = self._clean_name(indicator_name)

        # Add parameters if provided
        if parameters:
            param_parts = []
            for key, value in sorted(parameters.items()):
                if key in [
                    "period",
                    "fast_period",
                    "slow_period",
                    "signal_period",
                    "window",
                ]:
                    param_parts.append(str(value))

            if param_parts:
                clean_name = f"{clean_name}_{'_'.join(param_parts)}"

        # Add timeframe suffix
        return f"{clean_name}_{timeframe}"

    def standardize_fuzzy_name(
        self, indicator_name: str, fuzzy_set: str, timeframe: str
    ) -> str:
        """
        Create standardized name for a fuzzy membership column.

        Args:
            indicator_name: Base indicator name
            fuzzy_set: Fuzzy set name (e.g., 'oversold', 'bullish')
            timeframe: Timeframe identifier

        Returns:
            Standardized fuzzy column name
        """
        clean_indicator = self._clean_name(indicator_name)
        clean_fuzzy = self._clean_name(fuzzy_set)
        return f"{clean_indicator}_{clean_fuzzy}_{timeframe}"

    def standardize_signal_name(self, signal_type: str, timeframe: str) -> str:
        """
        Create standardized name for a signal column.

        Args:
            signal_type: Type of signal (BUY, SELL, HOLD, confidence, etc.)
            timeframe: Timeframe identifier

        Returns:
            Standardized signal column name
        """
        clean_signal = self._clean_name(signal_type)
        return f"{clean_signal}_{timeframe}"

    def standardize_dataframe_columns(
        self,
        columns: list[str],
        timeframe: str,
        column_types: Optional[dict[str, ColumnType]] = None,
    ) -> dict[str, str]:
        """
        Create mapping of original to standardized column names.

        Args:
            columns: List of original column names
            timeframe: Timeframe for these columns
            column_types: Optional mapping of column names to types

        Returns:
            Dictionary mapping original names to standardized names
        """
        mapping = {}

        for col in columns:
            col_lower = col.lower()

            # Preserve OHLCV columns
            if col_lower in self.OHLCV_COLUMNS:
                mapping[col] = col_lower
                continue

            # Preserve timestamp columns
            if col_lower in self.TIMESTAMP_COLUMNS:
                mapping[col] = col_lower
                continue

            # Preserve metadata columns
            if col_lower in self.METADATA_COLUMNS:
                mapping[col] = col_lower
                continue

            # Determine column type
            if column_types and col in column_types:
                col_type = column_types[col]
            else:
                col_type = self._infer_column_type(col)

            # Standardize based on type
            if col_type == ColumnType.INDICATOR:
                standardized = self._standardize_indicator_column(col, timeframe)
            elif col_type == ColumnType.FUZZY:
                standardized = self._standardize_fuzzy_column(col, timeframe)
            elif col_type == ColumnType.SIGNAL:
                standardized = self._standardize_signal_column(col, timeframe)
            else:
                # Default: add timeframe suffix if not already present
                if not col.endswith(f"_{timeframe}"):
                    standardized = f"{self._clean_name(col)}_{timeframe}"
                else:
                    standardized = col

            mapping[col] = standardized

            # Store column info
            self.column_mapping[standardized] = ColumnInfo(
                original_name=col,
                standardized_name=standardized,
                column_type=col_type,
                timeframe=timeframe,
            )

        return mapping

    def _clean_name(self, name: str) -> str:
        """Clean a name for standardization."""
        # Remove special characters, replace with underscores
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        # Remove multiple underscores
        cleaned = re.sub(r"_+", "_", cleaned)
        # Remove leading/trailing underscores
        cleaned = cleaned.strip("_")
        # Convert to lowercase for consistency
        return cleaned.lower()

    def _infer_column_type(self, column_name: str) -> ColumnType:
        """Infer the type of a column from its name."""
        col_lower = column_name.lower()

        # Check for fuzzy patterns first (more specific)
        fuzzy_patterns = [
            r"oversold",
            r"overbought",
            r"neutral",
            r"bullish",
            r"bearish",
            r"strong",
            r"weak",
            r"high",
            r"low",
            r"medium",
        ]

        for pattern in fuzzy_patterns:
            if re.search(pattern, col_lower):
                return ColumnType.FUZZY

        # Check for signal patterns
        signal_patterns = [
            r"signal",
            r"buy",
            r"sell",
            r"hold",
            r"confidence",
            r"probability",
        ]

        for pattern in signal_patterns:
            if re.search(pattern, col_lower):
                return ColumnType.SIGNAL

        # Check for known indicator patterns (less specific, so last)
        indicator_patterns = [
            r"rsi",
            r"sma",
            r"ema",
            r"macd",
            r"bb",
            r"atr",
            r"adx",
            r"stoch",
            r"williams",
            r"cci",
            r"mfi",
            r"obv",
            r"momentum",
        ]

        for pattern in indicator_patterns:
            if re.search(pattern, col_lower):
                return ColumnType.INDICATOR

        # Default to indicator type
        return ColumnType.INDICATOR

    def _standardize_indicator_column(self, column_name: str, timeframe: str) -> str:
        """Standardize an indicator column name."""
        # Parse indicator name and parameters
        indicator_info = self._parse_indicator_name(column_name)

        if indicator_info:
            return self.standardize_indicator_name(
                indicator_info["name"], timeframe, indicator_info.get("parameters")
            )
        else:
            # Fallback: clean name and add timeframe
            clean_name = self._clean_name(column_name)
            return f"{clean_name}_{timeframe}"

    def _standardize_fuzzy_column(self, column_name: str, timeframe: str) -> str:
        """Standardize a fuzzy membership column name."""
        # Try to parse fuzzy column (indicator_fuzzyset format)
        parts = column_name.lower().split("_")

        if len(parts) >= 2:
            # Assume last part is fuzzy set, everything else is indicator
            fuzzy_set = parts[-1]
            indicator = "_".join(parts[:-1])
            return self.standardize_fuzzy_name(indicator, fuzzy_set, timeframe)
        else:
            # Fallback
            clean_name = self._clean_name(column_name)
            return f"{clean_name}_{timeframe}"

    def _standardize_signal_column(self, column_name: str, timeframe: str) -> str:
        """Standardize a signal column name."""
        clean_name = self._clean_name(column_name)
        return self.standardize_signal_name(clean_name, timeframe)

    def _parse_indicator_name(self, column_name: str) -> Optional[dict]:
        """Parse an indicator column name to extract name and parameters."""
        # Common patterns for indicators with parameters
        patterns = [
            r"([a-zA-Z]+)_([a-zA-Z]+)",  # MACD_line, MACD_signal (non-numeric suffix)
            r"([a-zA-Z]+)_(\d+)_(\d+)_(\d+)",  # MACD_12_26_9
            r"([a-zA-Z]+)_(\d+)_(\d+)",  # MACD_12_26
            r"([a-zA-Z]+)_(\d+)",  # RSI_14, SMA_20
        ]

        for pattern in patterns:
            match = re.match(pattern, column_name, re.IGNORECASE)
            if match:
                groups = match.groups()
                name = groups[0]

                # Handle compound names like MACD_line
                if len(groups) > 1 and not groups[1].isdigit():
                    # This is likely a compound name like MACD_line
                    compound_name = f"{groups[0]}_{groups[1]}"
                    return {"name": compound_name, "parameters": None}

                # Try to extract numeric parameters
                parameters = {}
                for i, group in enumerate(groups[1:], 1):
                    if group.isdigit():
                        param_names = [
                            "period",
                            "fast_period",
                            "slow_period",
                            "signal_period",
                        ]
                        if i - 1 < len(param_names):
                            parameters[param_names[i - 1]] = int(group)

                return {"name": name, "parameters": parameters if parameters else None}

        return None

    def get_column_info(self, standardized_name: str) -> Optional[ColumnInfo]:
        """Get information about a standardized column."""
        return self.column_mapping.get(standardized_name)

    def get_original_name(self, standardized_name: str) -> Optional[str]:
        """Get the original name for a standardized column."""
        info = self.column_mapping.get(standardized_name)
        return info.original_name if info else None

    def filter_columns_by_type(
        self, columns: list[str], column_type: ColumnType
    ) -> list[str]:
        """Filter columns by their type."""
        return [
            col
            for col in columns
            if col in self.column_mapping
            and self.column_mapping[col].column_type == column_type
        ]

    def filter_columns_by_timeframe(
        self, columns: list[str], timeframe: str
    ) -> list[str]:
        """Filter columns by their timeframe."""
        return [
            col
            for col in columns
            if col in self.column_mapping
            and self.column_mapping[col].timeframe == timeframe
        ]

    def get_timeframes(self, columns: list[str]) -> set[str]:
        """Get all timeframes present in the column list."""
        timeframes = set()
        for col in columns:
            if col in self.column_mapping:
                tf = self.column_mapping[col].timeframe
                if tf:
                    timeframes.add(tf)
        return timeframes

    def validate_naming_consistency(self, columns: list[str]) -> dict[str, list[str]]:
        """
        Validate naming consistency across columns.

        Returns:
            Dictionary with validation results
        """
        results = {"valid": [], "invalid": [], "warnings": [], "recommendations": []}

        timeframes = self.get_timeframes(columns)

        # Check for consistent timeframe usage
        for tf in timeframes:
            tf_columns = self.filter_columns_by_timeframe(columns, tf)

            # Check for columns that should have timeframe but don't
            for col in columns:
                if col not in self.column_mapping:
                    if not any(col.endswith(f"_{t}") for t in timeframes):
                        if (
                            col.lower() not in self.OHLCV_COLUMNS
                            and col.lower() not in self.TIMESTAMP_COLUMNS
                        ):
                            results["warnings"].append(
                                f"Column '{col}' may need timeframe suffix"
                            )

        # Check for potential duplicates
        base_names = {}
        for col in columns:
            if col in self.column_mapping:
                info = self.column_mapping[col]
                base_name = info.original_name
                if base_name in base_names:
                    base_names[base_name].append(col)
                else:
                    base_names[base_name] = [col]

        for base_name, standardized_names in base_names.items():
            if len(standardized_names) > 1:
                results["recommendations"].append(
                    f"Multiple versions of '{base_name}': {standardized_names}"
                )

        return results


def create_standardized_column_mapping(
    multi_timeframe_data: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    """
    Create standardized column mappings for multi-timeframe data.

    Args:
        multi_timeframe_data: Dict mapping timeframes to lists of column names

    Returns:
        Dict mapping timeframes to column name mappings
    """
    standardizer = ColumnStandardizer()
    mappings = {}

    for timeframe, columns in multi_timeframe_data.items():
        mappings[timeframe] = standardizer.standardize_dataframe_columns(
            columns, timeframe
        )

    return mappings
