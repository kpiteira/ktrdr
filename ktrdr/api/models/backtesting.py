"""
Pydantic models for backtesting API endpoints.

This module defines the request and response models for the backtesting API
following the async operations architecture pattern.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class BacktestStartRequest(BaseModel):
    """
    Request model for starting a backtest.

    Following async operations architecture:
    - Returns operation_id for tracking via /operations/* endpoints
    - Uses strategy_name (auto-discovers paths internally)
    - Supports commission and slippage parameters
    - Symbol/timeframe are optional - if not provided, read from strategy config
    """

    strategy_name: str
    symbol: Optional[str] = (
        None  # Optional - backend reads from strategy config if None
    )
    timeframe: Optional[str] = (
        None  # Optional - backend reads from strategy config if None
    )
    start_date: str  # ISO format: "YYYY-MM-DD"
    end_date: str  # ISO format: "YYYY-MM-DD"
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.001
    model_path: Optional[str] = None  # Explicit model path (for v3 models)

    @field_validator("strategy_name")
    @classmethod
    def validate_strategy_name(cls, v: str) -> str:
        """Validate that strategy_name is not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("symbol", "timeframe")
    @classmethod
    def validate_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        """Validate that optional string fields are not empty if provided."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Field cannot be empty if provided")
        return v.strip() if v else None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate that date strings can be parsed."""
        try:
            # Validate date format by attempting to parse
            datetime.fromisoformat(v)
            return v
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {v}") from e

    @field_validator("initial_capital")
    @classmethod
    def validate_positive_capital(cls, v: float) -> float:
        """Validate that initial capital is positive."""
        if v <= 0:
            raise ValueError("Initial capital must be positive")
        return v


class BacktestStartResponse(BaseModel):
    """
    Response model for backtest start endpoint.

    Returns operation_id immediately. Clients poll for progress via:
      GET /operations/{operation_id}

    Following async operations architecture pattern (same as training).
    """

    success: bool
    operation_id: str
    status: str
    message: str
    symbol: str
    timeframe: str
    mode: Optional[str] = None  # "local" or "remote"
