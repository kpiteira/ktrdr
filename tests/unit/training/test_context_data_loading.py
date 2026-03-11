"""Tests for training pipeline context data loading (Task 6.6)."""

import numpy as np
import pandas as pd
import pytest

from ktrdr.models.model_metadata import ModelMetadata


def _make_ohlcv(periods: int = 50) -> pd.DataFrame:
    """Create minimal OHLCV data for indicator computation."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=periods, freq="h")
    close = 100 + np.cumsum(np.random.randn(periods) * 0.5)
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.random.randint(1000, 5000, periods),
        },
        index=dates,
    )


def _make_context_df(periods: int = 50) -> pd.DataFrame:
    """Create context data (single 'close' column, like FRED yield data)."""
    np.random.seed(99)
    dates = pd.date_range("2024-01-01", periods=periods, freq="h")
    values = 4.0 + np.cumsum(np.random.randn(periods) * 0.02)
    return pd.DataFrame({"close": values}, index=dates)


class TestComputeForTimeframeWithContext:
    """Test IndicatorEngine.compute_for_timeframe passes context_data."""

    def test_compute_for_timeframe_without_context(self):
        """compute_for_timeframe works unchanged without context_data."""
        from ktrdr.indicators.indicator_engine import IndicatorEngine

        engine = IndicatorEngine({"rsi_14": {"type": "rsi", "period": 14}})
        data = _make_ohlcv()
        result = engine.compute_for_timeframe(data, "1h", {"rsi_14"})

        assert "1h_rsi_14" in result.columns

    def test_compute_for_timeframe_with_context(self):
        """compute_for_timeframe routes data_source indicators to context."""
        from ktrdr.indicators.indicator_engine import IndicatorEngine

        engine = IndicatorEngine(
            {
                "rsi_14": {"type": "rsi", "period": 14},
                "yield_rsi": {
                    "type": "rsi",
                    "period": 14,
                    "data_source": "yield_spread",
                },
            }
        )
        primary = _make_ohlcv()
        context = _make_context_df()

        result = engine.compute_for_timeframe(
            primary,
            "1h",
            {"rsi_14", "yield_rsi"},
            context_data={"yield_spread": context},
        )

        assert "1h_rsi_14" in result.columns
        assert "1h_yield_rsi" in result.columns


try:
    import torch  # noqa: F401

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@pytest.mark.skipif(not HAS_TORCH, reason="torch not available")
class TestPrepareFeatureWithContext:
    """Test TrainingPipelineV3.prepare_features with context_data."""

    def _make_v3_config(self, with_context: bool = False):
        """Build a minimal v3 strategy config."""
        from ktrdr.config.models import StrategyConfigurationV3

        indicators = {"rsi_14": {"type": "rsi", "period": 14}}

        if with_context:
            indicators["yield_rsi"] = {
                "type": "rsi",
                "period": 14,
                "data_source": "yield_spread",
            }

        data = {
            "name": "test_strategy",
            "version": "3.0",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "EURUSD"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
                "history_required": 200,
            },
            "indicators": indicators,
            "fuzzy_sets": {
                "rsi_momentum": {
                    "indicator": "rsi_14",
                    "oversold": [0, 25, 40],
                    "overbought": [60, 75, 100],
                },
            },
            "nn_inputs": [{"fuzzy_set": "rsi_momentum", "timeframes": "all"}],
            "model": {"type": "mlp", "hidden_layers": [32, 16]},
            "decisions": {"mode": "classification", "output_format": "classification"},
            "training": {"epochs": 10, "batch_size": 32},
        }

        if with_context:
            data["fuzzy_sets"]["yield_signal"] = {
                "indicator": "yield_rsi",
                "widening": [60, 75, 100],
                "narrowing": [0, 25, 40],
            }
            data["nn_inputs"].append({"fuzzy_set": "yield_signal", "timeframes": "all"})

        return StrategyConfigurationV3(**data)

    def test_prepare_features_without_context(self):
        """prepare_features works unchanged without context_data."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        config = self._make_v3_config(with_context=False)
        pipeline = TrainingPipelineV3(config)

        data = {"EURUSD": {"1h": _make_ohlcv(200)}}
        result = pipeline.prepare_features(data)

        assert result.shape[0] > 0
        assert result.shape[1] > 0

    def test_prepare_features_with_context(self):
        """prepare_features passes context_data to IndicatorEngine."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        config = self._make_v3_config(with_context=True)
        pipeline = TrainingPipelineV3(config)

        data = {"EURUSD": {"1h": _make_ohlcv(200)}}
        context = {"yield_spread": _make_context_df(200)}

        result = pipeline.prepare_features(data, context_data=context)

        assert result.shape[0] > 0
        # Should have features from both rsi_momentum and yield_signal fuzzy sets
        assert (
            result.shape[1] > 2
        )  # At least oversold + overbought + widening + narrowing

    def test_prepare_features_missing_context_raises(self):
        """prepare_features raises when data_source references missing context."""
        from ktrdr.training.training_pipeline import TrainingPipelineV3

        config = self._make_v3_config(with_context=True)
        pipeline = TrainingPipelineV3(config)

        data = {"EURUSD": {"1h": _make_ohlcv(200)}}

        with pytest.raises(KeyError, match="yield_spread"):
            pipeline.prepare_features(data)  # No context_data provided


class TestModelMetadataContextFields:
    """Test ModelMetadata context_data fields."""

    def test_metadata_without_context(self):
        """Existing metadata works unchanged without context fields."""
        meta = ModelMetadata(
            model_name="test_model",
            strategy_name="test_strategy",
        )
        d = meta.to_dict()
        assert "context_data_config" in d
        assert d["context_data_config"] is None

    def test_metadata_with_context_config(self):
        """ModelMetadata stores context_data_config."""
        context_config = [
            {
                "provider": "fred",
                "series": ["DGS2", "IRLTLT01DEM156N"],
                "frequency": "daily",
            }
        ]
        meta = ModelMetadata(
            model_name="test_model",
            strategy_name="test_strategy",
            context_data_config=context_config,
            context_source_ids=["yield_spread_DGS2_IRLTLT01DEM156N"],
        )
        d = meta.to_dict()
        assert d["context_data_config"] == context_config
        assert d["context_source_ids"] == ["yield_spread_DGS2_IRLTLT01DEM156N"]

    def test_metadata_roundtrip(self):
        """ModelMetadata context fields survive to_dict/from_dict roundtrip."""
        context_config = [{"provider": "fred", "series": "DGS2"}]
        source_ids = ["fred_DGS2"]

        original = ModelMetadata(
            model_name="test_model",
            strategy_name="test_strategy",
            context_data_config=context_config,
            context_source_ids=source_ids,
        )

        restored = ModelMetadata.from_dict(original.to_dict())
        assert restored.context_data_config == context_config
        assert restored.context_source_ids == source_ids

    def test_metadata_from_dict_without_context(self):
        """from_dict handles missing context fields gracefully (old models)."""
        data = {
            "model_name": "old_model",
            "strategy_name": "old_strategy",
        }
        meta = ModelMetadata.from_dict(data)
        assert meta.context_data_config is None
        assert meta.context_source_ids == []
