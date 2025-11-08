"""Worker self-registration for distributed backtesting architecture."""

import asyncio
import os
import platform
import socket
from typing import Any

import httpx

from ktrdr import get_logger

logger = get_logger(__name__)


class WorkerRegistration:
    """Handles worker self-registration with the backend API."""

    def __init__(
        self,
        max_retries: int = 5,
        retry_delay: float = 2.0,
    ):
        """
        Initialize worker registration.

        Args:
            max_retries: Maximum number of registration retry attempts
            retry_delay: Delay in seconds between retry attempts
        """
        self.worker_id = os.getenv("WORKER_ID") or self._generate_worker_id()
        self.worker_type = "backtesting"
        self.port = int(os.getenv("WORKER_PORT", "5003"))
        self.backend_url = os.getenv("KTRDR_API_URL", "http://backend:8000")
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _generate_worker_id(self) -> str:
        """
        Generate a worker ID from hostname.

        Returns:
            str: Generated worker ID in format "backtest-{hostname}"
        """
        hostname = socket.gethostname()
        return f"backtest-{hostname}"

    def get_endpoint_url(self) -> str:
        """
        Get the endpoint URL where this worker can be reached.

        Returns:
            str: HTTP URL for this worker
        """
        hostname = socket.gethostname()
        return f"http://{hostname}:{self.port}"

    def get_capabilities(self) -> dict[str, Any]:
        """
        Detect and return worker capabilities.

        Returns:
            dict: Worker capabilities (cores, memory, etc.)
        """
        try:
            import psutil

            # Get actual system resources
            cores = psutil.cpu_count(logical=False) or psutil.cpu_count()
            memory_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        except ImportError:
            # Fallback if psutil not available
            cores = os.cpu_count() or 1
            # Rough estimate - not accurate but better than nothing
            memory_gb = 4.0

        return {
            "cores": cores,
            "memory_gb": memory_gb,
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }

    async def register(self) -> bool:
        """
        Register this worker with the backend API.

        Retries on failure up to max_retries times.

        Returns:
            bool: True if registration successful, False otherwise
        """
        endpoint_url = self.get_endpoint_url()
        capabilities = self.get_capabilities()

        registration_data = {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "endpoint_url": endpoint_url,
            "capabilities": capabilities,
        }

        logger.info(
            f"Attempting to register worker {self.worker_id} at {endpoint_url}"
        )
        logger.debug(f"Registration data: {registration_data}")

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.backend_url}/api/v1/workers/register",
                        json=registration_data,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        logger.info(
                            f"Worker {self.worker_id} registered successfully: {result}"
                        )
                        return True
                    else:
                        logger.warning(
                            f"Registration attempt {attempt}/{self.max_retries} failed: "
                            f"HTTP {response.status_code} - {response.text}"
                        )

            except Exception as e:
                logger.warning(
                    f"Registration attempt {attempt}/{self.max_retries} failed: {e}"
                )

            # Wait before retrying (unless this was the last attempt)
            if attempt < self.max_retries:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                await asyncio.sleep(self.retry_delay)

        logger.error(
            f"Failed to register worker {self.worker_id} after {self.max_retries} attempts"
        )
        return False
