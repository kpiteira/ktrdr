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

    def test_on_symbol_processing_emits_preprocessing_progress(self):
        """Test symbol-level preprocessing progress reporting."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test processing first symbol - loading data (step 0/5)
        bridge.on_symbol_processing(
            symbol="AAPL",
            symbol_index=1,
            total_symbols=5,
            step="loading_data",
        )

        first_state = states[-1]
        assert first_state.message == "Processing AAPL (1/5) - Loading Data"
        assert first_state.context["phase"] == "preprocessing"
        assert first_state.context["symbol"] == "AAPL"
        assert first_state.context["symbol_index"] == 1
        assert first_state.context["total_symbols"] == 5
        assert first_state.context["preprocessing_step"] == "loading_data"
        # First symbol (0 completed), step 0/5 -> (0 + 0/5) / 5 * 5% = 0%
        assert first_state.percentage == pytest.approx(0.0)
        assert first_state.items_processed == 1

        # Test processing second symbol - computing indicators (step 1/5)
        bridge.on_symbol_processing(
            symbol="TSLA",
            symbol_index=2,
            total_symbols=5,
            step="computing_indicators",
        )

        second_state = states[-1]
        assert second_state.message == "Processing TSLA (2/5) - Computing Indicators"
        assert second_state.context["symbol"] == "TSLA"
        assert second_state.context["preprocessing_step"] == "computing_indicators"
        # Second symbol (1 completed), step 1/5 -> (1 + 1/5) / 5 * 5% = 1.2%
        assert second_state.percentage == pytest.approx(1.2)

        # Test processing last symbol - generating labels (step 4/5)
        bridge.on_symbol_processing(
            symbol="MSFT",
            symbol_index=5,
            total_symbols=5,
            step="generating_labels",
        )

        last_state = states[-1]
        assert last_state.message == "Processing MSFT (5/5) - Generating Labels"
        # Fifth symbol (4 completed), step 4/5 -> (4 + 4/5) / 5 * 5% = 4.8%
        assert last_state.percentage == pytest.approx(4.8)

    def test_on_symbol_processing_with_additional_context(self):
        """Test symbol processing includes additional context."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        bridge.on_symbol_processing(
            symbol="AAPL",
            symbol_index=1,
            total_symbols=3,
            step="loading_data",
            context={"timeframes": ["1h", "4h", "1d"]},
        )

        state = states[-1]
        assert state.context["timeframes"] == ["1h", "4h", "1d"]
        assert state.context["preprocessing_step"] == "loading_data"

    def test_on_symbol_processing_cancellation_check(self):
        """Test symbol processing respects cancellation token."""
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
            bridge.on_symbol_processing(
                symbol="AAPL",
                symbol_index=1,
                total_symbols=5,
                step="loading_data",
            )

    def test_on_indicator_computation_emits_granular_progress(self):
        """Test per-indicator computation progress reporting."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test first indicator on first symbol
        bridge.on_indicator_computation(
            symbol="AAPL",
            symbol_index=1,
            total_symbols=5,
            timeframe="1h",
            indicator_name="RSI",
            indicator_index=1,
            total_indicators=40,
        )

        first_state = states[-1]
        assert (
            first_state.message
            == "Processing AAPL (1/5) [1h] - Computing RSI (1/40)"
        )
        assert first_state.context["phase"] == "preprocessing"
        assert first_state.context["preprocessing_step"] == "computing_indicator"
        assert first_state.context["symbol"] == "AAPL"
        assert first_state.context["symbol_index"] == 1
        assert first_state.context["total_symbols"] == 5
        assert first_state.context["timeframe"] == "1h"
        assert first_state.context["indicator_name"] == "RSI"
        assert first_state.context["indicator_index"] == 1
        assert first_state.context["total_indicators"] == 40
        # First symbol (0 completed), first indicator (1/40) -> (0 + 1/40) / 5 * 5% = 0.025%
        assert first_state.percentage == pytest.approx(0.025, abs=0.01)
        assert first_state.items_processed == 1

        # Test middle indicator on second symbol
        bridge.on_indicator_computation(
            symbol="TSLA",
            symbol_index=2,
            total_symbols=5,
            timeframe="4h",
            indicator_name="MACD",
            indicator_index=20,
            total_indicators=40,
        )

        second_state = states[-1]
        assert (
            second_state.message
            == "Processing TSLA (2/5) [4h] - Computing MACD (20/40)"
        )
        assert second_state.context["timeframe"] == "4h"
        assert second_state.context["indicator_name"] == "MACD"
        assert second_state.context["indicator_index"] == 20
        # Second symbol (1 completed), 20th indicator (20/40=0.5) -> (1 + 0.5) / 5 * 5% = 1.5%
        assert second_state.percentage == pytest.approx(1.5, abs=0.01)

        # Test last indicator on last symbol
        bridge.on_indicator_computation(
            symbol="MSFT",
            symbol_index=5,
            total_symbols=5,
            timeframe="1d",
            indicator_name="EMA",
            indicator_index=40,
            total_indicators=40,
        )

        last_state = states[-1]
        assert (
            last_state.message
            == "Processing MSFT (5/5) [1d] - Computing EMA (40/40)"
        )
        # Last symbol (4 completed), last indicator (40/40=1.0) -> (4 + 1.0) / 5 * 5% = 5.0%
        assert last_state.percentage == pytest.approx(5.0, abs=0.01)

    def test_on_indicator_computation_percentage_calculation(self):
        """Test indicator computation calculates percentages correctly within 0-5% range."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test various progress points
        test_cases = [
            # (symbol_idx, total_symbols, indicator_idx, total_indicators, expected_percentage)
            (1, 5, 1, 40, 0.025),  # First symbol, first indicator: (0 + 1/40) / 5 * 5% = 0.025%
            (1, 5, 40, 40, 1.0),  # First symbol, last indicator: (0 + 1) / 5 * 5% = 1.0%
            (3, 5, 20, 40, 2.5),  # Middle symbol, middle indicator: (2 + 20/40) / 5 * 5% = 2.5%
            (5, 5, 40, 40, 5.0),  # Last symbol, last indicator: (4 + 1) / 5 * 5% = 5.0%
        ]

        for symbol_idx, total_symbols, ind_idx, total_indicators, expected_pct in test_cases:
            bridge.on_indicator_computation(
                symbol=f"SYM{symbol_idx}",
                symbol_index=symbol_idx,
                total_symbols=total_symbols,
                timeframe="1h",
                indicator_name=f"IND{ind_idx}",
                indicator_index=ind_idx,
                total_indicators=total_indicators,
            )

            state = states[-1]
            assert state.percentage == pytest.approx(expected_pct, abs=0.01), (
                f"Symbol {symbol_idx}/{total_symbols}, Indicator {ind_idx}/{total_indicators} "
                f"should be {expected_pct}%, got {state.percentage}%"
            )

    def test_on_indicator_computation_cancellation_check(self):
        """Test indicator computation respects cancellation token."""
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
            bridge.on_indicator_computation(
                symbol="AAPL",
                symbol_index=1,
                total_symbols=5,
                timeframe="1h",
                indicator_name="RSI",
                indicator_index=1,
                total_indicators=40,
            )

    def test_on_fuzzy_generation_emits_granular_progress(self):
        """Test per-fuzzy-set generation progress reporting."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test first fuzzy set on first symbol
        bridge.on_fuzzy_generation(
            symbol="AAPL",
            symbol_index=1,
            total_symbols=5,
            timeframe="1h",
            fuzzy_set_name="rsi_14",
            fuzzy_index=1,
            total_fuzzy_sets=40,
        )

        first_state = states[-1]
        assert (
            first_state.message
            == "Processing AAPL (1/5) [1h] - Fuzzifying rsi_14 (1/40)"
        )
        assert first_state.context["phase"] == "preprocessing"
        assert first_state.context["preprocessing_step"] == "generating_fuzzy"
        assert first_state.context["symbol"] == "AAPL"
        assert first_state.context["timeframe"] == "1h"
        assert first_state.context["fuzzy_set_name"] == "rsi_14"
        assert first_state.context["fuzzy_index"] == 1
        assert first_state.context["total_fuzzy_sets"] == 40
        # Same formula as indicators: (0 + 1/40) / 5 * 5% = 0.025%
        assert first_state.percentage == pytest.approx(0.025, abs=0.01)

        # Test middle fuzzy set
        bridge.on_fuzzy_generation(
            symbol="TSLA",
            symbol_index=2,
            total_symbols=5,
            timeframe="4h",
            fuzzy_set_name="macd_standard",
            fuzzy_index=20,
            total_fuzzy_sets=40,
        )

        second_state = states[-1]
        assert (
            second_state.message
            == "Processing TSLA (2/5) [4h] - Fuzzifying macd_standard (20/40)"
        )
        # (1 + 20/40) / 5 * 5% = 1.5%
        assert second_state.percentage == pytest.approx(1.5, abs=0.01)

    def test_on_fuzzy_generation_cancellation_check(self):
        """Test fuzzy generation respects cancellation token."""
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
            bridge.on_fuzzy_generation(
                symbol="AAPL",
                symbol_index=1,
                total_symbols=5,
                timeframe="1h",
                fuzzy_set_name="rsi_14",
                fuzzy_index=1,
                total_fuzzy_sets=40,
            )

    def test_on_preparation_phase_emits_preparation_progress(self):
        """Test preparation phase progress reporting."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test combining data phase
        bridge.on_preparation_phase(
            phase="combining_data",
            message="Combining data from 5 symbols",
        )

        first_state = states[-1]
        assert first_state.message == "Combining data from 5 symbols"
        assert first_state.context["phase"] == "preparation"
        assert first_state.context["preparation_phase"] == "combining_data"
        assert first_state.percentage == pytest.approx(5.0)  # After preprocessing
        assert first_state.items_processed == 0

        # Test splitting data phase
        bridge.on_preparation_phase(
            phase="splitting_data",
            message="Splitting 15847 samples (train/val/test)",
        )

        second_state = states[-1]
        assert second_state.message == "Splitting 15847 samples (train/val/test)"
        assert second_state.context["preparation_phase"] == "splitting_data"
        assert second_state.percentage == pytest.approx(5.0)

        # Test creating model phase
        bridge.on_preparation_phase(
            phase="creating_model",
            message="Creating model (input_dim=256)",
        )

        third_state = states[-1]
        assert third_state.message == "Creating model (input_dim=256)"
        assert third_state.context["preparation_phase"] == "creating_model"
        assert third_state.percentage == pytest.approx(5.0)

    def test_on_preparation_phase_without_message(self):
        """Test preparation phase uses phase name when no message provided."""
        states = deque()
        manager = GenericProgressManager(callback=states.append)
        manager.start_operation("training", total_steps=5)

        context = _make_context(total_epochs=5, total_batches=50)
        bridge = TrainingProgressBridge(
            context=context,
            progress_manager=manager,
        )

        # Test without explicit message - should format phase name
        bridge.on_preparation_phase(phase="combining_data")

        state = states[-1]
        assert state.message == "Combining Data"  # Formatted from phase name
        assert state.context["preparation_phase"] == "combining_data"

    def test_on_preparation_phase_cancellation_check(self):
        """Test preparation phase respects cancellation token."""
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
            bridge.on_preparation_phase(
                phase="combining_data",
                message="Combining data from 5 symbols",
            )
