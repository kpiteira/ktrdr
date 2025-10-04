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

    async def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
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
                    list(data.keys())
                    if isinstance(data, dict)
                    else type(data).__name__
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
