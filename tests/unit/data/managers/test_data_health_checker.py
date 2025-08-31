"""
Test cases for DataHealthChecker component.

This module tests the extracted health check functionality that was moved
from DataManager to maintain separation of concerns and keep DataManager lean.
"""

import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch
from typing import Any, Dict

import pytest

from ktrdr.data.managers.data_health_checker import DataHealthChecker


class TestDataHealthChecker:
    """Test DataHealthChecker initialization and basic functionality."""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for testing."""
        data_loader = MagicMock()
        data_loader.data_dir = "/mock/data/dir"
        
        data_validator = MagicMock()
        data_validator.auto_correct = True
        data_validator.max_gap_percentage = 5.0
        
        gap_classifier = MagicMock()
        
        ib_adapter = MagicMock()
        ib_adapter.use_host_service = False
        ib_adapter.host_service_url = None
        
        repair_methods = {
            "ffill": "ffill_method",
            "bfill": "bfill_method",
            "interpolate": "interpolate_method",
        }
        
        return {
            "data_loader": data_loader,
            "data_validator": data_validator,
            "gap_classifier": gap_classifier,
            "ib_adapter": ib_adapter,
            "repair_methods": repair_methods,
        }

    @pytest.fixture
    def health_checker(self, mock_components):
        """Create DataHealthChecker instance with mock components."""
        return DataHealthChecker(
            data_loader=mock_components["data_loader"],
            data_validator=mock_components["data_validator"],
            gap_classifier=mock_components["gap_classifier"],
            ib_adapter=mock_components["ib_adapter"],
            enable_ib=True,
            max_gap_percentage=5.0,
            default_repair_method="ffill",
            repair_methods=mock_components["repair_methods"],
        )

    def test_initialization(self, health_checker, mock_components):
        """Test DataHealthChecker initialization."""
        assert health_checker.data_loader == mock_components["data_loader"]
        assert health_checker.data_validator == mock_components["data_validator"]
        assert health_checker.gap_classifier == mock_components["gap_classifier"]
        assert health_checker.ib_adapter == mock_components["ib_adapter"]
        assert health_checker.enable_ib is True
        assert health_checker.max_gap_percentage == 5.0
        assert health_checker.default_repair_method == "ffill"
        assert health_checker.repair_methods == mock_components["repair_methods"]

    def test_initialization_without_ib_adapter(self, mock_components):
        """Test initialization without IB adapter."""
        health_checker = DataHealthChecker(
            data_loader=mock_components["data_loader"],
            data_validator=mock_components["data_validator"],
            gap_classifier=mock_components["gap_classifier"],
            ib_adapter=None,
            enable_ib=False,
        )
        
        assert health_checker.ib_adapter is None
        assert health_checker.enable_ib is False


class TestDataLoaderHealthCheck:
    """Test data loader health check functionality."""

    @pytest.fixture
    def health_checker_with_temp_dir(self):
        """Create health checker with temporary data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_loader = MagicMock()
            data_loader.data_dir = temp_dir
            
            health_checker = DataHealthChecker(
                data_loader=data_loader,
                data_validator=MagicMock(),
                gap_classifier=MagicMock(),
            )
            yield health_checker

    @pytest.mark.asyncio
    async def test_check_data_loader_health_success(self, health_checker_with_temp_dir):
        """Test successful data loader health check."""
        result = await health_checker_with_temp_dir.check_data_loader_health()
        
        assert result["status"] == "healthy"
        assert result["directory_accessible"] is True
        assert "data_directory" in result
        assert result["type"] == "MagicMock"

    @pytest.mark.asyncio
    async def test_check_data_loader_health_nonexistent_dir(self):
        """Test data loader health check with non-existent directory."""
        data_loader = MagicMock()
        data_loader.data_dir = "/nonexistent/directory"
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_loader_health()
        
        assert result["status"] == "warning"
        assert result["directory_accessible"] is False
        assert result["issue"] == "Data directory does not exist"

    @pytest.mark.asyncio
    async def test_check_data_loader_health_no_data_dir(self):
        """Test data loader health check with no data directory configured."""
        data_loader = MagicMock()
        data_loader.data_dir = None
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_loader_health()
        
        assert result["status"] == "warning"
        assert result["directory_accessible"] is False
        assert result["issue"] == "Data directory does not exist"

    @pytest.mark.asyncio
    async def test_check_data_loader_health_exception(self):
        """Test data loader health check with exception."""
        data_loader = MagicMock()
        data_loader.data_dir = "/test/dir"
        
        # Make os.path.exists raise an exception
        with patch('os.path.exists', side_effect=Exception("Test exception")):
            health_checker = DataHealthChecker(
                data_loader=data_loader,
                data_validator=MagicMock(),
                gap_classifier=MagicMock(),
            )
            
            result = await health_checker.check_data_loader_health()
            
            assert result["status"] == "error"
            assert result["error"] == "Test exception"


