"""
Unit tests for DeviceManager.

Tests cover:
- CUDA device detection
- MPS device detection
- CPU fallback
- Device info retrieval
- Device capability detection
"""
import pytest
import torch
from unittest.mock import patch, MagicMock

from ktrdr.training.device_manager import DeviceManager


class TestDeviceDetection:
    """Test device detection logic."""

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_detect_device_cuda_preferred(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test CUDA is selected when both CUDA and MPS are available."""
        # MPS has higher priority according to implementation plan line 504-517
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = True

        device = DeviceManager.detect_device()

        assert device == "cuda"
        mock_cuda_available.assert_called_once()

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_detect_device_mps_when_available(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test MPS is selected when available (Apple Silicon priority)."""
        mock_mps_available.return_value = True
        mock_cuda_available.return_value = False

        device = DeviceManager.detect_device()

        assert device == "mps"
        mock_mps_available.assert_called_once()

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_detect_device_mps_preferred_over_cuda(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test MPS has priority over CUDA when both available."""
        mock_mps_available.return_value = True
        mock_cuda_available.return_value = True

        device = DeviceManager.detect_device()

        assert device == "mps"
        # Should check MPS first and not check CUDA
        mock_mps_available.assert_called_once()

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_detect_device_cpu_fallback(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test CPU is used when no GPU available."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = False

        device = DeviceManager.detect_device()

        assert device == "cpu"
        mock_mps_available.assert_called_once()
        mock_cuda_available.assert_called_once()


class TestDeviceInfo:
    """Test device information retrieval."""

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    @patch("torch.cuda.get_device_name")
    def test_get_device_info_cuda(
        self, mock_get_device_name, mock_cuda_available, mock_mps_available
    ):
        """Test device info for CUDA device."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = True
        mock_get_device_name.return_value = "NVIDIA GeForce RTX 3080"

        info = DeviceManager.get_device_info()

        assert info["device"] == "cuda"
        assert info["device_name"] == "NVIDIA GeForce RTX 3080"
        assert info["available"] is True
        assert "capabilities" in info

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_get_device_info_mps(self, mock_cuda_available, mock_mps_available):
        """Test device info for MPS device."""
        mock_mps_available.return_value = True
        mock_cuda_available.return_value = False

        info = DeviceManager.get_device_info()

        assert info["device"] == "mps"
        assert info["device_name"] == "Apple Silicon MPS"
        assert info["available"] is True
        assert "capabilities" in info

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_get_device_info_cpu(self, mock_cuda_available, mock_mps_available):
        """Test device info for CPU fallback."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = False

        info = DeviceManager.get_device_info()

        assert info["device"] == "cpu"
        assert info["device_name"] == "CPU"
        assert info["available"] is True
        assert "capabilities" in info


class TestDeviceCapabilities:
    """Test device capability detection."""

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_mps_capabilities_no_mixed_precision(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test MPS capabilities indicate no mixed precision support."""
        mock_mps_available.return_value = True
        mock_cuda_available.return_value = False

        info = DeviceManager.get_device_info()

        assert info["capabilities"]["mixed_precision"] is False
        assert info["capabilities"]["memory_info"] is False

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_cuda_capabilities_full_features(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test CUDA capabilities indicate full feature support."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = True

        info = DeviceManager.get_device_info()

        assert info["capabilities"]["mixed_precision"] is True
        assert info["capabilities"]["memory_info"] is True

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_cpu_capabilities_limited(self, mock_cuda_available, mock_mps_available):
        """Test CPU capabilities are limited."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = False

        info = DeviceManager.get_device_info()

        assert info["capabilities"]["mixed_precision"] is False
        assert info["capabilities"]["memory_info"] is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("torch.backends.mps.is_available")
    def test_detect_device_handles_mps_exception(self, mock_mps_available):
        """Test graceful fallback when MPS check raises exception."""
        mock_mps_available.side_effect = RuntimeError("MPS check failed")

        device = DeviceManager.detect_device()

        # Should fall back to checking CUDA or CPU
        assert device in ["cuda", "cpu"]

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_detect_device_handles_cuda_exception(
        self, mock_cuda_available, mock_mps_available
    ):
        """Test graceful fallback when CUDA check raises exception."""
        mock_mps_available.return_value = False
        mock_cuda_available.side_effect = RuntimeError("CUDA check failed")

        device = DeviceManager.detect_device()

        # Should fall back to CPU
        assert device == "cpu"

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    @patch("torch.cuda.get_device_name")
    def test_get_device_info_handles_device_name_exception(
        self, mock_get_device_name, mock_cuda_available, mock_mps_available
    ):
        """Test device info handles missing device name gracefully."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = True
        mock_get_device_name.side_effect = RuntimeError("Could not get device name")

        info = DeviceManager.get_device_info()

        assert info["device"] == "cuda"
        # Should have fallback device name
        assert "device_name" in info
        assert info["device_name"] != ""


class TestDeviceObject:
    """Test torch.device object creation."""

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_get_torch_device_cuda(self, mock_cuda_available, mock_mps_available):
        """Test getting torch.device object for CUDA."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = True

        device = DeviceManager.get_torch_device()

        assert isinstance(device, torch.device)
        assert device.type == "cuda"

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_get_torch_device_mps(self, mock_cuda_available, mock_mps_available):
        """Test getting torch.device object for MPS."""
        mock_mps_available.return_value = True
        mock_cuda_available.return_value = False

        device = DeviceManager.get_torch_device()

        assert isinstance(device, torch.device)
        assert device.type == "mps"

    @patch("torch.backends.mps.is_available")
    @patch("torch.cuda.is_available")
    def test_get_torch_device_cpu(self, mock_cuda_available, mock_mps_available):
        """Test getting torch.device object for CPU."""
        mock_mps_available.return_value = False
        mock_cuda_available.return_value = False

        device = DeviceManager.get_torch_device()

        assert isinstance(device, torch.device)
        assert device.type == "cpu"
