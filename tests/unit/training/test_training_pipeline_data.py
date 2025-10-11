"""
Unit tests for TrainingPipeline data loading methods.

Tests the pure data loading and validation functions EXTRACTED from
local (StrategyTrainer) and host (TrainingService) training paths.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from ktrdr.training.training_pipeline import TrainingPipeline


class TestTrainingPipelineDataLoading:
    """Test TrainingPipeline data loading methods (extracted from StrategyTrainer)."""

    def test_load_market_data_single_timeframe(self):
        """Test loading data for a single timeframe (extracted logic)."""
        # Arrange
        symbol = "EURUSD"
        timeframes = ["1h"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"

        # Mock DataManager
        mock_dm = MagicMock()
        mock_data = pd.DataFrame(
            {
                "open": [1.10, 1.11, 1.12],
                "high": [1.11, 1.12, 1.13],
                "low": [1.09, 1.10, 1.11],
                "close": [1.11, 1.12, 1.12],
                "volume": [1000, 1100, 1050],
            },
            index=pd.date_range(start="2024-01-01", periods=3, freq="1h"),
        )
        mock_dm.load_data.return_value = mock_data

        # Act
        result = TrainingPipeline.load_market_data(
            symbol=symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            data_mode="local",
            data_manager=mock_dm,
        )

        # Assert
        assert isinstance(result, dict)
        assert "1h" in result
        assert len(result["1h"]) == 3
        # Verify dates are passed to load_data for efficient filtering
        mock_dm.load_data.assert_called_once_with(
            symbol, "1h", start_date=start_date, end_date=end_date, mode="local"
        )

    def test_load_market_data_multi_timeframe(self):
        """Test loading data for multiple timeframes (extracted logic)."""
        # Arrange
        symbol = "EURUSD"
        timeframes = ["1h", "4h"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"

        # Mock DataManager and MultiTimeframeCoordinator
        mock_dm = MagicMock()
        mock_mtc = MagicMock()

        # Mock multi-timeframe data
        mock_multi_data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10, 1.11],
                    "high": [1.11, 1.12],
                    "low": [1.09, 1.10],
                    "close": [1.11, 1.12],
                    "volume": [1000, 1100],
                },
                index=pd.date_range(start="2024-01-01", periods=2, freq="1h"),
            ),
            "4h": pd.DataFrame(
                {
                    "open": [1.10],
                    "high": [1.11],
                    "low": [1.09],
                    "close": [1.11],
                    "volume": [4000],
                },
                index=pd.date_range(start="2024-01-01", periods=1, freq="4h"),
            ),
        }
        mock_mtc.load_multi_timeframe_data.return_value = mock_multi_data

        # Act
        result = TrainingPipeline.load_market_data(
            symbol=symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            data_mode="local",
            data_manager=mock_dm,
            multi_timeframe_coordinator=mock_mtc,
        )

        # Assert
        assert isinstance(result, dict)
        assert "1h" in result
        assert "4h" in result
        assert len(result["1h"]) == 2
        assert len(result["4h"]) == 1
        mock_mtc.load_multi_timeframe_data.assert_called_once()

    def test_load_market_data_multi_timeframe_partial_success(self):
        """Test handling of partial multi-timeframe loading."""
        # Arrange
        symbol = "EURUSD"
        timeframes = ["1h", "4h", "1d"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"

        mock_dm = MagicMock()
        mock_mtc = MagicMock()

        # Only return 2 out of 3 timeframes (simulating partial failure)
        mock_multi_data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10],
                    "high": [1.11],
                    "low": [1.09],
                    "close": [1.11],
                    "volume": [1000],
                },
                index=pd.date_range(start="2024-01-01", periods=1, freq="1h"),
            ),
            "4h": pd.DataFrame(
                {
                    "open": [1.10],
                    "high": [1.11],
                    "low": [1.09],
                    "close": [1.11],
                    "volume": [4000],
                },
                index=pd.date_range(start="2024-01-01", periods=1, freq="4h"),
            ),
        }
        mock_mtc.load_multi_timeframe_data.return_value = mock_multi_data

        # Act
        result = TrainingPipeline.load_market_data(
            symbol=symbol,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date,
            data_mode="local",
            data_manager=mock_dm,
            multi_timeframe_coordinator=mock_mtc,
        )

        # Assert - should succeed with warning (partial success is allowed)
        assert isinstance(result, dict)
        assert len(result) == 2  # Only 2 out of 3 timeframes

    def test_load_market_data_multi_timeframe_total_failure(self):
        """Test handling of complete multi-timeframe loading failure."""
        # Arrange
        symbol = "EURUSD"
        timeframes = ["1h", "4h"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"

        mock_dm = MagicMock()
        mock_mtc = MagicMock()

        # Return empty dict (total failure)
        mock_mtc.load_multi_timeframe_data.return_value = {}

        # Act & Assert
        with pytest.raises(ValueError, match="No timeframes successfully loaded"):
            TrainingPipeline.load_market_data(
                symbol=symbol,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                data_mode="local",
                data_manager=mock_dm,
                multi_timeframe_coordinator=mock_mtc,
            )

    # test_filter_data_by_date_range() removed
    # Date filtering is now delegated to DataManager.load_data() directly


class TestTrainingPipelineDataValidation:
    """Test TrainingPipeline data validation methods."""

    def test_validate_data_quality_valid_data(self):
        """Test validation passes for valid multi-timeframe data."""
        # Arrange
        data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10] * 150,
                    "high": [1.11] * 150,
                    "low": [1.09] * 150,
                    "close": [1.11] * 150,
                    "volume": [1000] * 150,
                },
                index=pd.date_range(start="2024-01-01", periods=150, freq="1h"),
            )
        }

        # Act
        result = TrainingPipeline.validate_data_quality(data, min_rows=100)

        # Assert
        assert result["valid"] is True
        assert result["timeframes_checked"] == 1
        assert result["total_rows"] == 150
        assert len(result["issues"]) == 0

    def test_validate_data_quality_insufficient_rows(self):
        """Test validation fails with insufficient data rows."""
        # Arrange
        data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10] * 50,
                    "high": [1.11] * 50,
                    "low": [1.09] * 50,
                    "close": [1.11] * 50,
                    "volume": [1000] * 50,
                },
                index=pd.date_range(start="2024-01-01", periods=50, freq="1h"),
            )
        }

        # Act
        result = TrainingPipeline.validate_data_quality(data, min_rows=100)

        # Assert
        assert result["valid"] is False
        assert "1h: Only 50 rows (< 100 required)" in result["issues"]

    def test_validate_data_quality_missing_columns(self):
        """Test validation fails when required columns are missing."""
        # Arrange
        data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10] * 150,
                    "high": [1.11] * 150,
                    # Missing: low, close, volume
                },
                index=pd.date_range(start="2024-01-01", periods=150, freq="1h"),
            )
        }

        # Act
        result = TrainingPipeline.validate_data_quality(data, min_rows=100)

        # Assert
        assert result["valid"] is False
        assert any("Missing columns" in issue for issue in result["issues"])
        assert any("low" in issue for issue in result["issues"])

    def test_validate_data_quality_excessive_nan_values(self):
        """Test validation fails with excessive NaN values."""
        # Arrange
        df = pd.DataFrame(
            {
                "open": [1.10] * 100,
                "high": [1.11] * 100,
                "low": [None] * 100,  # 100% NaN in one column = 20% overall
                "close": [1.11] * 100,
                "volume": [1000] * 100,
            },
            index=pd.date_range(start="2024-01-01", periods=100, freq="1h"),
        )

        data = {"1h": df}

        # Act
        result = TrainingPipeline.validate_data_quality(data, min_rows=100)

        # Assert
        assert result["valid"] is False
        assert any("missing values" in issue for issue in result["issues"])

    def test_validate_data_quality_multi_timeframe(self):
        """Test validation works correctly with multiple timeframes."""
        # Arrange
        data = {
            "1h": pd.DataFrame(
                {
                    "open": [1.10] * 150,
                    "high": [1.11] * 150,
                    "low": [1.09] * 150,
                    "close": [1.11] * 150,
                    "volume": [1000] * 150,
                },
                index=pd.date_range(start="2024-01-01", periods=150, freq="1h"),
            ),
            "4h": pd.DataFrame(
                {
                    "open": [1.10] * 100,
                    "high": [1.11] * 100,
                    "low": [1.09] * 100,
                    "close": [1.11] * 100,
                    "volume": [4000] * 100,
                },
                index=pd.date_range(start="2024-01-01", periods=100, freq="4h"),
            ),
        }

        # Act
        result = TrainingPipeline.validate_data_quality(data, min_rows=100)

        # Assert
        assert result["valid"] is True
        assert result["timeframes_checked"] == 2
        assert result["total_rows"] == 250  # 150 + 100
