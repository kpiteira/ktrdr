"""
Generic async operation executor for unified CLI operations.

This module provides infrastructure for executing async operations with:
- HTTP client lifecycle management
- Signal handling for graceful cancellation (Ctrl+C)
- Polling the operations API until completion
- Progress display integration
- Error handling and recovery

The executor has ZERO domain knowledge - all operation-specific logic
is delegated to OperationAdapter implementations.
"""

import asyncio
import logging
import signal
from typing import Any, Callable, Optional

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ktrdr.cli.operation_adapters import OperationAdapter
from ktrdr.config.host_services import get_api_base_url
from ktrdr.logging import get_logger

logger = get_logger(__name__)


def _suppress_console_logging() -> tuple[logging.Handler | None, int]:
    """
    Suppress console logging during progress display.

    Rich's Progress display uses cursor control to update a single line.
    If log messages are printed to stdout during progress, they break the display
    and cause new lines to appear instead of updating in place.

    Returns:
        Tuple of (handler, original_level) to restore later, or (None, 0) if not found.
    """
    import sys

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            # Check if this handler writes to stdout
            # (handle both real stdout and test mocks)
            stream = getattr(handler, "stream", None)
            if stream is sys.stdout or getattr(stream, "name", None) == "<stdout>":
                original_level = handler.level
                handler.setLevel(logging.CRITICAL)  # Suppress all but CRITICAL
                return handler, original_level
    return None, 0


def _restore_console_logging(handler: logging.Handler | None, level: int) -> None:
    """Restore console logging to its original level."""
    if handler is not None:
        handler.setLevel(level)


