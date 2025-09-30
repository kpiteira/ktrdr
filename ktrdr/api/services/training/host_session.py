"""Host session manager coordinating remote training execution."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from ktrdr import get_logger
from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.progress_bridge import TrainingProgressBridge
from ktrdr.api.services.training.result_aggregator import from_host_run
from ktrdr.async_infrastructure.cancellation import CancellationError, CancellationToken
from ktrdr.training.training_adapter import TrainingAdapter

logger = get_logger(__name__)

_TERMINAL_SUCCESS = {"completed"}
_TERMINAL_FAILURE = {"failed"}
_TERMINAL_CANCELLATION = {"stopped", "cancelled"}


class HostSessionManager:
    """Coordinate host-service training sessions under the orchestrator."""

    def __init__(
        self,
        *,
        adapter: TrainingAdapter,
        context: TrainingOperationContext,
        progress_bridge: TrainingProgressBridge,
        cancellation_token: CancellationToken | None,
        poll_interval: float = 2.0,
        max_poll_interval: float = 10.0,
        backoff_factor: float = 1.5,
        max_retries: int = 3,
    ) -> None:
        self._adapter = adapter
        self._context = context
        self._bridge = progress_bridge
        self._token = cancellation_token
        self._base_poll_interval = max(0.1, poll_interval)
        self._max_poll_interval = max(self._base_poll_interval, max_poll_interval)
        self._backoff_factor = max(1.0, backoff_factor)
        self._max_retries = max(0, max_retries)

        self._current_interval = self._base_poll_interval
        self._last_snapshot: dict[str, Any] | None = None
        self._cancel_sent = False

    async def run(self) -> dict[str, Any]:
        """Start the host session and poll until completion."""
        await self.start_session()
        host_snapshot = await self.poll_session()

        # Aggregate result into standardized format
        return from_host_run(self._context, host_snapshot)

    async def start_session(self) -> str:
        """Start a remote training session through the adapter."""
        self._ensure_not_cancelled()

        start_date = self._context.start_date or "2020-01-01"
        end_date = self._context.end_date or datetime.now(UTC).strftime("%Y-%m-%d")

        logger.info(
            "Starting host training for strategy=%s symbols=%s timeframes=%s",
            self._context.strategy_name,
            self._context.symbols,
            self._context.timeframes,
        )

        response = await self._adapter.train_multi_symbol_strategy(
            strategy_config_path=str(self._context.strategy_path),
            symbols=self._context.symbols,
            timeframes=self._context.timeframes,
            start_date=start_date,
            end_date=end_date,
            validation_split=self._context.training_config.get("validation_split", 0.2),
            data_mode=self._context.training_config.get("data_mode", "local"),
            cancellation_token=self._token,
            training_config=self._context.training_config,
        )

        session_id = response.get("session_id") if isinstance(response, dict) else None
        if not session_id:
            raise RuntimeError("Host service did not return a session_id")

        self._context.session_id = session_id
        self._context.metadata.parameters["session_id"] = session_id

        message = f"Host session {session_id} started for {self._context.strategy_name}"
        self._bridge.on_phase("host_start", message=message)

        self._current_interval = self._base_poll_interval
        return session_id

    async def poll_session(self) -> dict[str, Any]:
        """Poll host-service status until a terminal state is reached."""
        if not self._context.session_id:
            raise RuntimeError("Cannot poll host session without a session_id")

        retries = 0
        interval = self._current_interval
        session_id = self._context.session_id

        self._bridge.on_phase(
            "host_polling", message=f"Polling host session {session_id}"
        )

        try:
            while True:
                self._ensure_not_cancelled()

                try:
                    snapshot = await self._adapter.get_training_status(session_id)
                    retries = 0
                    interval = min(
                        self._max_poll_interval, interval * self._backoff_factor
                    )
                except Exception as exc:  # pragma: no cover - network failure path
                    retries += 1
                    if retries > self._max_retries:
                        logger.error(
                            "Polling failed for session %s after %s retries: %s",
                            session_id,
                            retries,
                            exc,
                        )
                        raise
                    logger.warning(
                        "Polling error for session %s (attempt %s/%s): %s",
                        session_id,
                        retries,
                        self._max_retries,
                        exc,
                    )
                    await asyncio.sleep(interval)
                    interval = min(
                        self._max_poll_interval, interval * self._backoff_factor
                    )
                    continue

                self._last_snapshot = snapshot
                self._bridge.on_remote_snapshot(snapshot)

                status = str(snapshot.get("status") or "").lower()
                logger.info(
                    "Host session %s status: %s, progress: %s",
                    session_id,
                    status,
                    snapshot.get("progress", {}),
                )
                if status in _TERMINAL_SUCCESS:
                    self._bridge.on_complete(
                        f"Remote training session {session_id} completed"
                    )
                    return snapshot

                if status in _TERMINAL_CANCELLATION:
                    self._cancel_sent = True
                    self._bridge.on_cancellation(
                        message=f"Remote session {session_id} cancelled",
                        context={"host_status": status},
                    )
                    raise CancellationError("Remote training cancelled")

                if status in _TERMINAL_FAILURE:
                    error_message = snapshot.get("error") or "Remote training failed"
                    self._bridge.on_phase("failed", message=error_message)
                    raise RuntimeError(error_message)

                await asyncio.sleep(interval)
        except CancellationError:
            await self.cancel_session()
            raise

    async def cancel_session(self) -> dict[str, Any]:
        """Issue a stop request to the host service and record cancellation."""
        if not self._context.session_id:
            raise RuntimeError("Cannot cancel host session without a session_id")

        if self._cancel_sent:
            return {
                "session_id": self._context.session_id,
                "status": "cancel_requested",
            }

        self._cancel_sent = True
        logger.info("Sending cancellation to host session %s", self._context.session_id)
        try:
            response = await self._adapter.stop_training(self._context.session_id)
        except Exception as exc:  # pragma: no cover - network failure path
            logger.error(
                "Failed to stop host session %s: %s",
                self._context.session_id,
                exc,
            )
            raise

        self._bridge.on_cancellation(
            message=f"Remote session {self._context.session_id} cancellation requested",
            context={
                "host_status": (
                    response.get("status") if isinstance(response, dict) else None
                )
            },
        )
        return response

    def _ensure_not_cancelled(self) -> None:
        if self._token and self._token.is_cancelled():
            raise CancellationError("Training operation cancelled")
