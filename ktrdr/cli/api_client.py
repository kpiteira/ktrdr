"""
Centralized API client for KTRDR CLI commands.

This module provides a centralized HTTP client for all CLI commands to interact
with the KTRDR API server. It handles common concerns like error handling,
timeouts, retries, and response formatting.
"""

import asyncio
from typing import Any, Optional

import httpx
from rich.console import Console

from ktrdr.cli.ib_diagnosis import (
    detect_ib_issue_from_api_response,
    format_ib_diagnostic_message,
    should_show_ib_diagnosis,
)
from ktrdr.config.host_services import get_api_base_url
from ktrdr.errors import DataError, ValidationError
from ktrdr.logging import get_logger

logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)


class KtrdrApiClient:
    """
    Centralized API client for KTRDR CLI commands.

    Provides a consistent interface for all CLI commands to interact with the
    KTRDR API server, including standardized error handling, timeouts, and
    response processing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the KTRDR API server (defaults to configured URL)
            timeout: Default timeout in seconds for requests
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Delay between retry attempts in seconds
        """
        self.base_url = (base_url or get_api_base_url()).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _enhance_error_with_ib_diagnosis(
        self, response_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Enhance API response with IB diagnosis if applicable.

        Args:
            response_data: Original API response

        Returns:
            Enhanced response with IB diagnostic information
        """
        # Check if this is an error response that might be IB-related
        if not should_show_ib_diagnosis(response_data):
            return response_data

        # Detect IB issue and enhance the response
        problem_type, clear_message, details = detect_ib_issue_from_api_response(
            response_data
        )

        if problem_type and clear_message:
            # Create enhanced error info
            error_info = response_data.get("error", {})
            enhanced_error = {
                **error_info,
                "ib_diagnosis": {
                    "problem_type": problem_type.value,
                    "clear_message": clear_message,
                    "details": details,
                },
                "message": format_ib_diagnostic_message(
                    problem_type, clear_message, details
                ),
            }

            # Return enhanced response
            return {**response_data, "error": enhanced_error}

        return response_data

    async def _make_request(  # type: ignore[return]
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Make an HTTP request with error handling and retries.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path (without base URL)
            json_data: JSON payload for request body
            params: Query parameters
            timeout: Custom timeout for this request
            retries: Custom retry count for this request

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ValidationError: For client errors (4xx)
            DataError: For server errors (5xx) or connection issues
        """
        url = f"{self.base_url}{endpoint}"
        request_timeout = timeout or self.timeout
        max_attempts = (retries or self.max_retries) + 1

        logger.debug(f"Making {method} request to {url}")

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                    )

                    if response.status_code >= 200 and response.status_code < 300:
                        # Success
                        try:
                            response_data = response.json()
                            # Enhance with IB diagnosis if applicable
                            return self._enhance_error_with_ib_diagnosis(response_data)
                        except Exception as e:
                            raise DataError(
                                message="Invalid JSON response from API",
                                error_code="API-InvalidResponse",
                                details={
                                    "url": url,
                                    "status_code": response.status_code,
                                    "response_text": response.text[:500],
                                    "error": str(e),
                                },
                            ) from e

                    elif response.status_code >= 400 and response.status_code < 500:
                        # Client error - don't retry
                        try:
                            error_detail = response.json()
                        except Exception:
                            error_detail = {"message": response.text}

                        # FastAPI HTTPException uses 'detail', our custom errors use 'message'
                        error_message = error_detail.get("detail") or error_detail.get(
                            "message", "Unknown error"
                        )

                        raise ValidationError(
                            message=f"API request failed: {error_message}",
                            error_code=f"API-{response.status_code}",
                            details={
                                "url": url,
                                "status_code": response.status_code,
                                "error_detail": error_detail,
                            },
                        )

                    else:
                        # Server error - might retry
                        error_msg = f"API server error (HTTP {response.status_code})"
                        if attempt == max_attempts - 1:
                            # Last attempt - raise error
                            try:
                                error_detail = response.json()
                            except Exception:
                                error_detail = {"message": response.text}

                            raise DataError(
                                message=error_msg,
                                error_code=f"API-ServerError-{response.status_code}",
                                details={
                                    "url": url,
                                    "status_code": response.status_code,
                                    "error_detail": error_detail,
                                    "attempts": max_attempts,
                                },
                            )
                        else:
                            # Retry after delay
                            logger.warning(
                                f"{error_msg}, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                            )
                            await asyncio.sleep(self.retry_delay)
                            continue

            except httpx.ConnectError as e:
                if attempt == max_attempts - 1:
                    raise DataError(
                        message="Could not connect to KTRDR API server",
                        error_code="API-ConnectionError",
                        details={
                            "url": url,
                            "base_url": self.base_url,
                            "error": str(e),
                            "suggestion": "Make sure the API server is running at the configured URL",
                        },
                    ) from e
                else:
                    logger.warning(
                        f"Connection failed, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue

            except httpx.TimeoutException as e:
                if attempt == max_attempts - 1:
                    raise DataError(
                        message=f"Request timed out after {request_timeout}s",
                        error_code="API-TimeoutError",
                        details={
                            "url": url,
                            "timeout": request_timeout,
                            "error": str(e),
                        },
                    ) from e
                else:
                    logger.warning(
                        f"Request timed out, retrying in {self.retry_delay}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue

            except Exception as e:
                raise DataError(
                    message=f"Unexpected error making API request: {str(e)}",
                    error_code="API-UnexpectedError",
                    details={
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                ) from e

    # =============================================================================
    # Generic HTTP Methods
    # =============================================================================

    async def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make a GET request to the API."""
        return await self._make_request("GET", endpoint, params=params, timeout=timeout)

    async def post(
        self,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make a POST request to the API."""
        return await self._make_request(
            "POST", endpoint, json_data=json, params=params, timeout=timeout
        )

    async def delete(
        self,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Make a DELETE request to the API."""
        return await self._make_request(
            "DELETE", endpoint, json_data=json, params=params, timeout=timeout
        )

    # =============================================================================
    # Data Management Endpoints
    # =============================================================================

    async def get_symbols(self) -> list[dict[str, Any]]:
        """Get list of available trading symbols."""
        response = await self._make_request("GET", "/symbols")
        if not response.get("success"):
            raise DataError(
                message="Failed to get symbols",
                error_code="API-GetSymbolsError",
                details={"response": response},
            )
        return response.get("data", [])

    async def get_timeframes(self) -> list[dict[str, Any]]:
        """Get list of available timeframes."""
        response = await self._make_request("GET", "/timeframes")
        if not response.get("success"):
            raise DataError(
                message="Failed to get timeframes",
                error_code="API-GetTimeframesError",
                details={"response": response},
            )
        return response.get("data", [])

    async def get_cached_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
    ) -> dict[str, Any]:
        """Get cached OHLCV data for visualization."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trading_hours_only:
            params["trading_hours_only"] = str(trading_hours_only)
        if include_extended:
            params["include_extended"] = str(include_extended)

        response = await self._make_request(
            "GET",
            f"/data/{symbol}/{timeframe}",
            params=params,
        )

        if not response.get("success"):
            raise DataError(
                message=f"Failed to get cached data for {symbol} ({timeframe})",
                error_code="API-GetCachedDataError",
                details={
                    "response": response,
                    "symbol": symbol,
                    "timeframe": timeframe,
                },
            )
        return response.get("data", {})

    async def load_data(
        self,
        symbol: str,
        timeframe: str,
        mode: str = "tail",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
        async_mode: bool = False,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Load data via DataManager with IB integration."""
        payload: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "mode": mode,
        }

        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        if trading_hours_only or include_extended:
            payload["filters"] = {
                "trading_hours_only": trading_hours_only,
                "include_extended": include_extended,
            }

        # Add async_mode parameter if specified
        params = {}
        if async_mode:
            params["async_mode"] = "true"

        # Use longer timeout for data loading operations (shorter for async mode)
        request_timeout = timeout or (10.0 if async_mode else 300.0)

        response = await self._make_request(
            "POST",
            "/data/acquire/download",
            json_data=payload,
            params=params,
            timeout=request_timeout,
        )

        return response  # Return full response including success flag and error info

    async def get_data_range(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any]:
        """Get available date range for a symbol and timeframe."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
        }

        response = await self._make_request(
            "POST",
            "/data/range",
            json_data=payload,
        )

        if not response.get("success"):
            raise DataError(
                message=f"Failed to get data range for {symbol} ({timeframe})",
                error_code="API-GetDataRangeError",
                details={
                    "response": response,
                    "symbol": symbol,
                    "timeframe": timeframe,
                },
            )
        return response.get("data", {})

    # =============================================================================
    # Training Endpoints
    # =============================================================================

    async def start_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
        **kwargs,  # Accept additional parameters for backward compatibility
    ) -> dict[str, Any]:
        """Start a training task (supports 1-N symbols)."""
        payload = {
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "task_id": task_id,
            "detailed_analytics": detailed_analytics,
        }

        response = await self._make_request(
            "POST",
            "/trainings/start",
            json_data=payload,
            timeout=300.0,  # 5 minutes for training startup
        )

        if not response.get("success"):
            raise DataError(
                message="Failed to start training",
                error_code="API-StartTrainingError",
                details={"response": response},
            )
        return response

    async def get_training_performance(self, task_id: str) -> dict[str, Any]:
        """Get training performance metrics."""
        response = await self._make_request("GET", f"/trainings/{task_id}/performance")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get training performance for task {task_id}",
                error_code="API-GetTrainingPerformanceError",
                details={"response": response, "task_id": task_id},
            )
        return response

    # =============================================================================
    # Models Endpoints
    # =============================================================================

    async def list_models(self) -> list[dict[str, Any]]:
        """Get list of available models."""
        response = await self._make_request("GET", "/models")
        if not response.get("success"):
            raise DataError(
                message="Failed to list models",
                error_code="API-ListModelsError",
                details={"response": response},
            )
        return response.get("data", [])

    async def save_model(
        self,
        task_id: str,
        model_name: str,
        description: Optional[str] = None,
    ) -> dict[str, Any]:
        """Save a trained model."""
        payload = {
            "task_id": task_id,
            "model_name": model_name,
        }
        if description:
            payload["description"] = description

        response = await self._make_request(
            "POST",
            "/models/save",
            json_data=payload,
        )

        if not response.get("success"):
            raise DataError(
                message=f"Failed to save model {model_name}",
                error_code="API-SaveModelError",
                details={"response": response, "model_name": model_name},
            )
        return response.get("data", {})

    async def load_model(self, model_name: str) -> dict[str, Any]:
        """Load a model for prediction."""
        response = await self._make_request(
            "POST",
            f"/models/{model_name}/load",
            timeout=60.0,  # 1 minute for model loading
        )

        if not response.get("success"):
            raise DataError(
                message=f"Failed to load model {model_name}",
                error_code="API-LoadModelError",
                details={"response": response, "model_name": model_name},
            )
        return response.get("data", {})

    async def predict(
        self,
        symbol: str,
        timeframe: str,
        model_name: Optional[str] = None,
        test_date: Optional[str] = None,
        data_mode: str = "local",
    ) -> dict[str, Any]:
        """Make predictions using a loaded model."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_mode": data_mode,
        }

        if model_name:
            payload["model_name"] = model_name
        if test_date:
            payload["test_date"] = test_date

        response = await self._make_request(
            "POST",
            "/models/predict",
            json_data=payload,
            timeout=60.0,  # 1 minute for predictions
        )

        if not response.get("success"):
            raise DataError(
                message="Failed to make predictions",
                error_code="API-PredictError",
                details={"response": response},
            )
        return response.get("data", {})

    # =============================================================================
    # Backtesting Endpoints
    # =============================================================================

    async def start_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
    ) -> dict[str, Any]:
        """Start a new backtest operation."""
        payload = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
        }

        response = await self._make_request(
            "POST",
            "/backtests/",
            json_data=payload,
            timeout=10.0,  # Quick timeout for starting async operation
        )

        if not response.get("success"):
            raise DataError(
                message="Failed to start backtest",
                error_code="API-StartBacktestError",
                details={"response": response},
            )
        return response

    async def get_backtest_results(self, backtest_id: str) -> dict[str, Any]:
        """Get the full results of a completed backtest."""
        response = await self._make_request("GET", f"/backtests/{backtest_id}/results")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get backtest results for {backtest_id}",
                error_code="API-GetBacktestResultsError",
                details={"response": response, "backtest_id": backtest_id},
            )
        return response

    async def get_backtest_trades(self, backtest_id: str) -> dict[str, Any]:
        """Get the list of trades from a backtest."""
        response = await self._make_request("GET", f"/backtests/{backtest_id}/trades")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get backtest trades for {backtest_id}",
                error_code="API-GetBacktestTradesError",
                details={"response": response, "backtest_id": backtest_id},
            )
        return response

    async def get_equity_curve(self, backtest_id: str) -> dict[str, Any]:
        """Get the equity curve data from a backtest."""
        response = await self._make_request(
            "GET", f"/backtests/{backtest_id}/equity_curve"
        )
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get equity curve for {backtest_id}",
                error_code="API-GetEquityCurveError",
                details={"response": response, "backtest_id": backtest_id},
            )
        return response

    # =============================================================================
    # Operations Management Endpoints
    # =============================================================================

    async def list_operations(
        self,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = False,
    ) -> dict[str, Any]:
        """List operations with optional filtering."""
        params = {
            "limit": str(limit),
            "offset": str(offset),
            "active_only": str(active_only),
        }
        if status:
            params["status"] = status
        if operation_type:
            params["operation_type"] = operation_type

        response = await self._make_request("GET", "/operations", params=params)
        if not response.get("success"):
            raise DataError(
                message="Failed to list operations",
                error_code="API-ListOperationsError",
                details={"response": response},
            )
        return response

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Get detailed status for a specific operation."""
        response = await self._make_request("GET", f"/operations/{operation_id}")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get operation status for {operation_id}",
                error_code="API-GetOperationStatusError",
                details={"response": response, "operation_id": operation_id},
            )
        return response

    async def get_operation_children(self, operation_id: str) -> dict[str, Any]:
        """Get child operations for a parent operation (Task 1.15)."""
        response = await self._make_request(
            "GET", f"/operations/{operation_id}/children"
        )
        if not response.get("success"):
            raise DataError(
                message=f"Failed to get children for operation {operation_id}",
                error_code="API-GetOperationChildrenError",
                details={"response": response, "operation_id": operation_id},
            )
        return response

    async def cancel_operation(
        self,
        operation_id: str,
        reason: Optional[str] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Cancel a running operation."""
        payload = {}
        if reason:
            payload["reason"] = reason
        if force:
            payload["force"] = str(force)

        try:
            response = await self._make_request(
                "DELETE",
                f"/operations/{operation_id}",
                json_data=payload if payload else None,
                timeout=60.0,  # Longer timeout to allow AsyncHostService retry delays to complete
            )

            if not response.get("success"):
                raise DataError(
                    message=f"Failed to cancel operation {operation_id}",
                    error_code="API-CancelOperationError",
                    details={"response": response, "operation_id": operation_id},
                )
            return response

        except ValidationError as e:
            # Check if this is an "operation already finished" error (HTTP 400)
            error_details = e.details.get("error_detail", {}) if e.details else {}
            error_message = error_details.get("detail", "") or error_details.get(
                "message", ""
            )

            if (
                "cannot be cancelled" in error_message.lower()
                and "already" in error_message.lower()
            ):
                # Operation is already cancelled/completed - treat as success
                return {
                    "success": True,
                    "message": f"Operation {operation_id} was already finished",
                    "already_finished": True,
                }
            else:
                # Re-raise for other validation errors
                raise

    async def retry_operation(self, operation_id: str) -> dict[str, Any]:
        """Retry a failed operation."""
        response = await self._make_request("POST", f"/operations/{operation_id}/retry")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to retry operation {operation_id}",
                error_code="API-RetryOperationError",
                details={"response": response, "operation_id": operation_id},
            )
        return response

    async def resume_operation(self, operation_id: str) -> dict[str, Any]:
        """Resume a cancelled or failed operation from checkpoint."""
        response = await self._make_request("POST", f"/operations/{operation_id}/resume")
        if not response.get("success"):
            raise DataError(
                message=f"Failed to resume operation {operation_id}",
                error_code="API-ResumeOperationError",
                details={"response": response, "operation_id": operation_id},
            )
        return response

    # =============================================================================
    # Dummy Service Endpoints
    # =============================================================================

    async def start_dummy_task(self) -> dict[str, Any]:
        """Start the awesome dummy task via API."""
        response = await self._make_request(
            "POST",
            "/dummy/start",
            timeout=10.0,  # Quick timeout for starting async operation
        )

        if not response.get("success"):
            raise DataError(
                message="Failed to start dummy task",
                error_code="API-StartDummyTaskError",
                details={"response": response},
            )
        return response

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"

    async def health_check(self) -> bool:
        """Check if the API server is healthy."""
        try:
            # Try a simple endpoint to check connectivity
            await self._make_request("GET", "/symbols", timeout=5.0, retries=0)
            return True
        except Exception:
            return False


# Singleton instance for CLI commands
_api_client: Optional[KtrdrApiClient] = None


def get_api_client(
    base_url: Optional[str] = None,
    timeout: float = 30.0,
) -> KtrdrApiClient:
    """
    Get the singleton API client instance.

    Args:
        base_url: Base URL of the KTRDR API server
        timeout: Default timeout in seconds

    Returns:
        KtrdrApiClient instance
    """
    global _api_client
    if _api_client is None:
        _api_client = KtrdrApiClient(base_url=base_url, timeout=timeout)
    return _api_client


async def check_api_connection(base_url: Optional[str] = None) -> bool:
    """
    Check if the API server is available.

    Args:
        base_url: Base URL to check

    Returns:
        True if API is available, False otherwise
    """
    client = KtrdrApiClient(base_url=base_url)
    return await client.health_check()
