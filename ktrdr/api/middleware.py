"""
API middleware module.

This module provides custom middleware for the FastAPI application,
including request/response logging and error handling.
"""

import logging
import time
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ktrdr.logging.config import should_rate_limit_log

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging API requests and responses.

    This middleware logs detailed information about each request and response,
    including method, path, status code, and timing information.
    """

    def __init__(self, app: ASGIApp):
        """Initialize the middleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log details.

        Args:
            request (Request): The incoming request
            call_next (Callable): Function to call the next middleware/route handler

        Returns:
            Response: The response from the next handler
        """
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "")

        # Determine if this is a high-frequency operation
        high_frequency_paths = [
            "/api/v1/operations/",
            "/api/v1/health",
            "/api/v1/status",
            "/api/v1/data/stream",
        ]

        is_high_frequency = any(
            request.url.path.startswith(path) for path in high_frequency_paths
        )

        # Log the request (DEBUG for high-frequency, INFO for others)
        log_level = logging.DEBUG if is_high_frequency else logging.INFO
        # Use rate limiting for high-frequency operations
        should_log_request = True
        if is_high_frequency:
            should_log_request = should_rate_limit_log(
                f"request_{request.url.path}", 30
            )  # Log every 30 seconds

        if should_log_request:
            logger.log(
                log_level,
                f"Request started: method={request.method} path={request.url.path} "
                f"client={request.client.host if request.client else 'unknown'} "
                f"request_id={request_id}",
            )

        try:
            # Process the request through the next handler
            response = await call_next(request)

            # Calculate request processing time
            process_time = (time.time() - start_time) * 1000

            # Log the response with same rules as request
            if should_log_request:
                logger.log(
                    log_level,
                    f"Request completed: method={request.method} path={request.url.path} "
                    f"status_code={response.status_code} "
                    f"duration={process_time:.2f}ms request_id={request_id}",
                )

            # Add processing time header to the response
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

            return response
        except Exception as exc:
            # Calculate request processing time
            process_time = (time.time() - start_time) * 1000

            # Log the error
            logger.error(
                f"Request failed: method={request.method} path={request.url.path} "
                f"error={str(exc)} duration={process_time:.2f}ms request_id={request_id}",
                exc_info=True,
            )

            # Re-raise the exception to be handled by FastAPI's exception handlers
            raise


def add_middleware(app: FastAPI) -> None:
    """
    Add all custom middleware to the FastAPI application.

    Args:
        app (FastAPI): The FastAPI application
    """
    # Add the request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    logger.info("Custom middleware added to the API application")
