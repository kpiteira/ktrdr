"""Worker self-registration for distributed training architecture."""

import asyncio
import os
import platform
import socket
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from ktrdr import get_logger

logger = get_logger(__name__)


class WorkerRegistration:
    """Handles training worker self-registration with the backend API."""

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

        Raises:
            RuntimeError: If KTRDR_API_URL environment variable is not set
        """
        self.worker_id = os.getenv("WORKER_ID") or self._generate_worker_id()
        self.worker_type = "training"
        self.port = int(os.getenv("WORKER_PORT", "5004"))

        # Backend URL is REQUIRED (no default)
        self.backend_url = os.getenv("KTRDR_API_URL")
        if not self.backend_url:
            raise RuntimeError(
                "KTRDR_API_URL environment variable is required for worker registration. "
                "Example: KTRDR_API_URL=http://192.168.1.100:8000"
            )

        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _generate_worker_id(self) -> str:
        """
        Generate a worker ID from hostname.

        Returns:
            str: Generated worker ID in format "training-{hostname}"
        """
        hostname = socket.gethostname()
        return f"training-{hostname}"

    def get_endpoint_url(self) -> str:
        """
        Get endpoint URL - IP-based for cross-network compatibility.

        Priority:
        1. WORKER_ENDPOINT_URL env var (explicit configuration)
        2. Auto-detected IP address (for multi-host)
        3. Hostname (for Docker Compose fallback)

        Returns:
            str: HTTP URL for this worker
        """
        # 1. Explicit configuration (Proxmox/cloud deployments)
        if endpoint_url := os.getenv("WORKER_ENDPOINT_URL"):
            return endpoint_url

        # 2. Auto-detect IP address (for multi-host deployments)
        if ip_address := self._detect_ip_address():
            return f"http://{ip_address}:{self.port}"

        # 3. Fallback to hostname (for Docker Compose)
        hostname = socket.gethostname()
        logger.warning(
            f"Using hostname for endpoint URL: {hostname}. "
            f"This may not work in multi-host deployments. "
            f"Set WORKER_ENDPOINT_URL=http://<IP>:{self.port} for production."
        )
        return f"http://{hostname}:{self.port}"

    def _detect_ip_address(self) -> Optional[str]:
        """
        Detect worker's IP address visible to backend.

        Uses dummy socket connection to backend to discover which
        local IP address would be used for communication.

        Returns:
            Optional[str]: Detected IP address, or None if detection fails
        """
        try:
            # Parse backend host from URL
            backend_host = urlparse(self.backend_url).hostname or "8.8.8.8"

            # Create dummy socket to backend
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((backend_host, 80))

            # Get local IP used for connection
            ip = s.getsockname()[0]
            s.close()

            logger.info(f"Auto-detected worker IP address: {ip}")
            return ip

        except Exception as e:
            logger.warning(f"Failed to auto-detect IP address: {e}")
            return None

    def get_capabilities(self) -> dict[str, Any]:
        """
        Detect and return worker capabilities.

        Returns:
            dict: Worker capabilities (cores, memory, GPU, etc.)
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

        # Detect GPU capabilities
        gpu_available = False
        gpu_info: dict[str, Any] = {}
        try:
            import torch

            if torch.cuda.is_available():
                gpu_available = True
                gpu_info = {
                    "cuda_version": torch.version.cuda,
                    "device_count": torch.cuda.device_count(),
                    "device_name": (
                        torch.cuda.get_device_name(0)
                        if torch.cuda.device_count() > 0
                        else None
                    ),
                }
            elif torch.backends.mps.is_available():
                gpu_available = True
                gpu_info = {
                    "backend": "mps",
                    "platform": "Apple Silicon",
                }
        except ImportError:
            pass

        capabilities: dict[str, Any] = {
            "cores": cores,
            "memory_gb": memory_gb,
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "gpu_available": gpu_available,
        }

        if gpu_available:
            capabilities["gpu"] = gpu_info

        return capabilities

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

        logger.info(f"Attempting to register worker {self.worker_id} at {endpoint_url}")
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
