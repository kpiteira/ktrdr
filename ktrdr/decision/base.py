"""Base classes and enums for trading decisions."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

import pandas as pd


class Signal(Enum):
    """Trading signal types."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Position(Enum):
    """Current position status."""

    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class TradingDecision:
    """Complete trading decision with metadata."""

    signal: Signal
    confidence: float
    timestamp: pd.Timestamp
    reasoning: dict[str, Any]
    current_position: Position

    def __post_init__(self):
        """Validate decision data."""
        if not 0 <= self.confidence <= 1:
            raise ValueError(
                f"Confidence must be between 0 and 1, got {self.confidence}"
            )

        if not isinstance(self.signal, Signal):
            raise ValueError(f"Signal must be a Signal enum, got {type(self.signal)}")

        if not isinstance(self.current_position, Position):
            raise ValueError(
                f"Current position must be a Position enum, got {type(self.current_position)}"
            )