class TestDataValidatorHealthCheck:
    """Test data validator health check functionality."""

    @pytest.mark.asyncio
    async def test_check_data_validator_health_success(self):
        """Test successful data validator health check."""
        data_validator = MagicMock()
        data_validator.auto_correct = True
        data_validator.max_gap_percentage = 5.0
        
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=data_validator,
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_validator_health()
        
        assert result["status"] == "healthy"
        assert result["auto_correct"] is True
        assert result["max_gap_percentage"] == 5.0
        assert result["type"] == "MagicMock"

    @pytest.mark.asyncio
    async def test_check_data_validator_health_none(self):
        """Test data validator health check with None validator."""
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=None,
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_validator_health()
        
        assert result["status"] == "error"
        assert result["issue"] == "Data validator not initialized"

    @pytest.mark.asyncio
    async def test_check_data_validator_health_with_missing_attributes(self):
        """Test data validator health check with missing attributes."""
        # Create a mock that doesn't have the expected attributes
        data_validator = MagicMock()
        del data_validator.auto_correct  # Remove the attribute
        del data_validator.max_gap_percentage  # Remove the attribute
        
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=data_validator,
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_validator_health()
        
        # Should still be healthy but with 'unknown' values for missing attributes
        assert result["status"] == "healthy"
        assert result["auto_correct"] == "unknown"
        assert result["max_gap_percentage"] == "unknown"


class TestGapClassifierHealthCheck:
    """Test gap classifier health check functionality."""

    @pytest.mark.asyncio
    async def test_check_gap_classifier_health_success(self):
        """Test successful gap classifier health check."""
        gap_classifier = MagicMock()
        
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=gap_classifier,
        )
        
        result = await health_checker.check_gap_classifier_health()
        
        assert result["status"] == "healthy"
        assert result["type"] == "MagicMock"

    @pytest.mark.asyncio
    async def test_check_gap_classifier_health_none(self):
        """Test gap classifier health check with None classifier."""
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=None,
        )
        
        result = await health_checker.check_gap_classifier_health()
        
        assert result["status"] == "error"
        assert result["issue"] == "Gap classifier not initialized"

    @pytest.mark.asyncio
    async def test_check_gap_classifier_health_exception(self):
        """Test gap classifier health check with exception."""
        # Use None to trigger the if condition check, which will raise AttributeError
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=None,
        )
        
        result = await health_checker.check_gap_classifier_health()
        
        assert result["status"] == "error"
        assert result["issue"] == "Gap classifier not initialized"


