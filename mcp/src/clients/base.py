"""Base HTTP client for KTRDR API communication"""

from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


class KTRDRAPIError(Exception):
    """Custom exception for KTRDR API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class BaseAPIClient:
    """Shared HTTP client functionality for all domain clients"""

    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        logger.info("API client initialized", base_url=self.base_url)

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling"""
        if not self.client:
            raise KTRDRAPIError(
                "API client not initialized. Use async context manager."
            )

        url = f"{endpoint}" if endpoint.startswith("/") else f"/{endpoint}"

        try:
            logger.debug("API request", method=method, url=url)
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()

            data = response.json()
            logger.debug(
                "API response",
                status=response.status_code,
                data_keys=(
                    list(data.keys()) if isinstance(data, dict) else type(data).__name__
                ),
            )
            return data

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error", status=e.response.status_code, url=url)
            try:
                error_data = e.response.json()
            except Exception:
                error_data = {"detail": e.response.text}

            raise KTRDRAPIError(
                f"HTTP {e.response.status_code}: {error_data.get('detail', 'Unknown error')}",
                status_code=e.response.status_code,
                details=error_data,
            ) from e

        except httpx.RequestError as e:
            logger.error("Request error", error=str(e), url=url)
            raise KTRDRAPIError(f"Request failed: {str(e)}") from e

    def _extract_list(
        self,
        response: dict[str, Any],
        field: str = "data",
        default: Optional[list] = None
    ) -> list[dict[str, Any]]:
        """
        Extract list from response envelope.

        For non-critical operations where empty list is acceptable.

        Args:
            response: API response dict
            field: Field name to extract (default "data")
            default: Default value if field missing (default [])

        Returns:
            Extracted list or default

        Example:
            response = {"success": true, "data": [...]}
            items = self._extract_list(response)
        """
        if default is None:
            default = []
        return response.get(field, default)

    def _extract_dict(
        self,
        response: dict[str, Any],
        field: str = "data",
        default: Optional[dict] = None
    ) -> dict[str, Any]:
        """
        Extract dict from response envelope.

        For non-critical operations where empty dict is acceptable.

        Args:
            response: API response dict
            field: Field name to extract (default "data")
            default: Default value if field missing (default {})

        Returns:
            Extracted dict or default

        Example:
            response = {"success": true, "data": {...}}
            item = self._extract_dict(response)
        """
        if default is None:
            default = {}
        return response.get(field, default)

    def _extract_or_raise(
        self,
        response: dict[str, Any],
        field: str = "data",
        operation: str = "operation"
    ) -> Any:
        """
        Extract field from response or raise detailed error.

        For critical operations that MUST succeed (training start, data loading).

        Args:
            response: API response dict
            field: Field name to extract
            operation: Operation name for error message

        Returns:
            Extracted value

        Raises:
            KTRDRAPIError: If field missing or response indicates error

        Example:
            response = {"success": true, "data": {...}}
            data = self._extract_or_raise(response, operation="training start")
        """
        # Check explicit error flag
        if not response.get("success", True):
            error_msg = response.get("error", "Unknown error")
            raise KTRDRAPIError(
                f"{operation.capitalize()} failed: {error_msg}",
                details=response
            )

        # Extract field
        if field not in response:
            raise KTRDRAPIError(
                f"{operation.capitalize()} response missing '{field}' field",
                details=response
            )

        return response[field]
