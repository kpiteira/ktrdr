"""Unit tests for BacktestingService v3 wiring.

Tests that v3 models are detected and use FeatureCache.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ktrdr.backtesting.backtesting_service import BacktestingService


class TestBacktestingServiceV3Detection:
    """Test v3 model detection in BacktestingService."""

    @pytest.fixture
    def v3_model_dir(self, tmp_path: Path) -> Path:
        """Create a mock v3 model directory with metadata_v3.json."""
        model_dir = tmp_path / "models" / "test_strategy" / "1h_v1"
        model_dir.mkdir(parents=True)

        # Create metadata_v3.json
        metadata = {
            "model_name": "test_model",
            "strategy_name": "test_strategy",
            "strategy_version": "3.0",
            "indicators": {"rsi_14": {"type": "RSI", "period": 14}},
            "fuzzy_sets": {"rsi_14": {"indicator": "rsi_14", "oversold": {}}},
            "nn_inputs": [{"fuzzy_set": "rsi_14", "timeframes": "all"}],
            "resolved_features": ["1h_rsi_14_oversold"],
            "training_symbols": ["EURUSD"],
            "training_timeframes": ["1h"],
            "training_metrics": {},
        }
        with open(model_dir / "metadata_v3.json", "w") as f:
            json.dump(metadata, f)

        return model_dir

    @pytest.fixture
    def v2_model_dir(self, tmp_path: Path) -> Path:
        """Create a mock v2 model directory (no metadata_v3.json)."""
        model_dir = tmp_path / "models" / "test_strategy" / "EURUSD_1h_v1"
        model_dir.mkdir(parents=True)

        # V2 models have metadata.json, not metadata_v3.json
        metadata = {
            "model_name": "test_model",
            "strategy_name": "test_strategy",
            "symbol": "EURUSD",
            "timeframe": "1h",
        }
        with open(model_dir / "metadata.json", "w") as f:
            json.dump(metadata, f)

        return model_dir

    def test_is_v3_model_detects_v3(self, v3_model_dir: Path):
        """V3 model detected by presence of metadata_v3.json."""
        assert BacktestingService.is_v3_model(v3_model_dir) is True

    def test_is_v3_model_rejects_v2(self, v2_model_dir: Path):
        """V2 model (no metadata_v3.json) not detected as v3."""
        assert BacktestingService.is_v3_model(v2_model_dir) is False

    def test_load_v3_metadata_loads_correctly(self, v3_model_dir: Path):
        """load_v3_metadata loads and parses metadata_v3.json."""
        metadata = BacktestingService.load_v3_metadata(v3_model_dir)

        assert metadata.strategy_version == "3.0"
        assert metadata.strategy_name == "test_strategy"
        assert len(metadata.resolved_features) == 1
        assert "1h_rsi_14_oversold" in metadata.resolved_features

    def test_load_v3_metadata_raises_for_v2(self, v2_model_dir: Path):
        """load_v3_metadata raises FileNotFoundError for v2 models."""
        with pytest.raises(FileNotFoundError) as exc_info:
            BacktestingService.load_v3_metadata(v2_model_dir)

        assert "metadata_v3.json" in str(exc_info.value)

    def test_validate_v3_model_passes_for_valid(self, v3_model_dir: Path):
        """validate_v3_model doesn't raise for valid v3 model."""
        BacktestingService.validate_v3_model(v3_model_dir)  # Should not raise

    def test_validate_v3_model_raises_for_v2(self, v2_model_dir: Path):
        """validate_v3_model raises ValueError for v2 models."""
        with pytest.raises(ValueError) as exc_info:
            BacktestingService.validate_v3_model(v2_model_dir)

        assert "not a v3 model" in str(exc_info.value)