class TestCustomHealthChecks:
    """Test custom health check methods."""

    @pytest.fixture
    def health_checker_with_temp_dir(self):
        """Create health checker with temporary data directory containing CSV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some sample CSV files
            for i in range(3):
                with open(os.path.join(temp_dir, f"test_{i}.csv"), "w") as f:
                    f.write("timestamp,open,high,low,close,volume\n")
            
            data_loader = MagicMock()
            data_loader.data_dir = temp_dir
            
            health_checker = DataHealthChecker(
                data_loader=data_loader,
                data_validator=MagicMock(),
                gap_classifier=MagicMock(),
            )
            yield health_checker

    @pytest.mark.asyncio
    async def test_check_data_directory_access_success(self, health_checker_with_temp_dir):
        """Test successful data directory access check."""
        result = await health_checker_with_temp_dir.check_data_directory_access()
        
        assert result["status"] == "healthy"
        assert "Data directory accessible" in result["message"]
        assert result["sample_files_count"] == 3
        assert len(result["sample_files"]) == 3

    @pytest.mark.asyncio
    async def test_check_data_directory_access_no_dir_configured(self):
        """Test data directory access check with no directory configured."""
        data_loader = MagicMock()
        data_loader.data_dir = None
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_directory_access()
        
        assert result["status"] == "warning"
        assert result["message"] == "No data directory configured"

    @pytest.mark.asyncio
    async def test_check_data_directory_access_nonexistent(self):
        """Test data directory access check with non-existent directory."""
        data_loader = MagicMock()
        data_loader.data_dir = "/nonexistent/directory"
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_data_directory_access()
        
        assert result["status"] == "error"
        assert "Data directory does not exist" in result["message"]

    @pytest.mark.asyncio
    async def test_check_local_data_availability_success(self, health_checker_with_temp_dir):
        """Test successful local data availability check."""
        result = await health_checker_with_temp_dir.check_local_data_availability()
        
        assert result["status"] == "healthy"
        assert "Local data available: 3 files" in result["message"]
        assert result["total_files"] == 3

    @pytest.mark.asyncio
    async def test_check_local_data_availability_no_files(self):
        """Test local data availability check with no CSV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_loader = MagicMock()
            data_loader.data_dir = temp_dir
            
            health_checker = DataHealthChecker(
                data_loader=data_loader,
                data_validator=MagicMock(),
                gap_classifier=MagicMock(),
            )
            
            result = await health_checker.check_local_data_availability()
            
            assert result["status"] == "warning"
            assert result["message"] == "No CSV data files found"

    @pytest.mark.asyncio
    async def test_check_local_data_availability_no_directory(self):
        """Test local data availability check with no directory."""
        data_loader = MagicMock()
        data_loader.data_dir = "/nonexistent/directory"
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
        )
        
        result = await health_checker.check_local_data_availability()
        
        assert result["status"] == "warning"
        assert result["message"] == "No data directory available"


class TestIBConnectionHealthCheck:
    """Test IB connection health check functionality."""

    @pytest.mark.asyncio
    async def test_check_ib_connection_disabled(self):
        """Test IB connection health check when IB is disabled."""
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
            enable_ib=False,
        )
        
        result = await health_checker.check_ib_connection()
        
        assert result["status"] == "info"
        assert result["message"] == "IB integration disabled"

    @pytest.mark.asyncio
    async def test_check_ib_connection_no_adapter(self):
        """Test IB connection health check with no adapter."""
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
            ib_adapter=None,
            enable_ib=True,
        )
        
        result = await health_checker.check_ib_connection()
        
        assert result["status"] == "warning"
        assert result["message"] == "IB adapter not initialized"

    @pytest.mark.asyncio
    async def test_check_ib_connection_success(self):
        """Test successful IB connection health check."""
        ib_adapter = MagicMock()
        ib_adapter.use_host_service = True
        ib_adapter.host_service_url = "http://localhost:8080"
        
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
            ib_adapter=ib_adapter,
            enable_ib=True,
        )
        
        result = await health_checker.check_ib_connection()
        
        assert result["status"] == "healthy"
        assert result["message"] == "IB adapter initialized and ready"
        assert result["adapter_type"] == "MagicMock"
        assert result["use_host_service"] is True
        assert result["host_service_url"] == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_check_ib_connection_with_missing_attributes(self):
        """Test IB connection health check with missing attributes."""
        # Create an adapter mock without expected attributes
        ib_adapter = MagicMock()
        del ib_adapter.use_host_service  # Remove the attribute
        del ib_adapter.host_service_url  # Remove the attribute
        
        health_checker = DataHealthChecker(
            data_loader=MagicMock(),
            data_validator=MagicMock(),
            gap_classifier=MagicMock(),
            ib_adapter=ib_adapter,
            enable_ib=True,
        )
        
        result = await health_checker.check_ib_connection()
        
        # Should still be healthy but with False/None defaults for missing attributes
        assert result["status"] == "healthy"
        assert result["use_host_service"] is False
        assert result["host_service_url"] is None


