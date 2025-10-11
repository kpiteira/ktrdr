"""
Device Manager for centralized GPU detection and device selection.

This module provides a unified interface for detecting and configuring
compute devices (CUDA, MPS, CPU) across the training system.

Extracted from training-host-service/services/training_service.py lines 504-517
to eliminate code duplication between local and host training paths.
"""

import logging
from typing import Any

import torch

logger = logging.getLogger(__name__)


class DeviceManager:
    """
    Centralized GPU detection and device selection.

    Provides static methods for:
    - Detecting best available device (MPS > CUDA > CPU)
    - Getting detailed device information for logging/metrics
    - Creating torch.device objects

    Device Priority (based on host service implementation):
    1. MPS (Apple Silicon) - Prioritized for macOS
    2. CUDA (NVIDIA GPUs)
    3. CPU (Fallback)
    """

    @staticmethod
    def detect_device() -> str:
        """
        Detect best available device (mps, cuda, or cpu).

        Device detection priority:
        1. MPS (Apple Silicon) - torch.backends.mps.is_available()
        2. CUDA (NVIDIA) - torch.cuda.is_available()
        3. CPU (Fallback)

        Returns:
            str: Device type ("mps", "cuda", or "cpu")

        Example:
            >>> device = DeviceManager.detect_device()
            >>> print(f"Using device: {device}")
            Using device: mps
        """
        try:
            # Check MPS first (Apple Silicon priority)
            if torch.backends.mps.is_available():
                logger.info("Using Apple Silicon MPS for GPU acceleration")
                return "mps"
        except RuntimeError as e:
            logger.warning(f"MPS check failed: {e}, checking other devices")

        try:
            # Check CUDA next
            if torch.cuda.is_available():
                try:
                    device_name = torch.cuda.get_device_name(0)
                    logger.info(f"Using CUDA GPU {device_name} for acceleration")
                except (RuntimeError, AssertionError):
                    # Can fail if torch not compiled with CUDA
                    logger.info("Using CUDA GPU for acceleration")

                return "cuda"
        except (RuntimeError, AssertionError) as e:
            logger.warning(f"CUDA check failed: {e}, falling back to CPU")

        # Fallback to CPU
        logger.info("No GPU available, using CPU")
        return "cpu"

    @staticmethod
    def get_device_info() -> dict[str, Any]:
        """
        Get detailed device information for logging/metrics.

        Returns:
            dict: Device information containing:
                - device (str): Device type ("mps", "cuda", "cpu")
                - device_name (str): Human-readable device name
                - available (bool): Whether device is available
                - capabilities (dict): Device capabilities
                    - mixed_precision (bool): Support for mixed precision training
                    - memory_info (bool): Support for memory queries

        Example:
            >>> info = DeviceManager.get_device_info()
            >>> print(f"Device: {info['device_name']}")
            >>> print(f"Mixed precision: {info['capabilities']['mixed_precision']}")
        """
        device = DeviceManager.detect_device()

        if device == "mps":
            return {
                "device": "mps",
                "device_name": "Apple Silicon MPS",
                "available": True,
                "capabilities": {
                    "mixed_precision": False,  # MPS doesn't support mixed precision
                    "memory_info": False,  # MPS doesn't support memory queries
                },
            }
        elif device == "cuda":
            device_name = "CUDA GPU"
            try:
                device_name = torch.cuda.get_device_name(0)
            except (RuntimeError, AssertionError) as e:
                logger.warning(f"Could not get CUDA device name: {e}")
                device_name = "CUDA GPU (name unavailable)"

            return {
                "device": "cuda",
                "device_name": device_name,
                "available": True,
                "capabilities": {
                    "mixed_precision": True,  # CUDA supports mixed precision
                    "memory_info": True,  # CUDA supports memory queries
                },
            }
        else:  # cpu
            return {
                "device": "cpu",
                "device_name": "CPU",
                "available": True,
                "capabilities": {
                    "mixed_precision": False,  # CPU doesn't support mixed precision
                    "memory_info": False,  # CPU doesn't support memory queries
                },
            }

    @staticmethod
    def get_torch_device() -> torch.device:
        """
        Get torch.device object for the best available device.

        Returns:
            torch.device: PyTorch device object ready for use

        Example:
            >>> device = DeviceManager.get_torch_device()
            >>> model = model.to(device)
        """
        device_str = DeviceManager.detect_device()
        return torch.device(device_str)
