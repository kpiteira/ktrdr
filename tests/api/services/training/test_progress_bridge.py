"""Tests for the training progress bridge integration."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from ktrdr.api.models.operations import OperationMetadata
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.async_infrastructure.progress import GenericProgressManager


class _DummyToken:
    def __init__(self, cancelled: bool = False) -> None:
        self._cancelled = cancelled

    def is_cancelled(self) -> bool:  # pragma: no cover - trivial accessor
        return self._cancelled


def _make_context(
    total_epochs: int = 5, total_batches: int | None = 50
) -> TrainingOperationContext:
    metadata = OperationMetadata(
        symbol="EURUSD",
        timeframe="1h",
        mode="local",
        parameters={"operation_name": "training", "service_name": "TrainingService"},
    )
    return TrainingOperationContext(
        operation_id="op-123",
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


class TestTrainingProgressBridge:
    """Behaviour tests for the training progress bridge."""

    def test_epoch_and_batch_updates_compute_percentage(self):
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
            batch_update_stride=1,
        )

        # Simulate early batch progress
        batch_metrics = {
            "progress_type": "batch",
            "batch": 0,
            "total_batches_per_epoch": 10,
            "completed_batches": 0,
            "total_batches": 50,
            "train_loss": 0.42,
        }
        bridge.on_batch(epoch=0, batch=0, total_batches=10, metrics=batch_metrics)

        first_state = states[-1]
        assert first_state.current_step == 0
        assert first_state.items_processed == 1  # includes processed batch
        assert first_state.percentage == pytest.approx(2.0)
        assert first_state.context["current_item"] == "Epoch 1 · Batch 1/10"

        # Complete the epoch
        epoch_metrics = {
            "progress_type": "epoch",
            "total_batches": 50,
            "completed_batches": 10,
            "total_batches_per_epoch": 10,
            "train_loss": 0.35,
            "val_accuracy": 0.78,
        }
        bridge.on_epoch(epoch=0, total_epochs=5, metrics=epoch_metrics)

        epoch_state = states[-1]
        assert epoch_state.current_step == 1
        assert epoch_state.percentage == pytest.approx(20.0)
        assert epoch_state.context["epoch_metrics"]["val_accuracy"] == 0.78
        assert epoch_state.context["phase"] == "epoch"

    def test_batch_throttling_skips_intermediate_updates(self):
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=4)

        context = _make_context(total_epochs=4, total_batches=40)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
            batch_update_stride=5,
        )

        batch_metrics = {
            "progress_type": "batch",
            "total_batches_per_epoch": 10,
            "total_batches": 40,
            "train_loss": 0.6,
        }

        for batch in range(9):
            bridge.on_batch(
                epoch=0,
                batch=batch,
                total_batches=10,
                metrics={**batch_metrics, "batch": batch},
            )

        batch_states = [
            state for state in list(states)[1:] if state.context.get("phase") == "batch"
        ]
        emitted_batches = [s.context.get("batch_index") for s in batch_states]
        assert emitted_batches == [0, 4, 9]

    def test_cancellation_raises_before_emitting(self):
        token = _DummyToken(cancelled=True)
        manager = GenericProgressManager(callback=lambda _: None)
        manager.start_operation("training", total_steps=2)

        context = _make_context(total_epochs=2, total_batches=20)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
            cancellation_token=token,
        )

        with pytest.raises(CancellationError):
            bridge.on_batch(
                epoch=0,
                batch=0,
                total_batches=10,
                metrics={"progress_type": "batch", "batch": 0, "total_batches": 20},
            )

    def test_remote_snapshot_updates_progress_state(self):
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        context.session_id = "sess-999"
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        snapshot = {
            "session_id": "sess-999",
            "status": "running",
            "progress": {
                "epoch": 3,
                "total_epochs": 5,
                "batch": 120,
                "total_batches": 250,
                "progress_percent": 60.0,
            },
            "metrics": {
                "current": {"loss": 0.34},
                "best": {"loss": 0.30},
            },
            "gpu_usage": {
                "gpu_memory": {"allocated_mb": 4096, "total_mb": 12288},
            },
            "resource_usage": {
                "system_memory": {"process_mb": 2048},
            },
            "timestamp": "2024-01-01T12:00:00Z",
        }

        bridge.on_remote_snapshot(snapshot)

        last_state = states[-1]
        assert last_state.percentage == pytest.approx(60.0)
        assert last_state.current_step == 3
        assert last_state.context.get("host_status") == "running"
        assert last_state.context.get("host_session_id") == "sess-999"
        assert last_state.context.get("gpu_usage") == snapshot["gpu_usage"]

    def test_on_cancellation_emits_even_when_token_cancelled(self):
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=2)

        context = _make_context(total_epochs=2, total_batches=20)
        context.session_id = "sess-555"
        token = _DummyToken(cancelled=True)

        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
            cancellation_token=token,
        )

        bridge.on_cancellation(message="Cancelled by user")

        last_state = states[-1]
        assert last_state.context.get("phase_name") == "cancelled"
        assert last_state.context.get("host_session_id") == "sess-555"
        assert last_state.message == "Cancelled by user"
