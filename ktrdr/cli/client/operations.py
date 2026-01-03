"""Operations execution module for long-running CLI operations.

This module provides the core polling loop for executing long-running
operations with progress callbacks and cancellation support.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol

from ktrdr.logging import get_logger

if TYPE_CHECKING:
    from ktrdr.cli.client.async_client import AsyncCLIClient

logger = get_logger(__name__)

# Terminal states that end the poll loop
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


class OperationAdapter(Protocol):
    """Protocol for operation adapters.

    This matches the existing adapter pattern from operation_adapters.py.
    """

    def get_start_endpoint(self) -> str:
        """Return endpoint to start the operation."""
        ...

    def get_start_payload(self) -> dict[str, Any]:
        """Return payload for starting the operation."""
        ...

    def parse_start_response(self, response: dict[str, Any]) -> str:
        """Extract operation ID from start response."""
        ...


async def execute_operation(
    client: "AsyncCLIClient",
    adapter: OperationAdapter,
    on_progress: Optional[Callable[[int, str], None]] = None,
    poll_interval: float = 0.3,
) -> dict[str, Any]:
    """Execute a long-running operation with polling.

    This function starts an operation via the adapter, then polls until
    it reaches a terminal state (completed, failed, cancelled).

    Args:
        client: AsyncCLIClient instance for HTTP requests
        adapter: Operation adapter defining endpoints and payload
        on_progress: Optional callback invoked with (progress_pct, message)
        poll_interval: Seconds between status polls

    Returns:
        Final operation result dict with status and any result data

    Raises:
        APIError: If the start request fails
        ConnectionError: If cannot connect to server
        TimeoutError: If requests time out
    """
    # Start the operation
    start_response = await client.post(
        adapter.get_start_endpoint(),
        json=adapter.get_start_payload(),
    )

    # Extract operation ID
    operation_id = adapter.parse_start_response(start_response)
    logger.debug(f"Operation started: {operation_id}")

    # Poll until terminal state
    status_endpoint = f"/operations/{operation_id}"

    try:
        while True:
            status_response = await client.get(status_endpoint)

            # Handle unsuccessful response
            if not status_response.get("success"):
                logger.warning(f"Polling returned unsuccessful: {status_response}")
                await asyncio.sleep(poll_interval)
                continue

            operation_data = status_response.get("data", {})
            status = operation_data.get("status")

            logger.debug(f"Operation {operation_id} status: {status}")

            # Invoke progress callback if provided
            if on_progress and status not in TERMINAL_STATES:
                progress_info = operation_data.get("progress", {})
                percentage = progress_info.get("percentage", 0)
                current_step = progress_info.get("current_step", "Working...")
                message = f"Status: {status} - {current_step}"
                on_progress(percentage, message)

            # Check for terminal states
            if status in TERMINAL_STATES:
                logger.debug(
                    f"Operation {operation_id} reached terminal state: {status}"
                )
                return operation_data

            # Continue polling
            await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        # Handle cancellation - send DELETE to backend
        logger.debug(
            f"Operation {operation_id} cancelled, sending cancellation request"
        )

        try:
            await client.delete(status_endpoint, timeout=5.0)
        except Exception as e:
            logger.warning(f"Failed to send cancellation request: {e}")

        return {"status": "cancelled", "operation_id": operation_id}
