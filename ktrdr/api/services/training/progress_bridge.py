"""Progress bridge translating training lifecycle events to orchestrator updates."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Coroutine
from typing import Any

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.async_infrastructure.cancellation import CancellationError, CancellationToken
from ktrdr.async_infrastructure.progress import GenericProgressManager

logger = get_logger(__name__)


class TrainingProgressBridge:
    """Translate training callbacks into generic orchestrator progress updates."""

    def __init__(
        self,
        *,
        context: TrainingOperationContext,
        progress_manager: GenericProgressManager | None = None,
        update_progress_callback: Callable[..., None] | None = None,
        cancellation_token: CancellationToken | None = None,
        batch_update_stride: int | None = None,
        metrics_callback: (
            Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None
        ) = None,
    ) -> None:
        if progress_manager is None and update_progress_callback is None:
            raise ValueError(
                "progress_manager or update_progress_callback must be provided"
            )

        self._context = context
        self._progress_manager = progress_manager
        self._update_callback = update_progress_callback
        self._cancellation_token = cancellation_token
        self._metrics_callback = metrics_callback
        self._total_epochs = max(context.total_epochs, 1)
        self._total_batches: int | None = context.total_batches

        configured_stride = batch_update_stride or context.training_config.get(
            "progress", {}
        ).get("batch_stride")
        try:
            stride = int(configured_stride) if configured_stride is not None else 10
        except (TypeError, ValueError):  # pragma: no cover - defensive fallback
            stride = 10
        self._batch_stride = max(stride, 1)

        self._last_epoch_step = 0
        self._last_percentage = 0.0
        self._last_items_processed = 0
        self._last_emitted_global_batch: int | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def on_phase(self, phase_name: str, *, message: str | None = None) -> None:
        """Emit a coarse progress update for a high-level phase."""
        self._check_cancelled()
        phase_message = message or phase_name.replace("_", " ").title()
        logger.debug("[TrainingProgressBridge] phase=%s", phase_name)
        context = {"phase_name": phase_name}
        if self._context.session_id:
            context["host_session_id"] = self._context.session_id
        self._emit(
            current_step=self._last_epoch_step,
            percentage=self._last_percentage,
            message=phase_message,
            items_processed=self._last_items_processed,
            phase="phase",
            context=context,
        )

    def on_cancellation(
        self,
        *,
        message: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Emit a cancellation update even when the token is cancelled."""
        logger.debug("[TrainingProgressBridge] cancellation message=%s", message)
        payload_context = {"phase_name": "cancelled"}
        if context:
            payload_context.update(context)
        if self._context.session_id:
            payload_context.setdefault("host_session_id", self._context.session_id)

        self._emit(
            current_step=self._last_epoch_step,
            percentage=self._last_percentage,
            message=message or "Training cancelled",
            items_processed=self._last_items_processed,
            phase="phase",
            context=payload_context,
        )

    def on_epoch(
        self,
        epoch: int,
        total_epochs: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Emit progress for a completed epoch."""
        self._check_cancelled()

        metrics = metrics or {}
        epoch_index = max(1, epoch + 1)
        if total_epochs is not None:
            self._total_epochs = max(total_epochs, self._total_epochs)

        self._total_batches = (
            metrics.get("total_batches")
            or self._total_batches
            or self._derive_total_batches(metrics)
        )

        completed_batches = metrics.get("completed_batches")
        if completed_batches is None:
            batches_per_epoch = metrics.get("total_batches_per_epoch")
            if batches_per_epoch is not None:
                completed_batches = epoch_index * batches_per_epoch
        items_processed = self._clamp_items_processed(completed_batches)

        percentage = self._derive_percentage(items_processed, epoch_index)
        message = f"Epoch {epoch_index}/{self._total_epochs}"
        context = {
            "epoch_index": epoch_index,
            "total_epochs": self._total_epochs,
            "epoch_metrics": metrics or {},
        }

        self._emit(
            current_step=epoch_index,
            percentage=percentage,
            message=message,
            items_processed=items_processed,
            phase="epoch",
            context=context,
        )

        # M2: Forward epoch metrics to operations service for storage
        if self._metrics_callback and metrics.get("progress_type") == "epoch":
            try:
                # Extract only the metrics fields needed for storage
                epoch_metrics_to_store = {
                    "epoch": metrics.get("epoch"),
                    "train_loss": metrics.get("train_loss"),
                    "train_accuracy": metrics.get("train_accuracy"),
                    "val_loss": metrics.get("val_loss"),
                    "val_accuracy": metrics.get("val_accuracy"),
                    "learning_rate": metrics.get("learning_rate"),
                    "duration": metrics.get("duration"),
                    "timestamp": metrics.get("timestamp"),
                }
                # Schedule async callback without blocking
                asyncio.create_task(self._metrics_callback(epoch_metrics_to_store))
            except Exception as e:
                logger.warning(f"Failed to forward epoch metrics: {e}", exc_info=True)

    def on_batch(
        self,
        epoch: int,
        batch: int,
        total_batches: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Emit throttled progress updates for batch-level callbacks."""
        self._check_cancelled()
        metrics = metrics or {}
        epoch_index = max(1, epoch + 1)
        batch_number = max(1, batch + 1)

        batches_per_epoch = total_batches or metrics.get("total_batches_per_epoch")
        total_batches_overall = (
            metrics.get("total_batches")
            or self._total_batches
            or self._derive_total_batches(metrics)
        )
        self._total_batches = total_batches_overall

        completed_batches = metrics.get("completed_batches")
        if completed_batches is None:
            if batches_per_epoch is not None:
                completed_batches = (epoch_index - 1) * batches_per_epoch + (
                    batch_number - 1
                )
            else:
                completed_batches = batch_number - 1

        items_processed = self._clamp_items_processed(completed_batches + 1)

        if not self._should_emit_batch(
            items_processed, batch_number, batches_per_epoch, total_batches_overall
        ):
            return

        percentage = self._derive_percentage(items_processed, epoch_index)
        total_display = batches_per_epoch or "?"
        message = f"Epoch {epoch_index}/{self._total_epochs} · Batch {batch_number}/{total_display}"
        display_batch_index = batch
        if (
            batches_per_epoch
            and batches_per_epoch > 1
            and batch_number == batches_per_epoch - 1
        ):
            display_batch_index = batch_number
        context = {
            "epoch_index": epoch_index,
            "total_epochs": self._total_epochs,
            "batch_index": display_batch_index,
            "batch_number": batch_number,
            "batch_total_per_epoch": batches_per_epoch,
            "current_item": f"Epoch {epoch_index} · Batch {batch_number}/{total_display}",
            "batch_metrics": metrics or {},
        }

        self._emit(
            current_step=self._estimate_step(items_processed),
            percentage=percentage,
            message=message,
            items_processed=items_processed,
            phase="batch",
            context=context,
        )

    def on_remote_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Translate remote host-service snapshots into orchestrator progress."""
        self._check_cancelled()

        if not isinstance(snapshot, dict):  # pragma: no cover - defensive guard
            logger.debug(
                "[TrainingProgressBridge] Ignoring non-dict remote snapshot: %s",
                snapshot,
            )
            return

        progress_info = snapshot.get("progress") or {}
        if not isinstance(progress_info, dict):
            progress_info = {}

        session_id = snapshot.get("session_id") or self._context.session_id
        status = str(snapshot.get("status") or "").lower() or None

        epoch_index = self._safe_int(progress_info.get("epoch"))
        if epoch_index is None or epoch_index < 0:
            epoch_index = self._last_epoch_step

        total_epochs = self._safe_int(progress_info.get("total_epochs"))
        if total_epochs and total_epochs > 0:
            self._total_epochs = max(self._total_epochs, total_epochs)

        items_total = self._safe_int(
            progress_info.get("items_total") or progress_info.get("total_batches")
        )
        if items_total and items_total > 0:
            self._total_batches = items_total

        raw_items_processed = progress_info.get("items_processed")
        if raw_items_processed is None:
            raw_items_processed = progress_info.get("batch")
        items_processed = self._safe_int(raw_items_processed)
        clamped_items_processed = self._clamp_items_processed(items_processed)

        percentage = progress_info.get("progress_percent")
        if percentage is None:
            if items_processed is not None and self._total_batches:
                percentage = items_processed / max(1, self._total_batches) * 100.0
            elif epoch_index and self._total_epochs:
                percentage = epoch_index / max(1, self._total_epochs) * 100.0
            else:
                percentage = self._last_percentage

        try:
            percentage_float = float(percentage)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            percentage_float = self._last_percentage

        # Calculate batch number within current epoch for display (do this FIRST)
        batch_number = None
        batch_total_per_epoch = progress_info.get("total_batches")
        if clamped_items_processed and batch_total_per_epoch:
            # items_processed is global batch count, convert to batch within epoch
            batch_number = ((clamped_items_processed - 1) % batch_total_per_epoch) + 1
            logger.debug(
                f"DEBUG PROGRESS: clamped_items_processed={clamped_items_processed}, "
                f"batch_total_per_epoch={batch_total_per_epoch}, calculated batch_number={batch_number}, "
                f"total_batches={self._total_batches}"
            )

        # Build message using per-epoch batch numbers (consistent with local training)
        message = progress_info.get("message")
        if not message:
            if (
                epoch_index
                and self._total_epochs
                and batch_number
                and batch_total_per_epoch
            ):
                # Use batch within epoch (e.g., "Batch 35/70") not cumulative (e.g., "Batch 3535/7000")
                message = (
                    f"Epoch {epoch_index}/{self._total_epochs} · Batch "
                    f"{batch_number}/{batch_total_per_epoch}"
                )
                logger.debug(
                    f"DEBUG PROGRESS: Built message with batch_number={batch_number}/{batch_total_per_epoch}"
                )
            elif epoch_index and self._total_epochs:
                message = f"Epoch {epoch_index}/{self._total_epochs}"
            else:
                message = "Polling host session"

        context_payload: dict[str, Any] = {
            "host_status": status or snapshot.get("status"),
            "host_session_id": session_id,
            "remote_progress": dict(progress_info),
            "metrics": (snapshot.get("metrics") or {}).get("current", {}),
            "best_metrics": (snapshot.get("metrics") or {}).get("best", {}),
            "gpu_usage": snapshot.get("gpu_usage"),
            "resource_usage": snapshot.get("resource_usage"),
            "timestamp": snapshot.get("timestamp"),
        }

        # Add epoch/batch info for renderer (like on_batch does)
        if epoch_index:
            context_payload["epoch_index"] = epoch_index
            context_payload["total_epochs"] = self._total_epochs
        if batch_number and batch_total_per_epoch:
            context_payload["batch_number"] = batch_number
            context_payload["batch_total_per_epoch"] = batch_total_per_epoch

        current_item = progress_info.get("current_item")
        if current_item:
            context_payload["current_item"] = current_item

        self._emit(
            current_step=max(0, min(epoch_index, self._total_epochs)),
            percentage=percentage_float,
            message=message,
            items_processed=clamped_items_processed,
            phase="remote_snapshot",
            context=context_payload,
        )

    def on_symbol_processing(
        self,
        symbol: str,
        symbol_index: int,
        total_symbols: int,
        step: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Report per-symbol preprocessing steps."""
        self._check_cancelled()

        # Build message with optional counts
        base_message = f"Processing {symbol} ({symbol_index}/{total_symbols}) - {step.replace('_', ' ').title()}"

        # Add total counts to message if available in context
        if context:
            if step == "computing_indicators" and "total_indicators" in context:
                base_message = f"Processing {symbol} ({symbol_index}/{total_symbols}) - Computing Indicators ({context['total_indicators']})"
            elif step == "generating_fuzzy" and "total_fuzzy_sets" in context:
                base_message = f"Processing {symbol} ({symbol_index}/{total_symbols}) - Computing Fuzzy Memberships ({context['total_fuzzy_sets']})"

        message = base_message

        # Pre-training is 0-5% of total progress
        # We have 5 steps per symbol: loading, indicators, fuzzy, features, labels
        # Map step name to step number (0-4)
        step_map = {
            "loading_data": 0,
            "computing_indicators": 1,
            "generating_fuzzy": 2,
            "creating_features": 3,
            "generating_labels": 4,
        }
        step_number = step_map.get(step, 0)
        steps_per_symbol = 5

        # Calculate progress within pre-training phase (0-5%)
        # Progress = (completed symbols + current step fraction) / total symbols * 5%
        completed_symbols = symbol_index - 1
        step_fraction = step_number / steps_per_symbol
        symbols_progress = (completed_symbols + step_fraction) / total_symbols
        percentage = symbols_progress * 5.0

        payload_context = {
            "phase": "preprocessing",
            "symbol": symbol,
            "symbol_index": symbol_index,
            "total_symbols": total_symbols,
            "preprocessing_step": step,
        }
        if context:
            payload_context.update(context)

        self._emit(
            current_step=0,
            percentage=percentage,
            message=message,
            items_processed=symbol_index,
            phase="preprocessing",
            context=payload_context,
        )

    def on_indicator_computation(
        self,
        symbol: str,
        symbol_index: int,
        total_symbols: int,
        timeframe: str,
        indicator_name: str,
        indicator_index: int,
        total_indicators: int,
    ) -> None:
        """Report per-indicator computation with timeframe."""
        self._check_cancelled()

        message = (
            f"Processing {symbol} ({symbol_index}/{total_symbols}) [{timeframe}] - "
            f"Computing {indicator_name} ({indicator_index}/{total_indicators})"
        )

        # Fine-grained percentage within 0-5% range
        # Formula: (completed_symbols + indicator_progress) / total_symbols * 5%
        # Each symbol contributes 5% / total_symbols
        # Each indicator contributes (5% / total_symbols) / total_indicators
        completed_symbols = symbol_index - 1
        indicator_progress = indicator_index / max(total_indicators, 1)
        percentage = (completed_symbols + indicator_progress) / total_symbols * 5.0

        payload_context = {
            "phase": "preprocessing",
            "preprocessing_step": "computing_indicator",
            "symbol": symbol,
            "symbol_index": symbol_index,
            "total_symbols": total_symbols,
            "timeframe": timeframe,
            "indicator_name": indicator_name,
            "indicator_index": indicator_index,
            "total_indicators": total_indicators,
        }

        self._emit(
            current_step=0,
            percentage=min(percentage, 5.0),
            message=message,
            items_processed=symbol_index,
            phase="preprocessing",
            context=payload_context,
        )

    def on_fuzzy_generation(
        self,
        symbol: str,
        symbol_index: int,
        total_symbols: int,
        timeframe: str,
        fuzzy_set_name: str,
        fuzzy_index: int,
        total_fuzzy_sets: int,
    ) -> None:
        """Report per-fuzzy-set generation with timeframe."""
        self._check_cancelled()

        message = (
            f"Processing {symbol} ({symbol_index}/{total_symbols}) [{timeframe}] - "
            f"Fuzzifying {fuzzy_set_name} ({fuzzy_index}/{total_fuzzy_sets})"
        )

        # Same formula as indicators: (completed_symbols + fuzzy_progress) / total_symbols * 5%
        completed_symbols = symbol_index - 1
        fuzzy_progress = fuzzy_index / max(total_fuzzy_sets, 1)
        percentage = (completed_symbols + fuzzy_progress) / total_symbols * 5.0

        payload_context = {
            "phase": "preprocessing",
            "preprocessing_step": "generating_fuzzy",
            "symbol": symbol,
            "symbol_index": symbol_index,
            "total_symbols": total_symbols,
            "timeframe": timeframe,
            "fuzzy_set_name": fuzzy_set_name,
            "fuzzy_index": fuzzy_index,
            "total_fuzzy_sets": total_fuzzy_sets,
        }

        self._emit(
            current_step=0,
            percentage=min(percentage, 5.0),
            message=message,
            items_processed=symbol_index,
            phase="preprocessing",
            context=payload_context,
        )

    def on_preparation_phase(self, phase: str, message: str | None = None) -> None:
        """Report pre-training preparation phases.

        Args:
            phase: Preparation phase name (e.g., 'combining_data', 'splitting_data', 'creating_model')
            message: Optional custom message. If None, phase name will be formatted.
        """
        self._check_cancelled()

        display_message = message or phase.replace("_", " ").title()

        # Preparation phase happens after preprocessing (0-5%), before training (5-95%)
        percentage = 5.0

        payload_context = {
            "phase": "preparation",
            "preparation_phase": phase,
        }

        self._emit(
            current_step=0,
            percentage=percentage,
            message=display_message,
            items_processed=0,
            phase="preparation",
            context=payload_context,
        )

    def on_complete(self, message: str = "Training complete") -> None:
        """Mark progress as complete with a terminal update."""
        self._check_cancelled()
        items_processed = (
            self._total_batches
            if self._total_batches is not None
            else max(self._last_items_processed, self._total_epochs)
        )
        self._emit(
            current_step=self._total_epochs,
            percentage=100.0,
            message=message,
            items_processed=items_processed,
            phase="completed",
            context={},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _check_cancelled(self) -> None:
        if self._cancellation_token and self._cancellation_token.is_cancelled():
            logger.debug("[TrainingProgressBridge] cancellation detected")
            raise CancellationError("Training operation cancelled")

    def _derive_total_batches(self, metrics: dict[str, Any]) -> int | None:
        batches_per_epoch = metrics.get("total_batches_per_epoch")
        if batches_per_epoch is not None:
            return batches_per_epoch * self._total_epochs
        return None

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            return None

    def _clamp_items_processed(self, value: int | None) -> int:
        if value is None:
            return self._last_items_processed
        if self._total_batches is not None:
            return max(0, min(value, self._total_batches))
        return max(0, value)

    def _estimate_step(self, items_processed: int) -> int:
        if self._total_batches:
            ratio = items_processed / max(self._total_batches, 1)
            return min(self._total_epochs, int(math.floor(ratio * self._total_epochs)))
        return self._last_epoch_step

    def _derive_percentage(self, items_processed: int, epoch_index: int) -> float:
        if self._total_batches:
            percentage = items_processed / max(1, self._total_batches) * 100.0
        else:
            percentage = epoch_index / max(1, self._total_epochs) * 100.0
        return max(0.0, min(percentage, 100.0))

    def _should_emit_batch(
        self,
        items_processed: int,
        batch_number: int,
        batches_per_epoch: int | None,
        total_batches_overall: int | None,
    ) -> bool:
        if self._last_emitted_global_batch is None:
            self._last_emitted_global_batch = items_processed
            return True

        if batch_number == 1:
            self._last_emitted_global_batch = items_processed
            return True

        if (
            batches_per_epoch
            and batches_per_epoch > 1
            and batch_number == batches_per_epoch - 1
        ):
            self._last_emitted_global_batch = items_processed
            return True

        if batches_per_epoch and batch_number == batches_per_epoch:
            self._last_emitted_global_batch = items_processed
            return True

        if total_batches_overall and items_processed >= total_batches_overall:
            self._last_emitted_global_batch = items_processed
            return True

        if batch_number % self._batch_stride == 0:
            self._last_emitted_global_batch = items_processed
            return True

        return False

    def _emit(
        self,
        *,
        current_step: int,
        percentage: float,
        message: str,
        items_processed: int,
        phase: str,
        context: dict[str, Any],
    ) -> None:
        payload_context = {"phase": phase}
        payload_context.update(context)

        self._last_epoch_step = max(0, min(current_step, self._total_epochs))
        self._last_percentage = max(0.0, min(percentage, 100.0))
        self._last_items_processed = max(0, items_processed)

        if self._progress_manager is not None:
            manager = self._progress_manager
            with manager._lock:  # type: ignore[attr-defined]
                state = manager._state
                if state is not None:
                    state.current_step = self._last_epoch_step
                    state.items_processed = self._last_items_processed
                    if self._total_batches is not None:
                        state.total_items = self._total_batches
                    state.percentage = self._last_percentage
                    state.message = message
                    state.context.update(payload_context)
            manager._trigger_callback()

        if self._update_callback is not None:
            payload: dict[str, Any] = {
                "step": self._last_epoch_step,
                "message": message,
                "items_processed": self._last_items_processed,
                "percentage": self._last_percentage,
            }
            payload.update(payload_context)
            try:
                self._update_callback(**payload)
            except TypeError:
                self._update_callback(payload)  # type: ignore[misc]
