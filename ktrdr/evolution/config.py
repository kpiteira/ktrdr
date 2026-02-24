"""Evolution run configuration.

Holds all parameters for an evolution experiment with sensible defaults
matching DESIGN.md and ARCHITECTURE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class DateRange:
    """A start/end date pair for training windows and fitness slices."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(
                f"DateRange start ({self.start}) must be <= end ({self.end})"
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict with ISO date strings."""
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> DateRange:
        """Reconstruct from a serialized dict."""
        return cls(
            start=date.fromisoformat(d["start"]),
            end=date.fromisoformat(d["end"]),
        )


def _default_training_window() -> DateRange:
    return DateRange(start=date(2015, 1, 1), end=date(2020, 12, 31))


def _default_fitness_slices() -> list[DateRange]:
    return [
        DateRange(start=date(2021, 1, 1), end=date(2022, 6, 30)),
        DateRange(start=date(2022, 7, 1), end=date(2023, 12, 31)),
        DateRange(start=date(2024, 1, 1), end=date(2025, 6, 30)),
    ]


@dataclass
class EvolutionConfig:
    """Configuration for an evolution run.

    Defaults match DESIGN.md / ARCHITECTURE.md values.
    """

    # Population
    population_size: int = 12
    generations: int = 5
    kill_rate: float = 0.5
    mutations_per_offspring: int = 1

    # Market
    symbol: str = "EURUSD"
    timeframe: str = "1h"

    # Model
    model: str = "haiku"

    # Date windows
    training_window: DateRange = field(default_factory=_default_training_window)
    fitness_slices: list[DateRange] = field(default_factory=_default_fitness_slices)

    # Fitness lambdas
    lambda_dd: float = 1.0
    lambda_var: float = 1.0
    lambda_complexity: float = 0.1

    # Operational
    poll_interval: int = 30  # seconds
    stale_operation_timeout: int = 1800  # 30 min in seconds
    budget_cap: float = 50.0

    # Reproducibility
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError(
                f"population_size must be >= 2, got {self.population_size}"
            )
        if self.generations < 1:
            raise ValueError(f"generations must be >= 1, got {self.generations}")
        if not self.fitness_slices:
            raise ValueError("fitness_slices must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML persistence."""
        return {
            "population_size": self.population_size,
            "generations": self.generations,
            "kill_rate": self.kill_rate,
            "mutations_per_offspring": self.mutations_per_offspring,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "model": self.model,
            "training_window": self.training_window.to_dict(),
            "fitness_slices": [s.to_dict() for s in self.fitness_slices],
            "lambda_dd": self.lambda_dd,
            "lambda_var": self.lambda_var,
            "lambda_complexity": self.lambda_complexity,
            "poll_interval": self.poll_interval,
            "stale_operation_timeout": self.stale_operation_timeout,
            "budget_cap": self.budget_cap,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvolutionConfig:
        """Reconstruct from a serialized dict."""
        return cls(
            population_size=d["population_size"],
            generations=d["generations"],
            kill_rate=d["kill_rate"],
            mutations_per_offspring=d["mutations_per_offspring"],
            symbol=d["symbol"],
            timeframe=d["timeframe"],
            model=d["model"],
            training_window=DateRange.from_dict(d["training_window"]),
            fitness_slices=[DateRange.from_dict(s) for s in d["fitness_slices"]],
            lambda_dd=d["lambda_dd"],
            lambda_var=d["lambda_var"],
            lambda_complexity=d["lambda_complexity"],
            poll_interval=d["poll_interval"],
            stale_operation_timeout=d["stale_operation_timeout"],
            budget_cap=d["budget_cap"],
            seed=d.get("seed"),
        )
