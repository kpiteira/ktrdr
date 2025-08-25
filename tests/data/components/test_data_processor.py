"""
Test suite for DataProcessor component.

Tests the extraction of data processing logic from DataManager into
a dedicated component for data validation, cleaning, and transformation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from ktrdr.data.components.data_processor import DataProcessor, ProcessorConfig, ValidationResult
from ktrdr.errors import DataValidationError


class TestProcessorConfig:
    """Test ProcessorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ProcessorConfig()
        
        assert config.remove_duplicates is True
        assert config.fill_gaps is True
        assert config.validate_ohlc is True
        assert config.max_gap_tolerance == timedelta(hours=1)
        assert config.timezone_conversion is True


class TestDataProcessor:
    """Test DataProcessor component functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ProcessorConfig()

    @pytest.fixture
    def processor(self, config):
        """Create DataProcessor instance."""
        return DataProcessor(config)

    @pytest.fixture
    def valid_ohlc_data(self):
        """Create valid OHLC test data."""
        dates = pd.date_range(
            start='2023-01-01 09:30:00', 
            periods=100, 
            freq='1h',
            tz='UTC'
        )
        return pd.DataFrame({
            'open': np.random.uniform(100, 110, 100),
            'high': np.random.uniform(110, 120, 100), 
            'low': np.random.uniform(90, 100, 100),
            'close': np.random.uniform(100, 110, 100),
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)

    @pytest.fixture
    def invalid_ohlc_data(self):
        """Create invalid OHLC test data with constraint violations."""
        dates = pd.date_range(
            start='2023-01-01 09:30:00', 
            periods=5, 
            freq='1h',
            tz='UTC'
        )
        return pd.DataFrame({
            'open': [100, 105, 102, 108, 106],
            'high': [95, 107, 104, 110, 108],  # high < open in first row
            'low': [98, 103, 100, 106, 104],   # low > open in first row
            'close': [102, 106, 103, 109, 107],
            'volume': [1000, 1500, 1200, 1800, 1300]
        }, index=dates)

    @pytest.fixture
    def data_with_duplicates(self):
        """Create data with duplicate timestamps."""
        dates = pd.date_range(
            start='2023-01-01 09:30:00', 
            periods=5, 
            freq='1h',
            tz='UTC'
        )
        # Add duplicate of second timestamp
        dates = dates.insert(2, dates[1])
        
        return pd.DataFrame({
            'open': [100, 105, 105, 102, 108, 106],   # Duplicate values for duplicate timestamp
            'high': [102, 107, 107, 104, 110, 108],
            'low': [98, 103, 103, 100, 106, 104],
            'close': [101, 106, 106, 103, 109, 107],
            'volume': [1000, 1500, 1500, 1200, 1800, 1300]
        }, index=dates)

    @pytest.fixture  
    def data_with_gaps(self):
        """Create data with missing time periods (gaps)."""
        # Create non-continuous timestamps (missing 2-hour gap)
        dates1 = pd.date_range(start='2023-01-01 09:30:00', periods=3, freq='1h', tz='UTC')
        dates2 = pd.date_range(start='2023-01-01 14:30:00', periods=3, freq='1h', tz='UTC') 
        dates = dates1.union(dates2)
        
        return pd.DataFrame({
            'open': [100, 105, 102, 108, 106, 104],
            'high': [102, 107, 104, 110, 108, 106],
            'low': [98, 103, 100, 106, 104, 102],
            'close': [101, 106, 103, 109, 107, 105],
            'volume': [1000, 1500, 1200, 1800, 1300, 1400]
        }, index=dates)

    def test_init_creates_validators(self, config):
        """Test that DataProcessor initializes validators correctly."""
        # This test should fail initially since DataProcessor doesn't exist yet
        processor = DataProcessor(config)
        assert hasattr(processor, 'config')
        assert hasattr(processor, 'validators')
        assert processor.config == config

    def test_process_raw_data_pipeline(self, processor, valid_ohlc_data):
        """Test main processing pipeline: validate -> clean -> transform."""
        # This test should fail initially
        result = processor.process_raw_data(valid_ohlc_data, 'AAPL', '1h')
        
        # Should return processed DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert all(col in result.columns for col in ['open', 'high', 'low', 'close', 'volume'])

    def test_validate_data_integrity_valid_data(self, processor, valid_ohlc_data):
        """Test data integrity validation with valid data."""
        # This test should fail initially
        result = processor.validate_data_integrity(valid_ohlc_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_data_integrity_invalid_ohlc(self, processor, invalid_ohlc_data):
        """Test data integrity validation catches OHLC constraint violations."""
        # This test should fail initially
        result = processor.validate_data_integrity(invalid_ohlc_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert any('OHLC constraint violation' in error for error in result.errors)

    def test_clean_data_removes_duplicates(self, processor, data_with_duplicates):
        """Test that clean_data removes duplicate timestamps."""
        # This test should fail initially
        cleaned = processor.clean_data(data_with_duplicates)
        
        assert len(cleaned) < len(data_with_duplicates)
        assert cleaned.index.is_unique
        # Should have 5 unique timestamps (original had 6 with 1 duplicate)
        assert len(cleaned) == 5

    def test_clean_data_preserves_data_when_no_duplicates(self, processor, valid_ohlc_data):
        """Test that clean_data preserves data when no cleaning needed."""
        # This test should fail initially
        cleaned = processor.clean_data(valid_ohlc_data)
        
        assert len(cleaned) == len(valid_ohlc_data)
        pd.testing.assert_frame_equal(cleaned, valid_ohlc_data)

    def test_apply_transformations_timezone_conversion(self, processor, valid_ohlc_data):
        """Test that transformations include timezone conversion."""
        # Create data with naive timestamps
        naive_data = valid_ohlc_data.copy()
        naive_data.index = naive_data.index.tz_localize(None)
        
        # This test should fail initially
        transformed = processor.apply_transformations(naive_data, 'AAPL')
        
        # Should have timezone-aware index
        assert transformed.index.tz is not None
        assert str(transformed.index.tz) == 'UTC'

    def test_apply_transformations_symbol_specific(self, processor, valid_ohlc_data):
        """Test that transformations can be symbol-specific."""
        # This test should fail initially
        result_aapl = processor.apply_transformations(valid_ohlc_data, 'AAPL')
        result_googl = processor.apply_transformations(valid_ohlc_data, 'GOOGL')
        
        # Results should be DataFrames (specific transformations TBD based on existing logic)
        assert isinstance(result_aapl, pd.DataFrame)
        assert isinstance(result_googl, pd.DataFrame)

    def test_configuration_controls_behavior(self, valid_ohlc_data, data_with_duplicates):
        """Test that configuration controls processing behavior."""
        # Config with duplicates removal disabled
        config_no_duplicates = ProcessorConfig(remove_duplicates=False)
        processor_no_clean = DataProcessor(config_no_duplicates)
        
        # This test should fail initially
        result = processor_no_clean.clean_data(data_with_duplicates)
        
        # Should not remove duplicates when disabled
        assert len(result) == len(data_with_duplicates)

    def test_thread_safety(self, processor, valid_ohlc_data):
        """Test that processor can handle concurrent operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def process_data():
            try:
                result = processor.process_raw_data(valid_ohlc_data, 'AAPL', '1h')
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # This test should fail initially
        threads = [threading.Thread(target=process_data) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All threads should complete successfully
        assert len(errors) == 0
        assert len(results) == 5
        # All results should be equivalent
        for result in results[1:]:
            pd.testing.assert_frame_equal(results[0], result)


class TestValidationResult:
    """Test ValidationResult data class."""
    
    def test_validation_result_creation(self):
        """Test ValidationResult can be created with proper attributes."""
        # This test should fail initially since ValidationResult doesn't exist yet
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []

    def test_validation_result_with_errors(self):
        """Test ValidationResult with validation errors."""
        errors = ['OHLC constraint violation', 'Missing required column']
        warnings = ['Data gap detected']
        
        # This test should fail initially
        result = ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        
        assert result.is_valid is False
        assert result.errors == errors
        assert result.warnings == warnings


class TestIntegrationWithDataQualityValidator:
    """Test integration with existing DataQualityValidator."""
    
    def test_uses_existing_validator_logic(self):
        """Test that DataProcessor integrates with existing DataQualityValidator."""
        config = ProcessorConfig()
        processor = DataProcessor(config)
        
        # This test should fail initially
        # Should use existing DataQualityValidator for validation logic
        assert hasattr(processor, 'validators')
        # Specific validator integration tests will be added after extraction