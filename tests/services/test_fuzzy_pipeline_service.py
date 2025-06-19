"""
Tests for fuzzy pipeline service.
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from ktrdr.services.fuzzy_pipeline_service import (
    FuzzyPipelineService,
    create_fuzzy_pipeline_service,
)
from ktrdr.fuzzy.indicator_integration import IntegratedFuzzyResult
from ktrdr.fuzzy.multi_timeframe_engine import MultiTimeframeFuzzyResult
from ktrdr.errors import ProcessingError, ConfigurationError


class TestFuzzyPipelineService:
    """Tests for FuzzyPipelineService."""

    @pytest.fixture
    def mock_data_manager(self):
        """Mock DataManager."""
        mock_dm = Mock()

        # Sample market data
        dates = pd.date_range("2024-01-01", periods=100, freq="1h")
        sample_data = pd.DataFrame(
            {
                "open": np.random.uniform(100, 110, len(dates)),
                "high": np.random.uniform(105, 115, len(dates)),
                "low": np.random.uniform(95, 105, len(dates)),
                "close": np.random.uniform(100, 110, len(dates)),
                "volume": np.random.uniform(1000, 10000, len(dates)),
            },
            index=dates,
        )

        mock_dm.get_data.return_value = sample_data
        return mock_dm

    @pytest.fixture
    def sample_indicator_config_dict(self):
        """Sample indicator configuration as dictionary."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": [
                        {"type": "RSI", "period": 14},
                        {"type": "MACD", "fast_period": 12, "slow_period": 26},
                    ]
                }
            }
        }

    @pytest.fixture
    def sample_fuzzy_config_dict(self):
        """Sample fuzzy configuration as dictionary."""
        return {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi", "macd"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 20, 40]},
                            "high": {"type": "triangular", "parameters": [60, 80, 100]},
                        },
                        "macd": {
                            "negative": {
                                "type": "triangular",
                                "parameters": [-1, -0.5, 0],
                            },
                            "positive": {
                                "type": "triangular",
                                "parameters": [0, 0.5, 1],
                            },
                        },
                    },
                    "weight": 1.0,
                    "enabled": True,
                }
            },
            "indicators": ["rsi", "macd"],
        }

    @pytest.fixture
    def sample_config_files(
        self, sample_indicator_config_dict, sample_fuzzy_config_dict
    ):
        """Create temporary config files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create indicator config file
            indicator_file = Path(temp_dir) / "indicator_config.yaml"
            with open(indicator_file, "w") as f:
                yaml.dump(sample_indicator_config_dict, f)

            # Create fuzzy config file
            fuzzy_file = Path(temp_dir) / "fuzzy_config.yaml"
            with open(fuzzy_file, "w") as f:
                yaml.dump(sample_fuzzy_config_dict, f)

            yield indicator_file, fuzzy_file

    def test_service_initialization(self, mock_data_manager):
        """Test service initialization."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager, enable_caching=True, cache_ttl_seconds=300
        )

        assert service.data_manager == mock_data_manager
        assert service.enable_caching is True
        assert service.cache_ttl_seconds == 300
        assert len(service._pipeline_cache) == 0
        assert len(service._result_cache) == 0

    def test_service_initialization_default_data_manager(self):
        """Test service initialization with default data manager."""
        service = FuzzyPipelineService()

        assert service.data_manager is not None
        assert service.enable_caching is True

    @patch("ktrdr.services.fuzzy_pipeline_service.create_integrated_pipeline")
    def test_process_symbol_fuzzy_with_dicts(
        self,
        mock_create_pipeline,
        mock_data_manager,
        sample_indicator_config_dict,
        sample_fuzzy_config_dict,
    ):
        """Test processing symbol with dictionary configurations."""
        # Mock pipeline
        mock_pipeline = Mock()
        mock_create_pipeline.return_value = mock_pipeline
        mock_pipeline.get_supported_timeframes.return_value = ["1h"]

        # Mock pipeline result
        mock_fuzzy_result = MultiTimeframeFuzzyResult(
            fuzzy_values={"rsi_low_1h": 0.8},
            timeframe_results={"1h": {"rsi_low": 0.8}},
            metadata={"processed_timeframes": ["1h"]},
            warnings=[],
            processing_time=0.05,
        )

        mock_integrated_result = IntegratedFuzzyResult(
            fuzzy_result=mock_fuzzy_result,
            indicator_data={"1h": {"rsi": 35.0}},
            processing_metadata={},
            errors=[],
            warnings=[],
            total_processing_time=0.1,
        )

        mock_pipeline.process_market_data.return_value = mock_integrated_result

        # Create service and process
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        result = service.process_symbol_fuzzy(
            symbol="AAPL",
            indicator_config=sample_indicator_config_dict,
            fuzzy_config=sample_fuzzy_config_dict,
            timeframes=["1h"],
            data_period_days=30,
        )

        # Verify
        assert isinstance(result, IntegratedFuzzyResult)
        assert result.processing_metadata["symbol"] == "AAPL"
        assert result.processing_metadata["service_version"] == "1.0.0"
        assert result.processing_metadata["data_period_days"] == 30

        # Verify data manager was called
        mock_data_manager.get_data.assert_called_with(
            symbol="AAPL", timeframe="1h", period_days=30
        )

    def test_process_symbol_fuzzy_with_files(
        self, mock_data_manager, sample_config_files
    ):
        """Test processing symbol with file configurations."""
        indicator_file, fuzzy_file = sample_config_files

        with patch(
            "ktrdr.services.fuzzy_pipeline_service.create_integrated_pipeline"
        ) as mock_create:
            # Mock pipeline
            mock_pipeline = Mock()
            mock_create.return_value = mock_pipeline
            mock_pipeline.get_supported_timeframes.return_value = ["1h"]

            # Mock result
            mock_fuzzy_result = MultiTimeframeFuzzyResult({}, {}, {}, [], 0.0)
            mock_integrated_result = IntegratedFuzzyResult(
                fuzzy_result=mock_fuzzy_result,
                indicator_data={},
                processing_metadata={},
                errors=[],
                warnings=[],
                total_processing_time=0.1,
            )
            mock_pipeline.process_market_data.return_value = mock_integrated_result

            # Create service and process
            service = FuzzyPipelineService(data_manager=mock_data_manager)

            result = service.process_symbol_fuzzy(
                symbol="AAPL",
                indicator_config=str(indicator_file),
                fuzzy_config=str(fuzzy_file),
            )

            assert isinstance(result, IntegratedFuzzyResult)

    def test_load_configuration_invalid_file(self, mock_data_manager):
        """Test loading configuration from non-existent file."""
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        with pytest.raises(ConfigurationError) as exc_info:
            service._load_configuration("/non/existent/file.yaml", "indicator")
        assert "configuration file not found" in str(exc_info.value)

    def test_load_configuration_invalid_type(self, mock_data_manager):
        """Test loading configuration with invalid type."""
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        with pytest.raises(ConfigurationError) as exc_info:
            service._load_configuration(123, "indicator")  # Invalid type
        assert "Invalid indicator configuration type" in str(exc_info.value)

    @patch("ktrdr.services.fuzzy_pipeline_service.create_integrated_pipeline")
    def test_process_multiple_symbols(
        self,
        mock_create_pipeline,
        mock_data_manager,
        sample_indicator_config_dict,
        sample_fuzzy_config_dict,
    ):
        """Test processing multiple symbols."""
        # Mock pipeline
        mock_pipeline = Mock()
        mock_create_pipeline.return_value = mock_pipeline
        mock_pipeline.get_supported_timeframes.return_value = ["1h"]

        # Mock result
        mock_fuzzy_result = MultiTimeframeFuzzyResult({}, {}, {}, [], 0.0)
        mock_integrated_result = IntegratedFuzzyResult(
            fuzzy_result=mock_fuzzy_result,
            indicator_data={},
            processing_metadata={},
            errors=[],
            warnings=[],
            total_processing_time=0.1,
        )
        mock_pipeline.process_market_data.return_value = mock_integrated_result

        # Create service and process
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        results = service.process_multiple_symbols(
            symbols=["AAPL", "GOOGL", "MSFT"],
            indicator_config=sample_indicator_config_dict,
            fuzzy_config=sample_fuzzy_config_dict,
        )

        assert len(results) == 3
        assert "AAPL" in results
        assert "GOOGL" in results
        assert "MSFT" in results

        for symbol, result in results.items():
            assert isinstance(result, IntegratedFuzzyResult)

    @patch("ktrdr.services.fuzzy_pipeline_service.create_integrated_pipeline")
    def test_process_multiple_symbols_with_error(
        self,
        mock_create_pipeline,
        mock_data_manager,
        sample_indicator_config_dict,
        sample_fuzzy_config_dict,
    ):
        """Test processing multiple symbols with one failing."""
        # Mock pipeline that fails for GOOGL
        mock_pipeline = Mock()
        mock_create_pipeline.return_value = mock_pipeline
        mock_pipeline.get_supported_timeframes.return_value = ["1h"]

        def side_effect(*args, **kwargs):
            # Check if data was requested for GOOGL (will be in market data)
            market_data = args[0] if args else kwargs.get("market_data", {})
            if mock_data_manager.get_data.call_count == 2:  # Second call is for GOOGL
                raise Exception("Failed to process GOOGL")

            # Return successful result for other symbols
            mock_fuzzy_result = MultiTimeframeFuzzyResult({}, {}, {}, [], 0.0)
            return IntegratedFuzzyResult(
                fuzzy_result=mock_fuzzy_result,
                indicator_data={},
                processing_metadata={},
                errors=[],
                warnings=[],
                total_processing_time=0.1,
            )

        mock_pipeline.process_market_data.side_effect = side_effect

        # Create service and process with continue_on_error=True
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        # Mock data manager to fail for GOOGL
        def get_data_side_effect(symbol, timeframe, period_days):
            if symbol == "GOOGL":
                raise Exception("Failed to get data for GOOGL")
            # Return successful data for other symbols
            dates = pd.date_range("2024-01-01", periods=100, freq="1h")
            return pd.DataFrame(
                {
                    "open": np.random.uniform(100, 110, len(dates)),
                    "high": np.random.uniform(105, 115, len(dates)),
                    "low": np.random.uniform(95, 105, len(dates)),
                    "close": np.random.uniform(100, 110, len(dates)),
                    "volume": np.random.uniform(1000, 10000, len(dates)),
                },
                index=dates,
            )

        mock_data_manager.get_data.side_effect = get_data_side_effect

        results = service.process_multiple_symbols(
            symbols=["AAPL", "GOOGL", "MSFT"],
            indicator_config=sample_indicator_config_dict,
            fuzzy_config=sample_fuzzy_config_dict,
            continue_on_error=True,
        )

        # Should have results for AAPL and MSFT, but not GOOGL
        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results
        assert "GOOGL" not in results

    def test_create_single_symbol_report(self, mock_data_manager):
        """Test creating summary report for single symbol."""
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        # Create sample result
        mock_fuzzy_result = MultiTimeframeFuzzyResult(
            fuzzy_values={
                "rsi_low_1h": 0.8,
                "macd_positive_1h": 0.6,
                "rsi_high_4h": 0.3,
            },
            timeframe_results={
                "1h": {"rsi_low": 0.8, "macd_positive": 0.6},
                "4h": {"rsi_high": 0.3},
            },
            metadata={"processed_timeframes": ["1h", "4h"]},
            warnings=["Minor warning"],
            processing_time=0.05,
        )

        integrated_result = IntegratedFuzzyResult(
            fuzzy_result=mock_fuzzy_result,
            indicator_data={"1h": {"rsi": 35.0, "macd": 0.1}},
            processing_metadata={
                "indicator_processing_time": 0.03,
                "fuzzy_processing_time": 0.02,
            },
            errors=[],
            warnings=["Service warning"],
            total_processing_time=0.1,
        )

        report = service.create_fuzzy_summary_report(integrated_result)

        # Verify report structure
        assert "summary" in report
        assert "timeframe_breakdown" in report
        assert "top_fuzzy_values" in report
        assert "performance" in report

        # Verify summary
        summary = report["summary"]
        assert summary["total_fuzzy_values"] == 3
        assert summary["processed_timeframes"] == 2
        assert summary["success"] is True
        assert summary["error_count"] == 0
        assert summary["warning_count"] == 1

        # Verify timeframe breakdown
        tf_breakdown = report["timeframe_breakdown"]
        assert "1h" in tf_breakdown
        assert "4h" in tf_breakdown
        assert tf_breakdown["1h"]["fuzzy_value_count"] == 2
        assert tf_breakdown["4h"]["fuzzy_value_count"] == 1

        # Verify top fuzzy values (sorted by value)
        top_values = report["top_fuzzy_values"]
        assert len(top_values) == 3
        values_list = list(top_values.values())
        assert values_list[0] >= values_list[1] >= values_list[2]  # Should be sorted

        # Verify performance metrics
        performance = report["performance"]
        assert performance["total_time"] == 0.1
        assert performance["indicator_time"] == 0.03
        assert performance["fuzzy_time"] == 0.02

    def test_create_multi_symbol_report(self, mock_data_manager):
        """Test creating summary report for multiple symbols."""
        service = FuzzyPipelineService(data_manager=mock_data_manager)

        # Create sample results for multiple symbols
        results = {}
        for symbol in ["AAPL", "GOOGL", "MSFT"]:
            mock_fuzzy_result = MultiTimeframeFuzzyResult(
                fuzzy_values={"rsi_low_1h": 0.8, "macd_positive_1h": 0.6},
                timeframe_results={"1h": {"rsi_low": 0.8, "macd_positive": 0.6}},
                metadata={"processed_timeframes": ["1h"]},
                warnings=[],
                processing_time=0.05,
            )

            results[symbol] = IntegratedFuzzyResult(
                fuzzy_result=mock_fuzzy_result,
                indicator_data={"1h": {"rsi": 35.0}},
                processing_metadata={},
                errors=[],
                warnings=[],
                total_processing_time=0.1,
            )

        report = service.create_fuzzy_summary_report(results)

        # Verify report structure
        assert "summary" in report
        assert "symbol_results" in report
        assert "aggregated_metrics" in report

        # Verify summary
        summary = report["summary"]
        assert summary["total_symbols"] == 3
        assert summary["successful_symbols"] == 3
        assert summary["failed_symbols"] == 0
        assert summary["success_rate"] == 1.0

        # Verify symbol results
        symbol_results = report["symbol_results"]
        assert len(symbol_results) == 3
        for symbol in ["AAPL", "GOOGL", "MSFT"]:
            assert symbol in symbol_results
            assert "summary" in symbol_results[symbol]

        # Verify aggregated metrics
        agg_metrics = report["aggregated_metrics"]
        assert agg_metrics["avg_fuzzy_values_per_symbol"] == 2.0
        assert agg_metrics["total_fuzzy_values"] == 6
        assert abs(agg_metrics["avg_processing_time"] - 0.1) < 1e-10
        assert abs(agg_metrics["total_processing_time"] - 0.3) < 1e-10

    def test_get_service_health(self, mock_data_manager):
        """Test service health check."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager, enable_caching=True, cache_ttl_seconds=300
        )

        health = service.get_service_health()

        assert "data_manager" in health
        assert "caching" in health
        assert "status" in health

        # Verify data manager info
        dm_info = health["data_manager"]
        assert dm_info["initialized"] is True
        assert "type" in dm_info

        # Verify caching info
        caching_info = health["caching"]
        assert caching_info["enabled"] is True
        assert caching_info["pipeline_cache_size"] == 0
        assert caching_info["result_cache_size"] == 0
        assert caching_info["cache_ttl_seconds"] == 300

        assert health["status"] == "healthy"

    def test_factory_function(self):
        """Test factory function for creating service."""
        service = create_fuzzy_pipeline_service(
            enable_caching=False, cache_ttl_seconds=600
        )

        assert isinstance(service, FuzzyPipelineService)
        assert service.enable_caching is False
        assert service.cache_ttl_seconds == 600

    def test_pipeline_caching(
        self, mock_data_manager, sample_indicator_config_dict, sample_fuzzy_config_dict
    ):
        """Test pipeline caching functionality."""
        service = FuzzyPipelineService(
            data_manager=mock_data_manager, enable_caching=True
        )

        # Get pipeline (should create new one)
        pipeline1 = service._get_or_create_pipeline(
            sample_indicator_config_dict, sample_fuzzy_config_dict
        )

        # Get pipeline again (should use cached one)
        pipeline2 = service._get_or_create_pipeline(
            sample_indicator_config_dict, sample_fuzzy_config_dict
        )

        # Should be the same object
        assert pipeline1 is pipeline2
        assert len(service._pipeline_cache) == 1

    @patch("ktrdr.services.fuzzy_pipeline_service.create_integrated_pipeline")
    def test_no_market_data_error(
        self,
        mock_create_pipeline,
        mock_data_manager,
        sample_indicator_config_dict,
        sample_fuzzy_config_dict,
    ):
        """Test handling when no market data is available."""
        # Mock data manager to return None
        mock_data_manager.get_data.return_value = None

        # Mock pipeline
        mock_pipeline = Mock()
        mock_create_pipeline.return_value = mock_pipeline
        mock_pipeline.get_supported_timeframes.return_value = ["1h"]

        service = FuzzyPipelineService(data_manager=mock_data_manager)

        with pytest.raises(ProcessingError) as exc_info:
            service.process_symbol_fuzzy(
                symbol="AAPL",
                indicator_config=sample_indicator_config_dict,
                fuzzy_config=sample_fuzzy_config_dict,
            )
        # Error message could be wrapped in a higher-level message
        error_msg = str(exc_info.value)
        assert ("No market data available" in error_msg or 
                "Fuzzy analysis failed" in error_msg)
