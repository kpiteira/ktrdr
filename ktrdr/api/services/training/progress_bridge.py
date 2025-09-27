"""Stub progress bridge for orchestrated training operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ktrdr import get_logger
from ktrdr.async_infrastructure.progress import GenericProgressManager

logger = get_logger(__name__)


class TrainingProgressBridge:
    """Placeholder progress bridge wiring training events to the orchestrator."""

    def __init__(
        self,
        *,
        progress_manager: GenericProgressManager | None = None,
        update_progress_callback: Callable[..., None] | None = None,
        total_steps: int = 1,
    ) -> None:
        if progress_manager is None and update_progress_callback is None:
            raise ValueError(
                "progress_manager or update_progress_callback must be provided"
            )

        self._progress_manager = progress_manager
        self._update_callback = update_progress_callback
        self._total_steps = max(total_steps, 1)

    def on_phase(self, phase_name: str) -> None:
        """Emit a coarse progress update for a named phase."""
        logger.debug("[TrainingProgressBridge] phase=%s", phase_name)
        self._emit_progress(
            step=0,
            message=f"Phase: {phase_name}",
            context={"phase": phase_name},
        )

    def on_epoch(
        self,
        epoch: int,
        total_epochs: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Stub epoch update (no fine-grained percentage yet)."""
        message = f"Epoch {epoch}"
        context: dict[str, Any] = {"phase": "epoch", "epoch": epoch}
        if total_epochs is not None:
            message = f"Epoch {epoch}/{total_epochs}"
            context["total_epochs"] = total_epochs
        if metrics:
            context["metrics"] = metrics

        logger.debug("[TrainingProgressBridge] epoch=%s total=%s", epoch, total_epochs)
        self._emit_progress(step=0, message=message, context=context)

    def on_batch(
        self,
        epoch: int,
        batch: int,
        total_batches: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Batch updates are ignored in the stub to avoid noisy progress spam."""
        logger.debug(
            "[TrainingProgressBridge] batch update ignored (epoch=%s batch=%s total=%s)",
            epoch,
            batch,
            total_batches,
        )
        # Intentional no-op for the stub implementation

    def on_remote_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Handle remote host-service snapshots (stubbed)."""
        logger.debug("[TrainingProgressBridge] remote snapshot=%s", snapshot)
        self._emit_progress(
            step=0,
            message="Remote progress update",
            context={"phase": "remote_snapshot", "snapshot": snapshot},
        )

    def on_complete(self, message: str = "Training complete") -> None:
        """Mark progress as complete with a single 100% update."""
        logger.debug("[TrainingProgressBridge] completing training")
        self._emit_progress(
            step=self._total_steps,
            message=message,
            context={"phase": "completed"},
        )

    def _emit_progress(
        self,
        *,
        step: int,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Send progress to whichever sink the bridge was configured with."""
        if context is None:
            context = {}

        if self._progress_manager is not None:
            self._progress_manager.update_progress(
                step=max(step, 0),
                message=message,
                items_processed=min(max(step, 0), self._total_steps),
                context=context,
            )

        if self._update_callback is not None:
            try:
                self._update_callback(
                    step=max(step, 0),
                    message=message,
                    items_processed=min(max(step, 0), self._total_steps),
                    **context,
                )
            except TypeError:
                # Fallback if consumer does not accept keyword context payload
                self._update_callback(
                    step=max(step, 0),
                    message=message,
                    items_processed=min(max(step, 0), self._total_steps),
                )
