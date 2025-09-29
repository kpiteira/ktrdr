"""Tests for the host session manager orchestrating remote training."""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from ktrdr.api.models.operations import OperationMetadata
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.async_infrastructure.cancellation import CancellationError
from ktrdr.async_infrastructure.progress import GenericProgressManager


class _MutableToken:
    def __init__(self) -> None:
        self.cancelled = False

    def is_cancelled(self) -> bool:  # pragma: no cover - trivial accessor
        return self.cancelled


class _StubAdapter:
    def __init__(self, *, status_responses: list[dict[str, Any]]) -> None:
        self.status_responses = list(status_responses)
        self.train_calls: list[dict[str, Any]] = []
        self.stop_calls: list[dict[str, Any]] = []
        self._last_snapshot: dict[str, Any] | None = None

    async def train_multi_symbol_strategy(self, **kwargs) -> dict[str, Any]:
        self.train_calls.append(kwargs)
        return {
            "success": True,
            "session_id": "sess-123",
            "training_started": True,
            "host_service_used": True,
        }

    async def get_training_status(self, session_id: str) -> dict[str, Any]:
        if self.status_responses:
            snapshot = self.status_responses.pop(0)
            self._last_snapshot = snapshot
            return snapshot
        # Repeat the last known snapshot if exhausted
        if self._last_snapshot is not None:
            return self._last_snapshot
        return {
            "session_id": session_id,
            "status": "running",
            "progress": {
                "epoch": 0,
                "total_epochs": 1,
                "batch": 0,
                "total_batches": 1,
                "progress_percent": 0.0,
            },
            "metrics": {"current": {}, "best": {}},
            "resource_usage": {},
            "gpu_usage": {},
            "timestamp": "2024-01-01T00:00:00Z",
        }

    async def stop_training(self, session_id: str) -> dict[str, Any]:
        self.stop_calls.append({"session_id": session_id})
        return {"session_id": session_id, "status": "stopped"}


def _make_context() -> TrainingOperationContext:
    metadata = OperationMetadata(
        symbol="EURUSD",
        timeframe="1h",
        mode="host_service",
        parameters={"operation_name": "training", "service_name": "TrainingService"},
    )
    return TrainingOperationContext(
        operation_id="op-789",
        strategy_name="sample",
        strategy_path=Path("/tmp/sample.yaml"),
        strategy_config={},
        symbols=["EURUSD"],
        timeframes=["1h"],
        start_date=None,
        end_date=None,
        training_config={"epochs": 10, "validation_split": 0.2},
        analytics_enabled=False,
        use_host_service=True,
        training_mode="host_service",
        total_epochs=10,
        total_batches=100,
        metadata=metadata,
    )


@pytest.fixture
def manager_factory():
    from ktrdr.api.services.training.host_session import HostSessionManager

    def _factory(*, adapter: _StubAdapter, token: _MutableToken):
        context = _make_context()
        states: deque[Any] = deque()
        progress = GenericProgressManager(callback=states.append)
        progress.start_operation("training", total_steps=context.total_steps)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=progress,
            cancellation_token=token,
        )
        manager = HostSessionManager(
            adapter=adapter,
            context=context,
            progress_bridge=bridge,
            cancellation_token=token,
            poll_interval=0.0,
            max_poll_interval=0.0,
        )
        return manager, context, states

    return _factory


@pytest.mark.asyncio
async def test_start_session_records_session_id(manager_factory):
    status = {
        "session_id": "sess-123",
        "status": "running",
        "progress": {
            "epoch": 1,
            "total_epochs": 10,
            "batch": 1,
            "total_batches": 100,
            "progress_percent": 1.0,
        },
        "metrics": {"current": {}, "best": {}},
        "resource_usage": {},
        "gpu_usage": {},
        "timestamp": "2024-01-01T00:00:00Z",
    }
    adapter = _StubAdapter(status_responses=[status])
    token = _MutableToken()
    manager, context, states = manager_factory(adapter=adapter, token=token)

    session_id = await manager.start_session()

    assert session_id == "sess-123"
    assert context.session_id == "sess-123"
    assert context.metadata.parameters["session_id"] == "sess-123"
    assert adapter.train_calls  # call recorded

    last_state = states[-1]
    assert last_state.context.get("phase_name") == "host_start"
    assert "sess-123" in last_state.message


@pytest.mark.asyncio
async def test_poll_session_emits_snapshots_and_returns_final_status(manager_factory):
    running = {
        "session_id": "sess-123",
        "status": "running",
        "progress": {
            "epoch": 2,
            "total_epochs": 10,
            "batch": 20,
            "total_batches": 100,
            "progress_percent": 20.0,
        },
        "metrics": {
            "current": {"loss": 0.45},
            "best": {"loss": 0.4},
        },
        "resource_usage": {
            "gpu": {"memory_mb": 2048},
        },
        "gpu_usage": {
            "gpu_memory": {"allocated_mb": 2048, "total_mb": 8192},
        },
        "timestamp": "2024-01-01T00:01:00Z",
    }
    finished = {
        **running,
        "status": "completed",
        "progress": {
            **running["progress"],
            "epoch": 10,
            "batch": 100,
            "progress_percent": 100.0,
        },
        "timestamp": "2024-01-01T00:10:00Z",
    }

    adapter = _StubAdapter(status_responses=[running, finished])
    token = _MutableToken()
    manager, context, states = manager_factory(adapter=adapter, token=token)
    await manager.start_session()

    final_status = await manager.poll_session()

    assert final_status["status"] == "completed"
    assert final_status["progress"]["progress_percent"] == 100.0

    remote_states = [
        state for state in states if state.context.get("phase") == "remote_snapshot"
    ]
    assert remote_states, "Expected remote snapshot progress updates"
    last_snapshot = remote_states[-1]
    assert last_snapshot.percentage == pytest.approx(100.0)
    assert last_snapshot.context.get("host_status") == "completed"
    assert last_snapshot.context.get("host_session_id") == "sess-123"


@pytest.mark.asyncio
async def test_poll_session_stops_remote_training_on_cancellation(manager_factory):
    running = {
        "session_id": "sess-123",
        "status": "running",
        "progress": {
            "epoch": 1,
            "total_epochs": 10,
            "batch": 5,
            "total_batches": 100,
            "progress_percent": 10.0,
        },
        "metrics": {"current": {}, "best": {}},
        "resource_usage": {},
        "gpu_usage": {},
        "timestamp": "2024-01-01T00:00:30Z",
    }
    adapter = _StubAdapter(status_responses=[running, running])
    token = _MutableToken()
    manager, context, states = manager_factory(adapter=adapter, token=token)
    await manager.start_session()

    async def trigger_cancellation():
        await asyncio.sleep(0)
        token.cancelled = True

    asyncio.create_task(trigger_cancellation())

    with pytest.raises(CancellationError):
        await manager.poll_session()

    assert adapter.stop_calls == [{"session_id": "sess-123"}]
    cancelled_states = [
        state for state in states if state.context.get("phase_name") == "cancelled"
    ]
    assert cancelled_states, "Expected cancellation progress update"
    assert cancelled_states[-1].context.get("host_session_id") == "sess-123"
