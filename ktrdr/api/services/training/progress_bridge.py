"""Progress bridge translating training lifecycle events to orchestrator updates."""

from __future__ import annotations

import math
from collections.abc import Callable
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
    ) -> None:
        if progress_manager is None and update_progress_callback is None:
            raise ValueError(
                "progress_manager or update_progress_callback must be provided"
            )

        self._context = context
        self._progress_manager = progress_manager
        self._update_callback = update_progress_callback
        self._cancellation_token = cancellation_token
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
        self._emit(
            current_step=self._last_epoch_step,
            percentage=self._last_percentage,
            message=phase_message,
            items_processed=self._last_items_processed,
            phase="phase",
            context={"phase_name": phase_name},
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
        context = {
            "epoch_index": epoch_index,
            "total_epochs": self._total_epochs,
            "batch_index": batch,
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
        """Handle remote host-service snapshots by forwarding context."""
        self._check_cancelled()
        logger.debug("[TrainingProgressBridge] remote snapshot=%s", snapshot)
        self._emit(
            current_step=self._last_epoch_step,
            percentage=self._last_percentage,
            message="Remote progress update",
            items_processed=self._last_items_processed,
            phase="remote_snapshot",
            context={"snapshot": snapshot},
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
