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

        # Log the request (DEBUG for operations polling, INFO for others)
        log_level = logging.DEBUG if request.url.path.startswith("/api/v1/operations/") else logging.INFO
        logger.log(
            log_level,
            f"Request started: method={request.method} path={request.url.path} "
            f"client={request.client.host if request.client else 'unknown'} "
            f"request_id={request_id}"
        )

        try:
            # Process the request through the next handler
            response = await call_next(request)

            # Calculate request processing time
            process_time = (time.time() - start_time) * 1000

            # Log the response (DEBUG for operations polling, INFO for others)
            log_level = logging.DEBUG if request.url.path.startswith("/api/v1/operations/") else logging.INFO
            logger.log(
                log_level,
                f"Request completed: method={request.method} path={request.url.path} "
                f"status_code={response.status_code} "
                f"duration={process_time:.2f}ms request_id={request_id}"
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
