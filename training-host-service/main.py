#!/usr/bin/env python3
"""
Training Host Service - Using WorkerAPIBase Pattern

A GPU-accelerated training worker that self-registers with the backend's
WorkerRegistry for unified worker management and GPU-first worker selection.

Migrated from standalone FastAPI to WorkerAPIBase pattern (Task 5.6).
"""

import logging
import logging.handlers
import os
import sys
import warnings
from pathlib import Path
from typing import Any

import torch
import uvicorn

# Suppress PyTorch distributed future warnings
warnings.filterwarnings(
    "ignore", message=".*torch.distributed.reduce_op.*", category=FutureWarning
)

# Add parent directory to path for ktrdr imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    # Import domain-specific endpoints
    from endpoints.training import router as training_router

    from ktrdr.api.models.operations import OperationType
    from ktrdr.api.models.workers import WorkerType
    from ktrdr.logging import configure_logging, get_logger
    from ktrdr.workers.base import WorkerAPIBase
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure the parent directory contains ktrdr modules")
    sys.exit(1)


class TrainingHostWorker(WorkerAPIBase):
    """
    Training host service using WorkerAPIBase pattern.

    Provides:
    - GPU detection and capability reporting
    - Self-registration with backend's WorkerRegistry
    - OperationsService endpoints (via WorkerAPIBase)
    - Health endpoint with GPU status (via WorkerAPIBase)
    - Training-specific endpoints (from endpoints/training.py)
    """

    def __init__(
        self,
        worker_port: int = 5002,
        backend_url: str = "http://localhost:8000",
        capabilities: dict[str, Any] | None = None,
    ):
        """
        Initialize training host worker.

        Args:
            worker_port: Port for this worker service (default: 5002)
            backend_url: URL of backend service for registration
            capabilities: Optional pre-detected capabilities (for testing)
        """
        # Detect GPU capabilities if not provided
        if capabilities is None:
            capabilities = self._detect_gpu_capabilities()

        # Initialize WorkerAPIBase (provides all infrastructure)
        super().__init__(
            worker_type=WorkerType.TRAINING,
            operation_type=OperationType.TRAINING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Store capabilities for health reporting
        self.capabilities = capabilities

        # Register domain-specific training endpoints
        self.app.include_router(training_router)

        # Override worker ID if provided by environment
        worker_id_env = os.getenv("WORKER_ID")
        if worker_id_env:
            self.worker_id = worker_id_env

    def _detect_gpu_capabilities(self) -> dict[str, Any]:
        """
        Detect GPU type and availability.

        Returns:
            Dictionary with GPU capabilities:
            - gpu: bool (True if GPU available)
            - gpu_type: str ("CUDA" or "MPS") if GPU available
            - gpu_count: int (number of GPUs) if GPU available
        """
        cuda_available = torch.cuda.is_available()
        mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

        if cuda_available:
            return {
                "gpu": True,
                "gpu_type": "CUDA",
                "gpu_count": torch.cuda.device_count(),
            }
        elif mps_available:
            return {
                "gpu": True,
                "gpu_type": "MPS",
                "gpu_count": 1,
            }
        else:
            return {"gpu": False}

    async def self_register(self) -> None:
        """
        Register this worker with backend's WorkerRegistry.

        Overrides WorkerAPIBase.self_register to include GPU capabilities.
        """
        import os

        import httpx

        registration_url = f"{self.backend_url}/api/v1/workers/register"

        # For host services (running outside Docker), use host.docker.internal
        # so backend can reach us from inside Docker
        hostname = os.getenv("WORKER_HOSTNAME", "host.docker.internal")

        payload = {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type.value,
            "endpoint_url": f"http://{hostname}:{self.worker_port}",
            "capabilities": self.capabilities,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(registration_url, json=payload)
                response.raise_for_status()

                gpu_info = ""
                if self.capabilities.get("gpu"):
                    gpu_type = self.capabilities.get("gpu_type", "unknown")
                    gpu_count = self.capabilities.get("gpu_count", 0)
                    gpu_info = f", GPU: {gpu_type} ({gpu_count} device(s))"

                logger.info(
                    f"✅ Worker registered successfully: {self.worker_id} "
                    f"(type: {self.worker_type.value}{gpu_info})"
                )
        except Exception as e:
            logger.warning(
                f"⚠️  Worker self-registration failed (will retry via health checks): {e}"
            )


def setup_logging():
    """Configure logging for training host service."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    configure_logging(
        log_dir=log_dir,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        config={
            "file_format": "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s",
        },
    )

    # Override root handler to write to host-service-specific log file
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            root_logger.removeHandler(handler)
            handler.close()

            host_log_file = log_dir / "ktrdr-host-service.log"
            new_handler = logging.handlers.RotatingFileHandler(
                filename=host_log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
            )
            new_handler.setLevel(logging.DEBUG)
            new_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s"
                )
            )
            root_logger.addHandler(new_handler)


# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create worker instance
worker = TrainingHostWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5002")),
    backend_url=os.getenv("KTRDR_API_URL", "http://localhost:8000"),
)

# Expose app for uvicorn
app = worker.app


if __name__ == "__main__":
    # Get configuration
    host = os.getenv("WORKER_HOST", "0.0.0.0")
    port = int(os.getenv("WORKER_PORT", "5002"))

    logger.info("Starting Training Host Service...")
    logger.info(f"Service will listen on http://{host}:{port}")

    # Log GPU capabilities
    gpu_info = worker.capabilities
    if gpu_info.get("gpu"):
        gpu_type = gpu_info.get("gpu_type", "unknown")
        gpu_count = gpu_info.get("gpu_count", 0)
        logger.info(f"GPU available: {gpu_type} ({gpu_count} device(s))")
    else:
        logger.info("No GPU available (CPU-only mode)")

    # Run the service
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
