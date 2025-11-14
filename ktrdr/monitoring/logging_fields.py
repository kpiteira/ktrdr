"""Standard logging fields for structured logs."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BaseLogFields:
    """Base fields for all logs."""

    def to_extra(self) -> dict[str, Any]:
        """
        Convert to extra dict for logging.

        Excludes None values to keep logs clean.

        Returns:
            Dictionary suitable for logger extra parameter
        """
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class OperationLogFields(BaseLogFields):
    """Standard fields for operation logs."""

    operation_id: str
    operation_type: str
    status: str | None = None


@dataclass
class DataLogFields(BaseLogFields):
    """Standard fields for data-related logs."""

    symbol: str
    timeframe: str
    provider: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass
class TrainingLogFields(BaseLogFields):
    """Standard fields for training logs."""

    strategy: str
    symbol: str
    model_id: str | None = None
    epochs: int | None = None
    batch_size: int | None = None
