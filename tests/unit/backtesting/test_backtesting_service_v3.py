"""Unit tests for BacktestingService v3 support.

Tests the v3-specific functionality in BacktestingService:
- Service loads v3 metadata correctly
- Non-v3 models rejected with clear error
- Config reconstructed from metadata
- FeatureCacheV3 used with correct config
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ktrdr.backtesting.backtesting_service import BacktestingService
from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.models.model_metadata import ModelMetadataV3


@pytest.fixture
def mock_worker_registry():
    """Create a mock worker registry for BacktestingService."""
    return MagicMock()


@pytest.fixture
def sample_v3_metadata():
    """Create sample v3 metadata for testing."""
    return {
        "model_name": "test_model",
        "strategy_name": "test_strategy",
        "strategy_version": "3.0",
        "indicators": {
            "rsi_14": {"type": "rsi", "period": 14},
        },
        "fuzzy_sets": {
            "rsi_fast": {
                "indicator": "rsi_14",
                "oversold": [0, 25, 40],
                "overbought": [60, 75, 100],
            },
        },
        "nn_inputs": [
            {"fuzzy_set": "rsi_fast", "timeframes": ["5m"]},
        ],
        "resolved_features": ["5m_rsi_fast_oversold", "5m_rsi_fast_overbought"],
        "training_symbols": ["EURUSD"],
        "training_timeframes": ["5m"],
        "training_metrics": {"accuracy": 0.85},
    }


@pytest.fixture
def sample_v2_metadata():
    """Create sample v2 (non-v3) metadata for testing."""
    return {
        "model_name": "test_model",
        "strategy_name": "test_strategy",
        "strategy_version": "2.0",
        "indicators": [],
        "fuzzy_sets": {},
    }


@pytest.fixture
def model_dir_with_v3_metadata(sample_v3_metadata):
    """Create a temporary model directory with v3 metadata file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model"
        model_path.mkdir(parents=True)

        # Write metadata_v3.json
        metadata_path = model_path / "metadata_v3.json"
        with open(metadata_path, "w") as f:
            json.dump(sample_v3_metadata, f)

        yield model_path


@pytest.fixture
def model_dir_with_v2_metadata(sample_v2_metadata):
    """Create a temporary model directory with v2 metadata file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model"
        model_path.mkdir(parents=True)

        # Write metadata.json (v2 format)
        metadata_path = model_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(sample_v2_metadata, f)

        yield model_path


@pytest.fixture
def model_dir_no_metadata():
    """Create a temporary model directory without metadata file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model"
        model_path.mkdir(parents=True)
        yield model_path


class TestBacktestingServiceV3MetadataLoading:
    """Tests for v3 metadata loading."""

    def test_load_v3_metadata_from_file(
        self, mock_worker_registry, model_dir_with_v3_metadata
    ):
        """Service should load v3 metadata from metadata_v3.json."""
        metadata = BacktestingService.load_v3_metadata(model_dir_with_v3_metadata)

        assert isinstance(metadata, ModelMetadataV3)
        assert metadata.model_name == "test_model"
        assert metadata.strategy_version == "3.0"
        assert len(metadata.resolved_features) == 2

    def test_load_v3_metadata_missing_file_raises_error(
        self, mock_worker_registry, model_dir_no_metadata
    ):
        """Loading v3 metadata from missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            BacktestingService.load_v3_metadata(model_dir_no_metadata)

        assert "metadata_v3.json" in str(exc_info.value)


class TestBacktestingServiceV3Validation:
    """Tests for v3 model validation."""

    def test_is_v3_model_returns_true_for_v3(
        self, mock_worker_registry, model_dir_with_v3_metadata
    ):
        """is_v3_model should return True for models with v3 metadata."""
        result = BacktestingService.is_v3_model(model_dir_with_v3_metadata)
        assert result is True

    def test_is_v3_model_returns_false_for_missing_metadata(
        self, mock_worker_registry, model_dir_no_metadata
    ):
        """is_v3_model should return False when metadata_v3.json doesn't exist."""
        result = BacktestingService.is_v3_model(model_dir_no_metadata)
        assert result is False

    def test_validate_v3_model_passes_for_v3(
        self, mock_worker_registry, model_dir_with_v3_metadata
    ):
        """validate_v3_model should pass without error for v3 models."""
        # Should not raise
        BacktestingService.validate_v3_model(model_dir_with_v3_metadata)

    def test_validate_v3_model_raises_for_non_v3(
        self, mock_worker_registry, model_dir_no_metadata
    ):
        """validate_v3_model should raise ValueError for non-v3 models."""
        with pytest.raises(ValueError) as exc_info:
            BacktestingService.validate_v3_model(model_dir_no_metadata)

        assert "v3" in str(exc_info.value).lower() or "3.0" in str(exc_info.value)


class TestBacktestingServiceConfigReconstruction:
    """Tests for config reconstruction from metadata."""

    def test_reconstruct_config_returns_strategy_config_v3(
        self, mock_worker_registry, model_dir_with_v3_metadata, sample_v3_metadata
    ):
        """reconstruct_config should return StrategyConfigurationV3."""
        metadata = ModelMetadataV3.from_dict(sample_v3_metadata)
        config = BacktestingService.reconstruct_config_from_metadata(metadata)

        assert isinstance(config, StrategyConfigurationV3)

    def test_reconstruct_config_preserves_indicators(
        self, mock_worker_registry, sample_v3_metadata
    ):
        """Reconstructed config should have same indicators as metadata."""
        metadata = ModelMetadataV3.from_dict(sample_v3_metadata)
        config = BacktestingService.reconstruct_config_from_metadata(metadata)

        assert "rsi_14" in config.indicators

    def test_reconstruct_config_preserves_fuzzy_sets(
        self, mock_worker_registry, sample_v3_metadata
    ):
        """Reconstructed config should have same fuzzy sets as metadata."""
        metadata = ModelMetadataV3.from_dict(sample_v3_metadata)
        config = BacktestingService.reconstruct_config_from_metadata(metadata)

        assert "rsi_fast" in config.fuzzy_sets

    def test_reconstruct_config_preserves_nn_inputs(
        self, mock_worker_registry, sample_v3_metadata
    ):
        """Reconstructed config should have same nn_inputs as metadata."""
        metadata = ModelMetadataV3.from_dict(sample_v3_metadata)
        config = BacktestingService.reconstruct_config_from_metadata(metadata)

        assert len(config.nn_inputs) == 1
        assert config.nn_inputs[0].fuzzy_set == "rsi_fast"
