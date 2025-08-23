"""
Health check endpoints for Training Host Service

Provides health monitoring and GPU status information.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import torch

# Import existing ktrdr modules
from ktrdr.logging import get_logger
from ktrdr.training.gpu_memory_manager import GPUMemoryManager, GPUMemoryConfig

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

# Global GPU manager instance
_gpu_manager: Optional[GPUMemoryManager] = None


def is_gpu_available() -> tuple[bool, str]:
    """Check for GPU availability (CUDA or MPS)."""
    cuda_available = torch.cuda.is_available()
    mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

    if cuda_available:
        return True, "CUDA"
    elif mps_available:
        return True, "MPS"
    else:
        return False, "None"


async def get_gpu_manager() -> Optional[GPUMemoryManager]:
    """Get or create GPU memory manager instance."""
    global _gpu_manager
    gpu_available, gpu_type = is_gpu_available()

    if _gpu_manager is None and gpu_available:
        try:
            config = GPUMemoryConfig()
            _gpu_manager = GPUMemoryManager(config)
        except Exception as e:
            logger.warning(f"Failed to initialize GPU manager: {str(e)}")
            _gpu_manager = None
    return _gpu_manager


# Response Models


class HealthResponse(BaseModel):
    """Health check response."""

    healthy: bool
    service: str = "training-host"
    timestamp: str
    gpu_status: Dict[str, Any]
    system_info: Dict[str, Any]
    error: Optional[str] = None


class DetailedHealthResponse(BaseModel):
    """Detailed health information."""

    healthy: bool
    service: str = "training-host"
    timestamp: str
    gpu_available: bool
    gpu_device_count: int
    gpu_memory_total_mb: float
    gpu_memory_allocated_mb: float
    active_training_sessions: int
    system_memory_usage_percent: float
    system_memory_total_mb: float
    uptime_seconds: float
    gpu_manager_status: Dict[str, Any]
    error: Optional[str] = None


# Endpoints


@router.get("/", response_model=HealthResponse)
async def basic_health_check():
    """
    Basic health check endpoint.

    Returns overall service health and GPU status.
    """
    try:
        current_time = datetime.utcnow()

        # Check GPU availability (CUDA or MPS)
        gpu_available, gpu_type = is_gpu_available()

        if gpu_type == "CUDA":
            gpu_device_count = torch.cuda.device_count()
        elif gpu_type == "MPS":
            gpu_device_count = 1  # MPS represents one unified GPU
        else:
            gpu_device_count = 0

        gpu_status = {
            "available": gpu_available,
            "device_count": gpu_device_count,
            "gpu_type": gpu_type,
        }

        if gpu_available:
            try:
                if gpu_type == "CUDA":
                    # Get CUDA GPU memory info
                    device = torch.cuda.current_device()
                    total_memory = torch.cuda.get_device_properties(device).total_memory
                    allocated_memory = torch.cuda.memory_allocated(device)
                    device_name = torch.cuda.get_device_name(device)
                elif gpu_type == "MPS":
                    # For MPS, we can't get exact memory stats the same way
                    # Use system info as approximation
                    import subprocess

                    try:
                        result = subprocess.run(
                            ["system_profiler", "SPDisplaysDataType"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if "Apple M" in result.stdout:
                            device_name = "Apple Silicon GPU (MPS)"
                            # MPS doesn't provide direct memory queries like CUDA
                            total_memory = 0  # Will be filled by system memory sharing
                            allocated_memory = 0
                        else:
                            device_name = "Unknown MPS Device"
                            total_memory = 0
                            allocated_memory = 0
                    except:
                        device_name = "Apple Silicon GPU (MPS)"
                        total_memory = 0
                        allocated_memory = 0
                else:
                    total_memory = 0
                    allocated_memory = 0
                    device_name = "Unknown"

                gpu_status.update(
                    {
                        "total_memory_mb": (
                            total_memory / (1024**2) if total_memory > 0 else 0
                        ),
                        "allocated_memory_mb": (
                            allocated_memory / (1024**2) if allocated_memory > 0 else 0
                        ),
                        "device_name": device_name,
                    }
                )
            except Exception as e:
                logger.warning(f"Error getting GPU memory info: {str(e)}")
                gpu_status["memory_error"] = str(e)

        # System info
        import psutil

        system_info = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_total_mb": psutil.virtual_memory().total / (1024**2),
        }

        return HealthResponse(
            healthy=True,
            timestamp=current_time.isoformat(),
            gpu_status=gpu_status,
            system_info=system_info,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            healthy=False,
            timestamp=datetime.utcnow().isoformat(),
            gpu_status={"available": False, "device_count": 0},
            system_info={"error": "Failed to get system info"},
            error=str(e),
        )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check with comprehensive status information.

    Provides detailed information about GPU memory, training sessions,
    system resources, and service uptime.
    """
    try:
        current_time = datetime.utcnow()

        # GPU information (CUDA or MPS)
        gpu_available, gpu_type = is_gpu_available()

        if gpu_type == "CUDA":
            gpu_device_count = torch.cuda.device_count()
        elif gpu_type == "MPS":
            gpu_device_count = 1  # MPS represents one unified GPU
        else:
            gpu_device_count = 0

        gpu_memory_total_mb = 0.0
        gpu_memory_allocated_mb = 0.0

        if gpu_available:
            try:
                if gpu_type == "CUDA":
                    device = torch.cuda.current_device()
                    gpu_memory_total_mb = torch.cuda.get_device_properties(
                        device
                    ).total_memory / (1024**2)
                    gpu_memory_allocated_mb = torch.cuda.memory_allocated(device) / (
                        1024**2
                    )
                elif gpu_type == "MPS":
                    # MPS shares system memory, so we can't get exact GPU memory
                    # This is a limitation of MPS vs CUDA
                    gpu_memory_total_mb = 0.0  # MPS uses shared memory
                    gpu_memory_allocated_mb = 0.0
            except Exception as e:
                logger.warning(f"Error getting detailed GPU info: {str(e)}")

        # System memory information
        import psutil

        memory = psutil.virtual_memory()
        system_memory_usage_percent = memory.percent
        system_memory_total_mb = memory.total / (1024**2)

        # GPU manager status
        gpu_manager = await get_gpu_manager()
        gpu_manager_status = {}

        if gpu_manager and gpu_manager.enabled:
            try:
                summary = gpu_manager.get_memory_summary()
                gpu_manager_status = {
                    "initialized": True,
                    "monitoring_active": hasattr(gpu_manager, "_monitoring_active")
                    and gpu_manager._monitoring_active,
                    "total_memory_mb": summary.get("total_memory_mb", 0),
                    "device_count": summary.get("device_count", 0),
                }
            except Exception as e:
                gpu_manager_status = {"error": str(e)}
        else:
            gpu_manager_status = {
                "initialized": False,
                "reason": "GPU not available or manager failed to initialize",
            }

        return DetailedHealthResponse(
            healthy=True,
            timestamp=current_time.isoformat(),
            gpu_available=gpu_available,
            gpu_device_count=gpu_device_count,
            gpu_memory_total_mb=gpu_memory_total_mb,
            gpu_memory_allocated_mb=gpu_memory_allocated_mb,
            active_training_sessions=0,  # TODO: Track active sessions
            system_memory_usage_percent=system_memory_usage_percent,
            system_memory_total_mb=system_memory_total_mb,
            uptime_seconds=0.0,  # TODO: Add uptime tracking
            gpu_manager_status=gpu_manager_status,
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        return DetailedHealthResponse(
            healthy=False,
            timestamp=datetime.utcnow().isoformat(),
            gpu_available=False,
            gpu_device_count=0,
            gpu_memory_total_mb=0.0,
            gpu_memory_allocated_mb=0.0,
            active_training_sessions=0,
            system_memory_usage_percent=0.0,
            system_memory_total_mb=0.0,
            uptime_seconds=0.0,
            gpu_manager_status={"error": str(e)},
            error=str(e),
        )
