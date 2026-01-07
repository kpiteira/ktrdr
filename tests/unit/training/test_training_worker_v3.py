"""
Tests for training worker v3 support.

Tests that v3 strategy configurations are properly detected and
ModelMetadataV3 is saved with resolved_features after training.
"""

import json

import pytest

from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator


class TestV3ConfigDetection:
    """Test v3 config format detection."""

    def test_is_v3_format_with_nn_inputs(self):
        """Config with nn_inputs and dict indicators is v3 format."""
        config = {
            "name": "test_strategy",
            "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
            "fuzzy_sets": {"rsi_fast": {"indicator": "rsi_14"}},
            "nn_inputs": [{"fuzzy_set": "rsi_fast", "timeframes": "all"}],
            "training_data": {},
        }

        assert LocalTrainingOrchestrator._is_v3_format(config) is True

    def test_is_v3_format_without_nn_inputs(self):
        """Config without nn_inputs is not v3 format."""
        config = {
            "name": "test_strategy",
            "indicators": {"rsi_14": {"type": "rsi", "period": 14}},
            "fuzzy_sets": {"rsi_fast": {"indicator": "rsi_14"}},
            # No nn_inputs
            "training_data": {},
        }

        assert LocalTrainingOrchestrator._is_v3_format(config) is False

    def test_is_v3_format_with_list_indicators(self):
        """Config with list indicators is not v3 format (v1/v2)."""
        config = {
            "name": "test_strategy",
            "indicators": [{"name": "rsi_14", "type": "rsi", "period": 14}],
            "fuzzy_sets": {},
            "nn_inputs": [{"fuzzy_set": "rsi_fast"}],  # Has nn_inputs but wrong format
        }

        assert LocalTrainingOrchestrator._is_v3_format(config) is False


class TestV3MetadataSaving:
    """Test ModelMetadataV3 is saved correctly for v3 configs."""

    @pytest.fixture
    def v3_config_dict(self):
        """Sample v3 configuration dictionary."""
        return {
            "name": "test_v3_strategy",
            "version": "3.0",
            "indicators": {
                "rsi_14": {"type": "rsi", "period": 14},
            },
            "fuzzy_sets": {
                "rsi_fast": {
                    "indicator": "rsi_14",
                    "oversold": [0, 30, 40],
                    "neutral": [30, 50, 70],
                    "overbought": [60, 70, 100],
                }
            },
            "nn_inputs": [{"fuzzy_set": "rsi_fast", "timeframes": ["5m", "1h"]}],
            "training_data": {
                "symbols": {"list": ["AAPL"]},
                "timeframes": {"timeframes": ["5m", "1h"]},
            },
            "model": {
                "hidden_sizes": [64, 32],
            },
            "training": {
                "epochs": 10,
                "batch_size": 32,
            },
        }

    @pytest.fixture
    def mock_model_dir(self, tmp_path):
        """Create a temporary model directory."""
        model_dir = tmp_path / "models" / "test_strategy" / "5m_v1"
        model_dir.mkdir(parents=True)
        return model_dir

    def test_save_v3_metadata_creates_file(self, v3_config_dict, mock_model_dir):
        """_save_v3_metadata creates metadata_v3.json in model directory."""
        # Arrange
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "5m_rsi_fast_overbought",
            "1h_rsi_fast_oversold",
            "1h_rsi_fast_neutral",
            "1h_rsi_fast_overbought",
        ]
        training_metrics = {"loss": 0.05, "accuracy": 0.85}

        # Act
        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=mock_model_dir,
            config=v3_config_dict,
            resolved_features=resolved_features,
            training_metrics=training_metrics,
            training_symbols=["AAPL"],
            training_timeframes=["5m", "1h"],
        )

        # Assert
        metadata_file = mock_model_dir / "metadata_v3.json"
        assert metadata_file.exists()

    def test_save_v3_metadata_contains_resolved_features(
        self, v3_config_dict, mock_model_dir
    ):
        """Saved metadata contains the resolved_features list."""
        resolved_features = [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_neutral",
            "1h_rsi_fast_oversold",
        ]

        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=mock_model_dir,
            config=v3_config_dict,
            resolved_features=resolved_features,
            training_metrics={},
            training_symbols=["AAPL"],
            training_timeframes=["5m"],
        )

        metadata_file = mock_model_dir / "metadata_v3.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["resolved_features"] == resolved_features

    def test_save_v3_metadata_contains_strategy_info(
        self, v3_config_dict, mock_model_dir
    ):
        """Saved metadata contains strategy name and version."""
        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=mock_model_dir,
            config=v3_config_dict,
            resolved_features=[],
            training_metrics={},
            training_symbols=["AAPL"],
            training_timeframes=["5m"],
        )

        metadata_file = mock_model_dir / "metadata_v3.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["strategy_name"] == "test_v3_strategy"
        assert metadata["strategy_version"] == "3.0"

    def test_save_v3_metadata_contains_config_sections(
        self, v3_config_dict, mock_model_dir
    ):
        """Saved metadata contains indicators, fuzzy_sets, and nn_inputs."""
        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=mock_model_dir,
            config=v3_config_dict,
            resolved_features=[],
            training_metrics={},
            training_symbols=["AAPL"],
            training_timeframes=["5m"],
        )

        metadata_file = mock_model_dir / "metadata_v3.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert "indicators" in metadata
        assert "rsi_14" in metadata["indicators"]
        assert "fuzzy_sets" in metadata
        assert "rsi_fast" in metadata["fuzzy_sets"]
        assert "nn_inputs" in metadata
        assert len(metadata["nn_inputs"]) == 1

    def test_save_v3_metadata_contains_training_context(
        self, v3_config_dict, mock_model_dir
    ):
        """Saved metadata contains training symbols, timeframes, and metrics."""
        training_metrics = {"loss": 0.05, "accuracy": 0.85}

        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=mock_model_dir,
            config=v3_config_dict,
            resolved_features=[],
            training_metrics=training_metrics,
            training_symbols=["AAPL", "GOOGL"],
            training_timeframes=["5m", "1h"],
        )

        metadata_file = mock_model_dir / "metadata_v3.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["training_symbols"] == ["AAPL", "GOOGL"]
        assert metadata["training_timeframes"] == ["5m", "1h"]
        assert metadata["training_metrics"]["loss"] == 0.05
        assert metadata["training_metrics"]["accuracy"] == 0.85


