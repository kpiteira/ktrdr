"""Tests for the local training runner orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ktrdr.api.models.operations import OperationMetadata
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.local_runner import LocalTrainingRunner
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.async_infrastructure.progress import GenericProgressManager


class _StubStrategyTrainer:
    def __init__(self, *, result: dict[str, Any] | None = None) -> None:
        self.called_with: dict[str, Any] | None = None
        self.progress_callback = None
        self.cancellation_token = None
        self.result = result or {
            "training_metrics": {"epochs_completed": 2},
            "model_path": "/tmp/model.pt",
        }

    def train_multi_symbol_strategy(self, *args, **kwargs):
        self.called_with = {"args": args, "kwargs": kwargs}
        self.progress_callback = kwargs.get("progress_callback")
        self.cancellation_token = kwargs.get("cancellation_token")

        if self.progress_callback:
            # Emit one batch and one epoch update to exercise the bridge
            batch_metrics = {
                "progress_type": "batch",
                "batch": 0,
                "total_batches_per_epoch": 5,
                "completed_batches": 0,
                "total_batches": 10,
            }
            self.progress_callback(0, 2, batch_metrics)

            epoch_metrics = {
                "progress_type": "epoch",
                "completed_batches": 5,
                "total_batches": 10,
                "total_batches_per_epoch": 5,
            }
            self.progress_callback(0, 2, epoch_metrics)

        return self.result


class _CancellingTrainer(_StubStrategyTrainer):
    def train_multi_symbol_strategy(self, *args, **kwargs):
        self.called_with = {"args": args, "kwargs": kwargs}
        callback = kwargs.get("progress_callback")
        if callback:
            callback(0, 1, {"progress_type": "batch", "batch": 0, "total_batches": 1})
        return {}


class _MutableToken:
    def __init__(self) -> None:
        self.cancelled = False

    def is_cancelled(self) -> bool:
        return self.cancelled


def _make_context(
    total_epochs: int = 2, total_batches: int | None = 10
) -> TrainingOperationContext:
    metadata = OperationMetadata(
        symbol="EURUSD",
        timeframe="1h",
        mode="local",
        parameters={"operation_name": "training", "service_name": "TrainingService"},
    )
    return TrainingOperationContext(
        operation_id="op-456",
        strategy_name="sample",
        strategy_path=Path("/tmp/sample.yaml"),
        strategy_config={},
        symbols=["EURUSD"],
        timeframes=["1h"],
        start_date=None,
        end_date=None,
        training_config={"epochs": total_epochs},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=total_epochs,
        total_batches=total_batches,
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_local_runner_emits_progress_and_returns_summary():
    states: list[Any] = []
    manager = GenericProgressManager(callback=states.append)
    manager.start_operation("training", total_steps=2)

    context = _make_context(total_epochs=2, total_batches=10)
    bridge = TrainingProgressBridge(context=context, progress_manager=manager)

    trainer = _StubStrategyTrainer()
    runner = LocalTrainingRunner(
        context=context,
        progress_bridge=bridge,
        cancellation_token=_MutableToken(),
        strategy_trainer=trainer,
    )

    result = await runner.run()

    assert trainer.called_with is not None
    assert result["training_metrics"]["epochs_completed"] == 2
    # Skip initial start snapshot
    epoch_state = next(
        state for state in states if state.context.get("phase") == "epoch"
    )
    assert epoch_state.percentage == pytest.approx(50.0)
    assert states[-1].context["phase"] == "completed"


@pytest.mark.asyncio
async def test_local_runner_raises_on_cancellation():
    manager = GenericProgressManager(callback=lambda _: None)
    manager.start_operation("training", total_steps=1)

    context = _make_context(total_epochs=1, total_batches=1)
    token = _MutableToken()
    token.cancelled = True
    trainer = _CancellingTrainer()

    bridge = TrainingProgressBridge(
        context=context,
        progress_manager=manager,
        cancellation_token=token,
    )

    runner = LocalTrainingRunner(
        context=context,
        progress_bridge=bridge,
        cancellation_token=token,
        strategy_trainer=trainer,
    )

    with pytest.raises(CancellationError):
        await runner.run()
