"""Unit tests for LocalTrainingOrchestrator v3 wiring.

Tests that v3 format strategies use TrainingPipelineV3 and produce
metadata_v3.json with resolved_features.
"""

from __future__ import annotations

import pytest

from ktrdr.api.services.training.local_orchestrator import LocalTrainingOrchestrator


class TestLocalOrchestratorV3Detection:
    """Test v3 format detection in LocalTrainingOrchestrator."""

    def test_is_v3_format_detects_v3_dict_indicators(self):
        """V3 format has dict indicators and nn_inputs."""
        v3_config = {
            "name": "test_v3",
            "version": "3.0",
            "indicators": {"rsi_14": {"type": "RSI", "period": 14, "source": "close"}},
            "fuzzy_sets": {"rsi_14": {"indicator": "rsi_14", "oversold": {}}},
            "nn_inputs": [{"fuzzy_set": "rsi_14", "timeframes": "all"}],
            "model": {},
            "training": {},
            "decisions": {},
        }
        assert LocalTrainingOrchestrator._is_v3_format(v3_config) is True

    def test_is_v3_format_rejects_v2_list_indicators(self):
        """V2 format has list indicators (no nn_inputs)."""
        v2_config = {
            "name": "test_v2",
            "version": "2.0",
            "indicators": [{"name": "RSI", "period": 14, "feature_id": "rsi_14"}],
            "fuzzy_sets": {"rsi_14": {"oversold": {}}},
            "model": {},
            "training": {"labels": {}},
        }
        assert LocalTrainingOrchestrator._is_v3_format(v2_config) is False

    def test_is_v3_format_rejects_dict_without_nn_inputs(self):
        """Dict indicators without nn_inputs is not valid v3."""
        invalid_config = {
            "indicators": {"rsi_14": {"type": "RSI"}},
            "fuzzy_sets": {},
            # Missing nn_inputs
        }
        assert LocalTrainingOrchestrator._is_v3_format(invalid_config) is False


class TestLocalOrchestratorV3Training:
    """Test v3 training execution path."""

    @pytest.fixture
    def v3_strategy_path(self, tmp_path):
        """Create a v3 strategy file."""
        strategy_path = tmp_path / "test_strategy.yaml"
        strategy_path.write_text(
            """
name: test_v3
version: '3.0'
scope: universal
training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100
indicators:
  rsi_14:
    type: RSI
    period: 14
    source: close
fuzzy_sets:
  rsi_14:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 40]
nn_inputs:
  - fuzzy_set: rsi_14
    timeframes: all
model:
  type: mlp
  architecture:
    hidden_layers: [8, 4]
decisions:
  output_format: classification
training:
  method: supervised
  labels:
    source: zigzag
    zigzag_threshold: 0.02
    label_lookahead: 10
  data_split:
    train: 0.7
    validation: 0.15
    test: 0.15
"""
        )
        return strategy_path

    @pytest.fixture
    def v2_strategy_path(self, tmp_path):
        """Create a v2 strategy file."""
        strategy_path = tmp_path / "test_v2.yaml"
        strategy_path.write_text(
            """
name: test_v2
version: '2.0'
indicators:
  - name: RSI
    period: 14
    feature_id: rsi_14
fuzzy_sets:
  rsi_14:
    oversold:
      type: triangular
      parameters: [0, 20, 40]
model:
  type: mlp
  hidden_layers: [8]
  training:
    epochs: 1
    batch_size: 32
    learning_rate: 0.001
training:
  labels:
    source: zigzag
    zigzag_threshold: 0.02
    label_lookahead: 10
  data_split:
    test_size: 0.1
    validation_size: 0.2
"""
        )
        return strategy_path

    def test_v3_strategy_detected_from_file(self, v3_strategy_path):
        """V3 strategy file should be detected as v3 format."""
        import yaml

        with open(v3_strategy_path) as f:
            config = yaml.safe_load(f)

        assert LocalTrainingOrchestrator._is_v3_format(config) is True

    def test_v2_strategy_detected_from_file(self, v2_strategy_path):
        """V2 strategy file should be detected as v2 format."""
        import yaml

        with open(v2_strategy_path) as f:
            config = yaml.safe_load(f)

        assert LocalTrainingOrchestrator._is_v3_format(config) is False

    def test_execute_v3_training_method_exists(self):
        """_execute_v3_training method should exist for v3 path."""
        assert hasattr(
            LocalTrainingOrchestrator, "_execute_v3_training"
        ), "_execute_v3_training method must be implemented for v3 training path"


class TestLocalOrchestratorV3Metadata:
    """Test that v3 training saves ModelMetadataV3."""

    def test_save_v3_metadata_creates_file(self, tmp_path):
        """_save_v3_metadata creates metadata_v3.json in model directory."""
        model_path = tmp_path / "model_dir"
        model_path.mkdir()

        config = {
            "name": "test_model",
            "version": "3.0",
            "indicators": {"rsi_14": {"type": "RSI", "period": 14}},
            "fuzzy_sets": {"rsi_14": {"indicator": "rsi_14", "oversold": {}}},
            "nn_inputs": [{"fuzzy_set": "rsi_14", "timeframes": "all"}],
        }
        resolved_features = ["1h_rsi_14_oversold"]
        training_metrics = {"accuracy": 0.85}
        training_symbols = ["EURUSD"]
        training_timeframes = ["1h"]

        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=model_path,
            config=config,
            resolved_features=resolved_features,
            training_metrics=training_metrics,
            training_symbols=training_symbols,
            training_timeframes=training_timeframes,
        )

        metadata_file = model_path / "metadata_v3.json"
        assert metadata_file.exists(), "metadata_v3.json should be created"

        import json

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["strategy_version"] == "3.0"
        assert metadata["resolved_features"] == resolved_features
        assert metadata["training_symbols"] == training_symbols
        assert metadata["training_timeframes"] == training_timeframes
        assert "indicators" in metadata
        assert "fuzzy_sets" in metadata
        assert "nn_inputs" in metadata

    def test_save_v3_metadata_includes_all_config_sections(self, tmp_path):
        """Metadata includes indicators, fuzzy_sets, and nn_inputs for reproducibility."""
        model_path = tmp_path / "model_dir"
        model_path.mkdir()

        config = {
            "name": "complex_model",
            "version": "3.0",
            "indicators": {
                "rsi_14": {"type": "RSI", "period": 14, "source": "close"},
                "macd_12_26_9": {"type": "MACD", "fast": 12, "slow": 26, "signal": 9},
            },
            "fuzzy_sets": {
                "rsi_14": {
                    "indicator": "rsi_14",
                    "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                    "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
                },
            },
            "nn_inputs": [
                {"fuzzy_set": "rsi_14", "timeframes": "all"},
            ],
        }
        resolved_features = [
            "1h_rsi_14_oversold",
            "1h_rsi_14_overbought",
        ]

        LocalTrainingOrchestrator._save_v3_metadata(
            model_path=model_path,
            config=config,
            resolved_features=resolved_features,
            training_metrics={},
            training_symbols=["EURUSD"],
            training_timeframes=["1h"],
        )

        import json

        with open(model_path / "metadata_v3.json") as f:
            metadata = json.load(f)

        # Verify all sections preserved
        assert len(metadata["indicators"]) == 2
        assert "rsi_14" in metadata["indicators"]
        assert "macd_12_26_9" in metadata["indicators"]

        assert len(metadata["fuzzy_sets"]) == 1
        assert "rsi_14" in metadata["fuzzy_sets"]

        assert len(metadata["nn_inputs"]) == 1
        assert metadata["nn_inputs"][0]["fuzzy_set"] == "rsi_14"
