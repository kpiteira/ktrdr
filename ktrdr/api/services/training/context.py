"""Context helpers for orchestrated training operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ktrdr.api.endpoints.strategies import _validate_strategy_config
from ktrdr.api.models.operations import OperationMetadata
from ktrdr.errors import ValidationError

# Default locations where strategy YAML files may live (docker + host paths)
DEFAULT_STRATEGY_PATHS: tuple[Path, ...] = (
    Path("/app/strategies"),
    Path("strategies"),
)


@dataclass(slots=True)
class TrainingOperationContext:
    """Immutable snapshot describing a managed training operation."""

    operation_id: str | None
    strategy_name: str
    strategy_path: Path
    strategy_config: dict[str, Any]
    symbols: list[str]
    timeframes: list[str]
    start_date: str | None
    end_date: str | None
    training_config: dict[str, Any]
    analytics_enabled: bool
    use_host_service: bool
    training_mode: str
    total_epochs: int
    total_batches: int | None
    metadata: OperationMetadata
    session_id: str | None = None

    @property
    def total_steps(self) -> int:
        """Expose the number of coarse progress steps (epochs)."""
        return max(self.total_epochs, 1)


def build_training_context(
    *,
    operation_id: str | None = None,
    strategy_name: str,
    symbols: list[str],
    timeframes: list[str],
    start_date: str | None,
    end_date: str | None,
    detailed_analytics: bool,
    use_host_service: bool,
    strategy_search_paths: Iterable[Path] | None = None,
) -> TrainingOperationContext:
    """Construct a ``TrainingOperationContext`` from user input and config files."""

    strategy_path = _resolve_strategy_path(strategy_name, strategy_search_paths)
    strategy_config = _load_strategy_config(strategy_path)
    _validate_strategy(strategy_config, strategy_name)

    if detailed_analytics:
        _apply_detailed_analytics(strategy_config)

    model_config = strategy_config.get("model", {}) or {}
    training_config = dict(model_config.get("training", {}) or {})
    total_epochs = _extract_total_epochs(training_config)
    total_batches = _extract_total_batches(training_config, total_epochs)
    model_type = model_config.get("type", "mlp")

    metadata = _build_operation_metadata(
        strategy_name=strategy_name,
        strategy_path=strategy_path,
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        model_type=model_type,
        total_epochs=total_epochs,
        use_host_service=use_host_service,
        analytics_enabled=detailed_analytics,
        total_batches=total_batches,
    )

    context = TrainingOperationContext(
        operation_id=operation_id,
        strategy_name=strategy_name,
        strategy_path=strategy_path,
        strategy_config=strategy_config,
        symbols=list(symbols),
        timeframes=list(timeframes),
        start_date=start_date,
        end_date=end_date,
        training_config=training_config,
        analytics_enabled=detailed_analytics,
        use_host_service=use_host_service,
        training_mode="host_service" if use_host_service else "local",
        total_epochs=total_epochs,
        total_batches=total_batches,
        metadata=metadata,
    )
    return context


def _resolve_strategy_path(
    strategy_name: str, strategy_search_paths: Iterable[Path] | None
) -> Path:
    """Locate the strategy YAML file, checking docker + host paths."""

    if Path(strategy_name).is_absolute() or Path(strategy_name).name != strategy_name:
        raise ValidationError(
            "Strategy name must be a file name without directory components"
        )

    candidate_paths: list[Path] = []

    search_roots = (
        list(strategy_search_paths)
        if strategy_search_paths is not None
        else list(DEFAULT_STRATEGY_PATHS)
    )

    strategy_filename = f"{strategy_name}.yaml"

    for root in search_roots:
        root_path = Path(root)
        root_resolved = root_path.resolve(strict=False)

        if not root_resolved.is_dir():
            candidate_paths.append(root_resolved)
            continue

        candidate = (root_resolved / strategy_filename).resolve(strict=False)

        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise ValidationError(
                "Strategy name resolves outside the allowed strategy directory"
            ) from exc

        candidate_paths.append(candidate)
        if candidate.exists():
            return candidate

    searched = ", ".join(str(p) for p in candidate_paths)
    raise ValidationError(
        f"Strategy file not found: {strategy_name}.yaml (searched: {searched})"
    )


def _load_strategy_config(strategy_path: Path) -> dict[str, Any]:
    """Load YAML strategy configuration from disk."""
    try:
        with open(strategy_path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:  # pragma: no cover - defensive guard
        raise ValidationError(f"Failed to parse strategy YAML: {exc}") from exc
    except OSError as exc:  # pragma: no cover - filesystem errors surfaced
        raise ValidationError(f"Unable to read strategy file: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError("Strategy configuration must be a mapping")

    return data


def _validate_strategy(strategy_config: dict[str, Any], strategy_name: str) -> None:
    """Run shared strategy validation and raise on errors."""
    issues = _validate_strategy_config(strategy_config, strategy_name)
    error_messages = [
        f"{issue.category}: {issue.message}"
        for issue in issues
        if getattr(issue, "severity", "").lower() == "error"
    ]

    if error_messages:
        formatted = "\n".join(error_messages)
        raise ValidationError(f"Strategy validation failed:\n{formatted}")


def _apply_detailed_analytics(strategy_config: dict[str, Any]) -> None:
    """Mirror legacy behaviour for enabling detailed analytics."""
    training_section = strategy_config.setdefault("training", {})
    training_section["detailed_analytics"] = True
    training_section["save_intermediate_models"] = True
    training_section["track_gradients"] = True


def _extract_total_epochs(training_config: dict[str, Any]) -> int:
    """Read total epochs, defaulting to 1 for unknown configs."""
    try:
        epochs = int(training_config.get("epochs", 1))
    except (TypeError, ValueError):
        epochs = 1
    return max(epochs, 1)


def _extract_total_batches(
    training_config: dict[str, Any], total_epochs: int
) -> int | None:
    """Derive total batches when configuration provides enough detail."""
    total_batches = training_config.get("total_batches")
    if isinstance(total_batches, int) and total_batches > 0:
        return total_batches

    per_epoch = training_config.get("batches_per_epoch")
    if isinstance(per_epoch, int) and per_epoch > 0 and total_epochs > 0:
        return per_epoch * total_epochs

    return None


def _build_operation_metadata(
    *,
    strategy_name: str,
    strategy_path: Path,
    symbols: list[str],
    timeframes: list[str],
    start_date: str | None,
    end_date: str | None,
    model_type: str,
    total_epochs: int,
    use_host_service: bool,
    analytics_enabled: bool,
    total_batches: int | None,
) -> OperationMetadata:
    """Assemble the OperationMetadata payload for orchestrated training."""

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    parameters: dict[str, Any] = {
        "strategy_name": strategy_name,
        "strategy_path": str(strategy_path),
        "training_type": model_type,
        "symbols": list(symbols),
        "timeframes": list(timeframes),
        "epochs": total_epochs,
        "use_host_service": use_host_service,
        "analytics_enabled": analytics_enabled,
        "training_mode": "host_service" if use_host_service else "local",
    }
    if total_batches is not None:
        parameters["total_batches"] = total_batches

    metadata = OperationMetadata(
        symbol=symbols[0] if symbols else "MULTI",
        timeframe=timeframes[0] if timeframes else None,
        mode="training",
        start_date=start_dt,
        end_date=end_dt,
        parameters=parameters,
    )
    return metadata
