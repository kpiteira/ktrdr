"""Unit tests for ModelBundle.

Tests ModelBundle.load() and associated utility functions (is_v3, load_v3_metadata,
reconstruct_config_from_metadata). These utilities moved from BacktestingService
to model_bundle.py as part of the backtesting pipeline refactor (M1).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ktrdr.models.model_metadata import ModelMetadata

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def v3_metadata_dict() -> dict:
    """Minimal valid v3 metadata for tests."""
    return {
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
        "training_metrics": {"accuracy": 0.65},
    }


@pytest.fixture
def v3_model_dir(tmp_path: Path, v3_metadata_dict: dict) -> Path:
    """Create a v3 model directory with all required files on disk.

    Contains: metadata_v3.json and features.json.
    Does NOT contain model.pt (torch file) — torch tests use a separate fixture.
    """
    model_dir = tmp_path / "models" / "test_strategy" / "1h_v1"
    model_dir.mkdir(parents=True)

    # metadata_v3.json
    with open(model_dir / "metadata_v3.json", "w") as f:
        json.dump(v3_metadata_dict, f)

    # features.json
    features = {
        "feature_count": 2,
        "feature_names": ["1h_rsi_14_oversold", "1h_rsi_14_overbought"],
    }
    with open(model_dir / "features.json", "w") as f:
        json.dump(features, f)

    return model_dir


@pytest.fixture
def v2_model_dir(tmp_path: Path) -> Path:
    """Create a v2 model directory (no metadata_v3.json)."""
    model_dir = tmp_path / "models" / "old_strategy" / "EURUSD_1h_v1"
    model_dir.mkdir(parents=True)

    with open(model_dir / "metadata.json", "w") as f:
        json.dump({"strategy_name": "old", "symbol": "EURUSD"}, f)

    return model_dir


# ---------------------------------------------------------------------------
# Tests: is_v3_model
# ---------------------------------------------------------------------------


class TestIsV3Model:
    """Test is_v3_model() detection."""

    def test_detects_v3(self, v3_model_dir: Path):
        from ktrdr.backtesting.model_bundle import is_v3_model

        assert is_v3_model(v3_model_dir) is True

    def test_rejects_v2(self, v2_model_dir: Path):
        from ktrdr.backtesting.model_bundle import is_v3_model

        assert is_v3_model(v2_model_dir) is False

    def test_rejects_nonexistent_dir(self, tmp_path: Path):
        from ktrdr.backtesting.model_bundle import is_v3_model

        assert is_v3_model(tmp_path / "nonexistent") is False


# ---------------------------------------------------------------------------
# Tests: load_v3_metadata
# ---------------------------------------------------------------------------


class TestLoadV3Metadata:
    """Test load_v3_metadata() function."""

    def test_loads_metadata(self, v3_model_dir: Path):
        from ktrdr.backtesting.model_bundle import load_v3_metadata

        metadata = load_v3_metadata(v3_model_dir)
        assert metadata.strategy_version == "3.0"
        assert metadata.strategy_name == "test_strategy"
        assert metadata.resolved_features == [
            "1h_rsi_14_oversold",
            "1h_rsi_14_overbought",
        ]

    def test_raises_for_missing_metadata(self, v2_model_dir: Path):
        from ktrdr.backtesting.model_bundle import load_v3_metadata

        with pytest.raises(FileNotFoundError, match="metadata_v3.json"):
            load_v3_metadata(v2_model_dir)


# ---------------------------------------------------------------------------
# Tests: reconstruct_config_from_metadata
# ---------------------------------------------------------------------------


class TestReconstructConfig:
    """Test reconstruct_config_from_metadata() function."""

    def test_creates_valid_v3_config(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert config.name == "test_strategy"
        assert config.version == "3.0"

    def test_preserves_indicators(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert "rsi_14" in config.indicators
        assert config.indicators["rsi_14"].type == "RSI"
        assert config.indicators["rsi_14"].period == 14

    def test_preserves_fuzzy_sets(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert "rsi_14" in config.fuzzy_sets
        assert config.fuzzy_sets["rsi_14"].indicator == "rsi_14"

    def test_preserves_nn_inputs(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert len(config.nn_inputs) == 1
        assert config.nn_inputs[0].fuzzy_set == "rsi_14"

    def test_single_symbol_mode(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert config.training_data.symbols.symbol == "EURUSD"

    def test_multi_timeframe_mode(self, v3_metadata_dict: dict):
        from ktrdr.backtesting.model_bundle import reconstruct_config_from_metadata

        v3_metadata_dict["training_timeframes"] = ["1h", "5m"]
        metadata = ModelMetadata.from_dict(v3_metadata_dict)
        config = reconstruct_config_from_metadata(metadata)

        assert config.training_data.timeframes.timeframes == ["1h", "5m"]
        assert config.training_data.timeframes.base_timeframe == "1h"


# ---------------------------------------------------------------------------
# Tests: ModelBundle.load() — requires torch mock
# ---------------------------------------------------------------------------


class TestModelBundleLoad:
    """Test ModelBundle.load() with mocked torch.

    Since torch is lazily imported inside load(), we inject a mock torch module
    via sys.modules to intercept the import.
    """

    @pytest.fixture(autouse=True)
    def _mock_torch(self):
        """Inject mock torch into sys.modules for all tests in this class."""
        self.mock_torch = MagicMock()
        self.mock_torch.load.return_value = {"0.weight": MagicMock(shape=(10, 2))}
        # Save and restore original torch entry
        original = sys.modules.get("torch")
        sys.modules["torch"] = self.mock_torch
        yield
        if original is not None:
            sys.modules["torch"] = original
        else:
            sys.modules.pop("torch", None)

    def test_load_raises_for_missing_metadata_v3(self, v2_model_dir: Path):
        """ModelBundle.load requires metadata_v3.json."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        with pytest.raises(FileNotFoundError, match="metadata_v3.json"):
            ModelBundle.load(str(v2_model_dir))

    def test_load_raises_for_nonexistent_path(self, tmp_path: Path):
        """ModelBundle.load raises for path that doesn't exist."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        with pytest.raises(FileNotFoundError):
            ModelBundle.load(str(tmp_path / "nonexistent"))

    def test_load_returns_frozen_dataclass(self, v3_model_dir: Path):
        """ModelBundle is immutable after creation."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        mock_model = MagicMock()

        with patch(
            "ktrdr.backtesting.model_bundle._build_model", return_value=mock_model
        ):
            bundle = ModelBundle.load(str(v3_model_dir))

        # Verify frozen
        with pytest.raises(AttributeError):
            bundle.model = MagicMock()  # type: ignore[misc]

    def test_load_calls_torch_with_map_location_cpu(self, v3_model_dir: Path):
        """ModelBundle.load must use map_location='cpu' for MPS/CUDA portability."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        mock_model = MagicMock()

        with patch(
            "ktrdr.backtesting.model_bundle._build_model", return_value=mock_model
        ):
            ModelBundle.load(str(v3_model_dir))

        self.mock_torch.load.assert_called_once()
        call_kwargs = self.mock_torch.load.call_args
        assert call_kwargs.kwargs.get("map_location") == "cpu"
        assert call_kwargs.kwargs.get("weights_only") is True

    def test_load_sets_model_eval_mode(self, v3_model_dir: Path):
        """Loaded model must be in eval mode."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        mock_model = MagicMock()

        with patch(
            "ktrdr.backtesting.model_bundle._build_model", return_value=mock_model
        ):
            ModelBundle.load(str(v3_model_dir))

        mock_model.eval.assert_called_once()

    def test_load_populates_all_fields(self, v3_model_dir: Path):
        """ModelBundle.load returns bundle with all required fields."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        mock_model = MagicMock()

        with patch(
            "ktrdr.backtesting.model_bundle._build_model", return_value=mock_model
        ):
            bundle = ModelBundle.load(str(v3_model_dir))

        assert bundle.model is mock_model
        assert bundle.metadata.strategy_name == "test_strategy"
        assert bundle.feature_names == ["1h_rsi_14_oversold", "1h_rsi_14_overbought"]
        assert bundle.strategy_config.name == "test_strategy"

    def test_load_raises_for_missing_model_pt(self, v3_model_dir: Path):
        """ModelBundle.load raises when torch.load fails."""
        from ktrdr.backtesting.model_bundle import ModelBundle

        self.mock_torch.load.side_effect = FileNotFoundError("model.pt not found")

        with patch("ktrdr.backtesting.model_bundle._build_model"):
            with pytest.raises(FileNotFoundError):
                ModelBundle.load(str(v3_model_dir))