class TestV3TrainingIntegration:
    """Integration tests for v3 training flow."""

    def test_v3_config_resolves_features(self):
        """V3 config gets features resolved using FeatureResolver."""
        from ktrdr.config.feature_resolver import FeatureResolver
        from ktrdr.config.models import (
            FuzzySetDefinition,
            NNInputSpec,
            StrategyConfigurationV3,
            SymbolConfiguration,
            SymbolMode,
            TimeframeConfiguration,
            TimeframeMode,
            TrainingDataConfiguration,
        )

        # Create minimal v3 config
        config = StrategyConfigurationV3(
            name="test",
            indicators={"rsi_14": {"type": "rsi", "period": 14}},
            fuzzy_sets={
                "rsi_fast": FuzzySetDefinition(
                    indicator="rsi_14",
                    oversold=[0, 30, 40],
                    overbought=[60, 70, 100],
                )
            },
            nn_inputs=[NNInputSpec(fuzzy_set="rsi_fast", timeframes=["5m"])],
            training_data=TrainingDataConfiguration(
                symbols=SymbolConfiguration(
                    mode=SymbolMode.MULTI_SYMBOL,
                    symbols=["AAPL"],
                ),
                timeframes=TimeframeConfiguration(
                    mode=TimeframeMode.MULTI_TIMEFRAME,
                    timeframes=["5m", "1h"],  # Need at least 2 for multi-timeframe
                ),
            ),
            model={"hidden_sizes": [64, 32]},
            decisions={"threshold": 0.5},
            training={"epochs": 10},
        )

        resolver = FeatureResolver()
        resolved = resolver.resolve(config)
        feature_ids = [f.feature_id for f in resolved]

        assert "5m_rsi_fast_oversold" in feature_ids
        assert "5m_rsi_fast_overbought" in feature_ids
        assert len(resolved) == 2  # oversold and overbought