class TestBacktestingServiceV3ConfigReconstruction:
    """Test v3 config reconstruction from model metadata."""

    @pytest.fixture
    def v3_metadata(self, tmp_path: Path):
        """Create and load v3 metadata."""
        model_dir = tmp_path / "models" / "test"
        model_dir.mkdir(parents=True)

        metadata = {
            "model_name": "test_model",
            "strategy_name": "test_strategy",
            "strategy_version": "3.0",
            "indicators": {"rsi_14": {"type": "RSI", "period": 14, "source": "close"}},
            "fuzzy_sets": {
                "rsi_14": {
                    "indicator": "rsi_14",
                    "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                    "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
                }
            },
            "nn_inputs": [{"fuzzy_set": "rsi_14", "timeframes": "all"}],
            "resolved_features": ["1h_rsi_14_oversold", "1h_rsi_14_overbought"],
            "training_symbols": ["EURUSD"],
            "training_timeframes": ["1h"],
            "training_metrics": {},
        }
        with open(model_dir / "metadata_v3.json", "w") as f:
            json.dump(metadata, f)

        return BacktestingService.load_v3_metadata(model_dir)

    def test_reconstruct_config_creates_valid_v3_config(self, v3_metadata):
        """reconstruct_config_from_metadata creates valid StrategyConfigurationV3."""
        config = BacktestingService.reconstruct_config_from_metadata(v3_metadata)

        # Check basic structure
        assert config.name == "test_strategy"
        assert config.version == "3.0"

        # Check indicators preserved
        assert "rsi_14" in config.indicators
        assert config.indicators["rsi_14"].type == "RSI"
        assert config.indicators["rsi_14"].period == 14

        # Check fuzzy sets preserved
        assert "rsi_14" in config.fuzzy_sets
        assert config.fuzzy_sets["rsi_14"].indicator == "rsi_14"

        # Check nn_inputs preserved
        assert len(config.nn_inputs) == 1
        assert config.nn_inputs[0].fuzzy_set == "rsi_14"


class TestDecisionOrchestratorV3Wiring:
    """Test DecisionOrchestrator uses FeatureCache for v3 models."""

    def test_check_v3_model_detects_v3(self, tmp_path: Path):
        """_check_v3_model returns True for v3 model directories."""
        from ktrdr.decision.orchestrator import DecisionOrchestrator

        # Create v3 model dir
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        metadata = {
            "model_name": "test",
            "strategy_name": "test",
            "strategy_version": "3.0",
            "indicators": {},
            "fuzzy_sets": {},
            "nn_inputs": [],
            "resolved_features": [],
            "training_symbols": [],
            "training_timeframes": [],
            "training_metrics": {},
        }
        with open(model_dir / "metadata_v3.json", "w") as f:
            json.dump(metadata, f)

        # Create mock orchestrator (won't fully initialize)
        orchestrator = MagicMock(spec=DecisionOrchestrator)
        orchestrator._check_v3_model = DecisionOrchestrator._check_v3_model.__get__(
            orchestrator, DecisionOrchestrator
        )

        assert orchestrator._check_v3_model(str(model_dir)) is True

    def test_check_v3_model_rejects_v2(self, tmp_path: Path):
        """_check_v3_model returns False for v2 model directories."""
        from ktrdr.decision.orchestrator import DecisionOrchestrator

        # Create v2 model dir (no metadata_v3.json)
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        with open(model_dir / "metadata.json", "w") as f:
            json.dump({"strategy_name": "test"}, f)

        # Create mock orchestrator
        orchestrator = MagicMock(spec=DecisionOrchestrator)
        orchestrator._check_v3_model = DecisionOrchestrator._check_v3_model.__get__(
            orchestrator, DecisionOrchestrator
        )

        assert orchestrator._check_v3_model(str(model_dir)) is False

    def test_decision_orchestrator_has_v3_methods(self):
        """DecisionOrchestrator should have v3 model methods."""
        from ktrdr.decision.orchestrator import DecisionOrchestrator

        # We can't easily instantiate without a real strategy config,
        # but we can check that the methods exist
        assert hasattr(DecisionOrchestrator, "_check_v3_model")
        assert hasattr(DecisionOrchestrator, "_create_feature_cache")
