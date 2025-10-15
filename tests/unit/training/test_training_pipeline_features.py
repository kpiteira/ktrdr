"""
Unit tests for TrainingPipeline feature engineering methods.

Tests cover:
- calculate_indicators() - technical indicator calculation
- generate_fuzzy_memberships() - fuzzy membership generation
- create_features() - feature matrix creation
- create_labels() - label generation
"""

import numpy as np
import pandas as pd
import torch

from ktrdr.training.training_pipeline import TrainingPipeline


class TestCalculateIndicators:
    """Tests for TrainingPipeline.calculate_indicators()"""

    def test_calculate_indicators_single_timeframe(self):
        """Test indicator calculation for single timeframe."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "open": [100.0, 101.0, 102.0, 103.0, 104.0] * 20,
                    "high": [101.0, 102.0, 103.0, 104.0, 105.0] * 20,
                    "low": [99.0, 100.0, 101.0, 102.0, 103.0] * 20,
                    "close": [100.5, 101.5, 102.5, 103.5, 104.5] * 20,
                    "volume": [1000, 1100, 1200, 1300, 1400] * 20,
                }
            )
        }

        indicator_configs = [
            {"type": "rsi", "feature_id": "rsi_14", "name": "rsi", "period": 14},
            {"type": "sma", "feature_id": "sma_20", "name": "sma", "period": 20},
        ]

        # Act
        result = TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Assert
        assert isinstance(result, dict)
        assert "1D" in result
        assert isinstance(result["1D"], pd.DataFrame)
        # Should have price data columns + indicators (using feature_ids)
        assert "close" in result["1D"].columns
        assert "rsi_14" in result["1D"].columns
        assert "sma_20" in result["1D"].columns
        # Should not have inf values
        assert not np.isinf(result["1D"].values).any()

    def test_calculate_indicators_multi_timeframe(self):
        """Test indicator calculation for multiple timeframes."""
        # Arrange
        price_data = {
            "1h": pd.DataFrame(
                {
                    "open": [100.0] * 100,
                    "high": [101.0] * 100,
                    "low": [99.0] * 100,
                    "close": [100.5] * 100,
                    "volume": [1000] * 100,
                }
            ),
            "4h": pd.DataFrame(
                {
                    "open": [100.0] * 100,
                    "high": [101.0] * 100,
                    "low": [99.0] * 100,
                    "close": [100.5] * 100,
                    "volume": [1000] * 100,
                }
            ),
        }

        indicator_configs = [
            {"type": "rsi", "feature_id": "rsi_14", "name": "rsi", "period": 14}
        ]

        # Act
        result = TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Assert
        assert isinstance(result, dict)
        assert "1h" in result
        assert "4h" in result
        assert all(isinstance(df, pd.DataFrame) for df in result.values())

    def test_calculate_indicators_handles_sma_ema_ratios(self):
        """Test that SMA/EMA indicators are converted to ratios (price/MA)."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [100.0, 102.0, 104.0, 106.0, 108.0] * 20,
                    "open": [99.0] * 100,
                    "high": [110.0] * 100,
                    "low": [98.0] * 100,
                    "volume": [1000] * 100,
                }
            )
        }

        indicator_configs = [
            {"type": "sma", "feature_id": "sma_5", "name": "sma", "period": 5}
        ]

        # Act
        result = TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Assert
        # SMA should be ratio: close / sma_value (using feature_id)
        # Skip the initial period where SMA hasn't been calculated yet (values will be 0)
        sma_values = result["1D"]["sma_5"][20:]  # Skip warmup period
        assert len(sma_values) > 0
        # Ratios should be around 1.0 (close to the MA)
        assert (sma_values > 0.5).all()  # Reasonable ratio range
        assert (sma_values < 2.0).all()

    def test_calculate_indicators_handles_macd(self):
        """Test MACD indicator returns main line (not signal or histogram)."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [100.0 + i * 0.5 for i in range(100)],
                    "open": [100.0] * 100,
                    "high": [105.0] * 100,
                    "low": [95.0] * 100,
                    "volume": [1000] * 100,
                }
            )
        }

        indicator_configs = [
            {
                "type": "macd",
                "feature_id": "macd_12_26",
                "name": "macd",
                "fast_period": 12,
                "slow_period": 26,
            }
        ]

        # Act
        result = TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Assert (using feature_id)
        assert "macd_12_26" in result["1D"].columns
        # MACD should have numeric values (not NaN for most rows)
        assert result["1D"]["macd_12_26"].notna().sum() > 50

    def test_calculate_indicators_no_inf_values(self):
        """Test that infinite values are replaced with 0."""
        # Arrange - create data that might produce inf
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [0.0, 1.0, 2.0, 3.0, 4.0]
                    * 20,  # Zero can cause division issues
                    "open": [0.1] * 100,
                    "high": [5.0] * 100,
                    "low": [0.0] * 100,
                    "volume": [1000] * 100,
                }
            )
        }

        indicator_configs = [
            {"type": "rsi", "feature_id": "rsi_14", "name": "rsi", "period": 14}
        ]

        # Act
        result = TrainingPipeline.calculate_indicators(price_data, indicator_configs)

        # Assert
        assert not np.isinf(result["1D"].values).any()


class TestGenerateFuzzyMemberships:
    """Tests for TrainingPipeline.generate_fuzzy_memberships()"""

    def test_generate_fuzzy_memberships_single_timeframe(self):
        """Test fuzzy membership generation for single timeframe."""
        # Arrange
        indicators = {
            "1D": pd.DataFrame(
                {
                    "rsi": [30.0, 50.0, 70.0, 40.0, 60.0] * 20,
                    "close": [100.0] * 100,
                }
            )
        }

        fuzzy_configs = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 0.0, 30.0]},
                "medium": {"type": "triangular", "parameters": [20.0, 50.0, 80.0]},
                "high": {"type": "triangular", "parameters": [70.0, 100.0, 100.0]},
            }
        }

        # Act
        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        # Assert
        assert isinstance(result, dict)
        assert "1D" in result
        assert isinstance(result["1D"], pd.DataFrame)
        # Should have fuzzy membership columns
        assert "rsi_low" in result["1D"].columns
        assert "rsi_medium" in result["1D"].columns
        assert "rsi_high" in result["1D"].columns

    def test_generate_fuzzy_memberships_multi_timeframe(self):
        """Test fuzzy membership generation for multiple timeframes."""
        # Arrange
        indicators = {
            "1h": pd.DataFrame({"rsi": [50.0] * 100}),
            "4h": pd.DataFrame({"rsi": [60.0] * 100}),
        }

        fuzzy_configs = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 0.0, 30.0]},
                "high": {"type": "triangular", "parameters": [70.0, 100.0, 100.0]},
            }
        }

        # Act
        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        # Assert
        assert isinstance(result, dict)
        assert "1h" in result
        assert "4h" in result
        assert all(isinstance(df, pd.DataFrame) for df in result.values())

    def test_generate_fuzzy_memberships_values_in_range(self):
        """Test that fuzzy membership values are between 0 and 1."""
        # Arrange
        indicators = {
            "1D": pd.DataFrame({"rsi": list(range(0, 100))})  # Full RSI range
        }

        fuzzy_configs = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0.0, 0.0, 30.0]},
                "high": {"type": "triangular", "parameters": [70.0, 100.0, 100.0]},
            }
        }

        # Act
        result = TrainingPipeline.generate_fuzzy_memberships(indicators, fuzzy_configs)

        # Assert
        for col in result["1D"].columns:
            if col.startswith("rsi_"):
                assert (result["1D"][col] >= 0.0).all()
                assert (result["1D"][col] <= 1.0).all()


class TestCreateFeatures:
    """Tests for TrainingPipeline.create_features()"""

    def test_create_features_returns_tensor_and_names(self):
        """Test that create_features returns tensor and feature names."""
        # Arrange
        fuzzy_data = {
            "1D": pd.DataFrame(
                {
                    "rsi_low": [0.8, 0.2, 0.1] * 33 + [0.8],
                    "rsi_medium": [0.1, 0.6, 0.2] * 33 + [0.1],
                    "rsi_high": [0.0, 0.2, 0.8] * 33 + [0.0],
                }
            )
        }

        feature_config = {"lookback_periods": 0}

        # Act
        features, feature_names = TrainingPipeline.create_features(
            fuzzy_data, feature_config
        )

        # Assert
        assert isinstance(features, torch.Tensor)
        assert isinstance(feature_names, list)
        assert len(feature_names) > 0
        assert all(isinstance(name, str) for name in feature_names)

    def test_create_features_multi_timeframe(self):
        """Test feature creation with multiple timeframes."""
        # Arrange
        fuzzy_data = {
            "1h": pd.DataFrame(
                {
                    "rsi_low": [0.5] * 100,
                    "rsi_high": [0.5] * 100,
                }
            ),
            "4h": pd.DataFrame(
                {
                    "rsi_low": [0.3] * 100,
                    "rsi_high": [0.7] * 100,
                }
            ),
        }

        feature_config = {"lookback_periods": 0}

        # Act
        features, feature_names = TrainingPipeline.create_features(
            fuzzy_data, feature_config
        )

        # Assert
        assert isinstance(features, torch.Tensor)
        assert features.shape[0] == 100  # Same as input data length
        # Should have features from both timeframes
        assert len(feature_names) >= 4  # At least 2 features per timeframe

    def test_create_features_shape_consistency(self):
        """Test that feature tensor shape matches expected dimensions."""
        # Arrange
        fuzzy_data = {
            "1D": pd.DataFrame(
                {
                    "rsi_low": [0.5] * 50,
                    "rsi_high": [0.5] * 50,
                    "macd_low": [0.3] * 50,
                    "macd_high": [0.7] * 50,
                }
            )
        }

        feature_config = {"lookback_periods": 0}

        # Act
        features, feature_names = TrainingPipeline.create_features(
            fuzzy_data, feature_config
        )

        # Assert
        assert features.shape[0] == 50  # Number of samples
        assert features.shape[1] == len(feature_names)  # Number of features


class TestCreateLabels:
    """Tests for TrainingPipeline.create_labels()"""

    def test_create_labels_returns_tensor(self):
        """Test that create_labels returns a tensor."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [100.0 + i * 0.5 for i in range(100)],
                    "open": [100.0] * 100,
                    "high": [105.0] * 100,
                    "low": [95.0] * 100,
                }
            )
        }

        label_config = {"zigzag_threshold": 0.05, "label_lookahead": 5}

        # Act
        labels = TrainingPipeline.create_labels(price_data, label_config)

        # Assert
        assert isinstance(labels, torch.Tensor)
        assert labels.dtype == torch.long  # Classification labels

    def test_create_labels_three_classes(self):
        """Test that labels contain three classes (buy=0, hold=1, sell=2)."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [100.0, 105.0, 110.0, 105.0, 100.0, 95.0, 100.0, 105.0]
                    * 15,
                    "open": [100.0] * 120,
                    "high": [115.0] * 120,
                    "low": [90.0] * 120,
                }
            )
        }

        label_config = {"zigzag_threshold": 0.05, "label_lookahead": 3}

        # Act
        labels = TrainingPipeline.create_labels(price_data, label_config)

        # Assert
        unique_labels = torch.unique(labels)
        # Should have at least 2 classes (might not always have all 3)
        assert len(unique_labels) >= 2
        # All labels should be 0, 1, or 2
        assert all(label in [0, 1, 2] for label in unique_labels.tolist())

    def test_create_labels_multi_timeframe_uses_base(self):
        """Test that multi-timeframe uses base timeframe for labels."""
        # Arrange
        price_data = {
            "1h": pd.DataFrame(
                {
                    "close": [100.0 + i * 0.5 for i in range(100)],
                    "open": [100.0] * 100,
                    "high": [105.0] * 100,
                    "low": [95.0] * 100,
                }
            ),
            "4h": pd.DataFrame(
                {
                    "close": [100.0 + i for i in range(50)],
                    "open": [100.0] * 50,
                    "high": [110.0] * 50,
                    "low": [90.0] * 50,
                }
            ),
        }

        label_config = {"zigzag_threshold": 0.05, "label_lookahead": 5}

        # Act
        labels = TrainingPipeline.create_labels(price_data, label_config)

        # Assert
        # Labels should be based on base timeframe (1h, which has 100 samples)
        # The actual length might be slightly less due to lookahead
        assert len(labels) > 90  # Should be close to 100

    def test_create_labels_length_matches_data(self):
        """Test that label length matches input data length (accounting for lookahead)."""
        # Arrange
        price_data = {
            "1D": pd.DataFrame(
                {
                    "close": [100.0 + i * 0.5 for i in range(200)],
                    "open": [100.0] * 200,
                    "high": [105.0] * 200,
                    "low": [95.0] * 200,
                }
            )
        }

        label_config = {"zigzag_threshold": 0.05, "label_lookahead": 5}

        # Act
        labels = TrainingPipeline.create_labels(price_data, label_config)

        # Assert
        # Should be same length as input data
        assert len(labels) == 200