class AsyncOperationExecutor:
    """
    Generic executor for async CLI operations.

    Responsibilities:
    - Manage HTTP client lifecycle
    - Setup/teardown signal handlers for Ctrl+C
    - Poll operations API until completion
    - Integrate with progress display
    - Handle cancellation gracefully
    - Coordinate error handling

    What it DOESN'T know:
    - Which endpoints to call (adapter provides)
    - What parameters to send (adapter provides)
    - How to interpret domain-specific results (adapter handles)
    - Any business logic about specific operations
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        poll_interval: float = 0.3,
        timeout: float = 30.0,
    ):
        """
        Initialize the async operation executor.

        Args:
            base_url: Base URL of the API server (defaults to configured URL)
            poll_interval: Polling interval in seconds (default: 300ms for responsive UI)
            timeout: Default timeout for HTTP requests in seconds
        """
        self.base_url = (base_url or get_api_base_url()).rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.cancelled = False
        self._signal_handler_registered = False

    def _signal_handler(self) -> None:
        """
        Handle SIGINT (Ctrl+C) by setting cancellation flag.

        This is called by the event loop when user presses Ctrl+C.
        We set a flag rather than raising an exception to allow
        graceful cleanup and cancellation request to backend.
        """
        if not self.cancelled:
            self.cancelled = True
            logger.debug("Cancellation requested by user (Ctrl+C)")

    def _setup_signal_handler(self) -> None:
        """
        Register signal handler for graceful cancellation.

        Uses asyncio event loop's signal handling to catch Ctrl+C
        without raising KeyboardInterrupt.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, self._signal_handler)
            self._signal_handler_registered = True
            logger.debug("Signal handler registered for SIGINT")
        except Exception as e:
            logger.warning(f"Failed to register signal handler: {e}")

    def _cleanup_signal_handler(self) -> None:
        """
        Remove signal handler after operation completes.

        Restores default Ctrl+C behavior for the shell.
        """
        if self._signal_handler_registered:
            try:
                loop = asyncio.get_running_loop()
                loop.remove_signal_handler(signal.SIGINT)
                self._signal_handler_registered = False
                logger.debug("Signal handler cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup signal handler: {e}")

    async def _start_operation(
        self,
        adapter: OperationAdapter,
        http_client: httpx.AsyncClient,
    ) -> str:
        """
        Start the operation and return operation_id.

        Args:
            adapter: Operation adapter providing domain-specific logic
            http_client: Async HTTP client

        Returns:
            operation_id to use for polling

        Raises:
            httpx.HTTPError: If request fails
            KeyError: If operation_id cannot be extracted from response
        """
        endpoint = adapter.get_start_endpoint()
        payload = adapter.get_start_payload()
        url = f"{self.base_url}{endpoint}"

        logger.debug(f"Starting operation: POST {url}")
        logger.debug(f"Payload: {payload}")

        response = await http_client.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()

        response_data = response.json()
        operation_id = adapter.parse_start_response(response_data)

        logger.debug(f"Operation started: {operation_id}")
        return operation_id

    async def _poll_until_complete(
        self,
        operation_id: str,
        http_client: httpx.AsyncClient,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
        progress_callback: Optional[Callable[[dict[str, Any]], str]] = None,
    ) -> dict[str, Any]:
        """
        Poll operation status until it reaches a terminal state.

        Args:
            operation_id: Operation ID to poll
            http_client: Async HTTP client
            progress: Optional Rich Progress instance for display
            task_id: Optional task ID for updating progress
            progress_callback: Optional callback to format progress messages

        Returns:
            Final operation status dictionary

        Terminal states: completed, failed, cancelled
        """
        url = f"{self.base_url}/operations/{operation_id}"
        logger.debug(f"Starting polling loop for operation {operation_id}")

        while not self.cancelled:
            try:
                response = await http_client.get(url, timeout=self.timeout)
                response.raise_for_status()
                status_data = response.json()

                if not status_data.get("success"):
                    logger.warning(
                        f"Polling returned unsuccessful response: {status_data}"
                    )
                    await asyncio.sleep(self.poll_interval)
                    continue

                operation_data = status_data.get("data", {})
                status = operation_data.get("status")

                logger.debug(f"Operation {operation_id} status: {status}")

                # Update progress display if enabled
                if progress and task_id is not None:
                    # Get progress percentage
                    progress_info = operation_data.get("progress", {})
                    progress_pct = progress_info.get("percentage", 0)

                    # Format progress message (use callback if provided)
                    if progress_callback:
                        progress_msg = progress_callback(operation_data)
                    else:
                        # Default format
                        current_step = progress_info.get("current_step", "Working...")
                        progress_msg = f"Status: {status} - {current_step}"

                    # Update progress bar
                    progress.update(
                        task_id, completed=progress_pct, description=progress_msg
                    )

                # Check for terminal states
                if status in ("completed", "failed", "cancelled"):
                    logger.debug(
                        f"Operation {operation_id} reached terminal state: {status}"
                    )
                    return operation_data

                # Continue polling
                await asyncio.sleep(self.poll_interval)

            except httpx.HTTPError as e:
                logger.warning(f"Polling error (will retry): {e}")
                await asyncio.sleep(self.poll_interval)
                continue

        # If we get here, operation was cancelled
        logger.debug("Polling loop exited due to cancellation")
        return {"status": "cancelled", "operation_id": operation_id}

    async def _handle_cancellation(
        self,
        operation_id: str,
        http_client: httpx.AsyncClient,
        console: Console,
    ) -> dict[str, Any]:
        """
        Send cancellation request to backend and wait for confirmation.

        Sends DELETE request to cancel the operation, then polls for a short time
        to get the final cancelled status and any results from the backend.

        Args:
            operation_id: Operation ID to cancel
            http_client: Async HTTP client
            console: Rich console for status updates

        Returns:
            Final operation status after cancellation
        """
        cancel_url = f"{self.base_url}/operations/{operation_id}"
        status_url = f"{self.base_url}/operations/{operation_id}"

        logger.debug(f"Sending cancellation request for operation {operation_id}")

        # Send cancellation request
        try:
            response = await http_client.delete(
                cancel_url,
                timeout=5.0,  # Short timeout for cancel
            )

            if response.status_code == 200:
                logger.debug("Cancellation request sent successfully")
                console.print(
                    "[cyan]🔄 Waiting for backend to confirm cancellation...[/cyan]"
                )
            elif response.status_code == 400:
                # Operation may already be finished - that's okay
                logger.debug("Operation already finished (cancel not needed)")
                return {"status": "cancelled", "operation_id": operation_id}
            else:
                logger.warning(f"Cancel request returned status {response.status_code}")
                return {"status": "cancelled", "operation_id": operation_id}

        except httpx.HTTPError as e:
            logger.warning(f"Failed to send cancel request (continuing anyway): {e}")
            return {"status": "cancelled", "operation_id": operation_id}

        # Poll for cancellation confirmation (max 3 seconds)
        max_polls = 10  # 10 * 0.3s = 3 seconds max
        for i in range(max_polls):
            try:
                response = await http_client.get(status_url, timeout=2.0)
                response.raise_for_status()
                status_data = response.json()

                if status_data.get("success"):
                    operation_data = status_data.get("data", {})
                    status = operation_data.get("status")

                    if status == "cancelled":
                        logger.debug(f"Cancellation confirmed after {i+1} polls")
                        return operation_data
                    elif status in ("completed", "failed"):
                        # Operation finished before cancellation took effect
                        logger.debug(
                            f"Operation finished as {status} before cancellation"
                        )
                        return operation_data

                await asyncio.sleep(0.3)

            except httpx.HTTPError as e:
                logger.debug(f"Error polling for cancellation status: {e}")
                await asyncio.sleep(0.3)
                continue

        # Timeout waiting for confirmation - return what we know
        logger.debug("Timeout waiting for cancellation confirmation")
        return {"status": "cancelled", "operation_id": operation_id}

    async def execute_operation(
        self,
        adapter: OperationAdapter,
        console: Console,
        progress_callback: Optional[Callable[[dict[str, Any]], str]] = None,
        show_progress: bool = True,
    ) -> bool:
        """
        Execute an async operation end-to-end.

        This is the main entry point for executing operations. It:
        1. Sets up signal handlers for Ctrl+C
        2. Creates HTTP client and Rich progress bar (if show_progress=True)
        3. Starts the operation via adapter
        4. Polls until completion or cancellation, updating progress
        5. Displays results via adapter
        6. Cleans up resources

        Args:
            adapter: Operation adapter providing domain-specific logic
            console: Rich console for output
            progress_callback: Optional callback that formats progress messages.
                             Takes operation_data dict, returns formatted string for display.
            show_progress: Whether to show progress bar

        Returns:
            True if operation completed successfully, False otherwise
        """
        # Reset cancellation flag
        self.cancelled = False

        try:
            # Setup signal handler
            self._setup_signal_handler()

            # Create HTTP client
            async with httpx.AsyncClient() as http_client:
                # Start the operation
                try:
                    operation_id = await self._start_operation(adapter, http_client)
                except httpx.HTTPStatusError as e:
                    # Try to parse structured error from response
                    try:
                        response_json = e.response.json()
                        # FastAPI HTTPException puts the detail in "detail" field
                        error_detail = response_json.get("detail", response_json)

                        if (
                            isinstance(error_detail, dict)
                            and "error_code" in error_detail
                        ):
                            # Structured ConfigurationError response
                            console.print("[red bold]Configuration Error:[/red bold]")
                            console.print(
                                f"  [red]{error_detail.get('message', 'Validation failed')}[/red]"
                            )

                            if error_detail.get("error_code"):
                                console.print(f"  Code: {error_detail['error_code']}")

                            if error_detail.get("context"):
                                context = error_detail["context"]
                                console.print("  Context:")
                                for key, value in context.items():
                                    console.print(f"    {key}: {value}")

                            if error_detail.get("suggestion"):
                                console.print("\n[yellow]Suggestion:[/yellow]")
                                console.print(f"  {error_detail['suggestion']}")
                        elif isinstance(error_detail, str):
                            # Plain string error from FastAPI (e.g., ValidationError)
                            console.print(f"[red bold]Error:[/red bold] {error_detail}")
                        else:
                            # Not a structured error, show generic message with detail
                            console.print(
                                f"[red]Failed to start operation: {e}[/red]",
                                style="bold",
                            )
                    except Exception:
                        # Fallback to simple error message
                        console.print(
                            f"[red]Failed to start operation: {e}[/red]", style="bold"
                        )
                    return False
                except httpx.HTTPError as e:
                    console.print(
                        f"[red]Failed to start operation: {e}[/red]", style="bold"
                    )
                    return False
                except KeyError as e:
                    console.print(
                        f"[red]Invalid response from server (missing operation_id): {e}[/red]",
                        style="bold",
                    )
                    return False

                # Poll until complete (with or without progress display)
                if show_progress:
                    # Suppress console logging during progress display
                    # (log output to stdout breaks Rich's single-line progress updates)
                    handler, original_level = _suppress_console_logging()
                    try:
                        # Create Rich progress bar and poll with updates
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                            TimeElapsedColumn(),
                            console=console,
                        ) as progress:
                            task_id = progress.add_task(
                                "Starting operation...", total=100
                            )
                            final_status = await self._poll_until_complete(
                                operation_id,
                                http_client,
                                progress,
                                task_id,
                                progress_callback,
                            )
                    finally:
                        # Always restore console logging
                        _restore_console_logging(handler, original_level)
                else:
                    # Poll without progress display
                    final_status = await self._poll_until_complete(
                        operation_id, http_client, None, None, None
                    )

                # Handle cancellation
                if self.cancelled or final_status.get("status") == "cancelled":
                    console.print(
                        "[yellow]⚠️  Operation cancelled by user[/yellow]", style="bold"
                    )
                    # Send cancellation to backend and wait for confirmation
                    final_status = await self._handle_cancellation(
                        operation_id, http_client, console
                    )

                    # Display any cancellation results/metadata via adapter
                    if hasattr(adapter, "display_cancellation_results"):
                        await adapter.display_cancellation_results(
                            final_status, console, http_client
                        )
                    else:
                        # Default cancellation message
                        iterations = final_status.get("metadata", {}).get(
                            "iterations_completed", "some"
                        )
                        console.print(
                            f"[yellow]✓ Cancellation confirmed. Completed {iterations} iterations.[/yellow]"
                        )

                    return False

                # Handle failure
                if final_status.get("status") == "failed":
                    error_msg = final_status.get("error_message", "Unknown error")
                    console.print(
                        f"[red]❌ Operation failed: {error_msg}[/red]", style="bold"
                    )
                    return False

                # Handle success
                if final_status.get("status") == "completed":
                    # Display results via adapter
                    await adapter.display_results(final_status, console, http_client)
                    return True

                # Unknown terminal state
                console.print(
                    f"[yellow]⚠️  Operation ended with unknown status: {final_status.get('status')}[/yellow]",
                    style="bold",
                )
                return False

        finally:
            # Always cleanup signal handler
            self._cleanup_signal_handler()