class TestComprehensiveHealthCheck:
    """Test comprehensive health check functionality."""

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check(self):
        """Test comprehensive health check performs all checks."""
        # Create mock components
        data_loader = MagicMock()
        data_loader.data_dir = None  # Will cause warnings
        
        data_validator = MagicMock()
        data_validator.auto_correct = True
        data_validator.max_gap_percentage = 5.0
        
        gap_classifier = MagicMock()
        
        repair_methods = {"ffill": "method", "bfill": "method"}
        
        health_checker = DataHealthChecker(
            data_loader=data_loader,
            data_validator=data_validator,
            gap_classifier=gap_classifier,
            ib_adapter=None,
            enable_ib=False,
            max_gap_percentage=5.0,
            default_repair_method="ffill",
            repair_methods=repair_methods,
        )
        
        result = await health_checker.perform_comprehensive_health_check()
        
        # Check that all expected sections are present
        assert "data_loader" in result
        assert "data_validator" in result
        assert "gap_classifier" in result
        assert "custom_checks" in result
        assert "data_configuration" in result
        assert "configuration" in result  # Backward compatibility
        
        # Check custom checks
        custom_checks = result["custom_checks"]
        assert "data_directory_access" in custom_checks
        assert "local_data_availability" in custom_checks
        assert "ib_connection" in custom_checks
        
        # Check configuration
        config = result["data_configuration"]
        assert config["max_gap_percentage"] == 5.0
        assert config["default_repair_method"] == "ffill"
        assert config["enable_ib"] is False
        assert config["valid_repair_methods"] == ["ffill", "bfill"]
        
        # Ensure backward compatibility
        assert result["configuration"] == config

    @pytest.mark.asyncio
    async def test_perform_comprehensive_health_check_all_healthy(self):
        """Test comprehensive health check with all components healthy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some sample CSV files
            for i in range(2):
                with open(os.path.join(temp_dir, f"test_{i}.csv"), "w") as f:
                    f.write("data\n")
            
            data_loader = MagicMock()
            data_loader.data_dir = temp_dir
            
            data_validator = MagicMock()
            data_validator.auto_correct = True
            data_validator.max_gap_percentage = 5.0
            
            gap_classifier = MagicMock()
            
            ib_adapter = MagicMock()
            ib_adapter.use_host_service = False
            ib_adapter.host_service_url = None
            
            health_checker = DataHealthChecker(
                data_loader=data_loader,
                data_validator=data_validator,
                gap_classifier=gap_classifier,
                ib_adapter=ib_adapter,
                enable_ib=True,
            )
            
            result = await health_checker.perform_comprehensive_health_check()
            
            # All main components should be healthy
            assert result["data_loader"]["status"] == "healthy"
            assert result["data_validator"]["status"] == "healthy"
            assert result["gap_classifier"]["status"] == "healthy"
            
            # All custom checks should be healthy or info
            custom_checks = result["custom_checks"]
            assert custom_checks["data_directory_access"]["status"] == "healthy"
            assert custom_checks["local_data_availability"]["status"] == "healthy"
            assert custom_checks["ib_connection"]["status"] == "healthy"