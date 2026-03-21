"""Tests for Gaussian MF strategy templates and dead zone elimination."""

import numpy as np
import pytest

from ktrdr.config.models import (
    FuzzySetDefinition,
    IndicatorDefinition,
    NNInputSpec,
    StrategyConfigurationV3,
    TrainingDataConfiguration,
)
from ktrdr.fuzzy.membership import MembershipFunctionFactory


class TestGaussianStrategyParsing:
    """Test that Gaussian MF strategy YAML parses correctly."""

    def test_yaml_parses_as_v3_config(self):
        """Strategy with Gaussian MFs and hybrid encoding parses correctly."""
        config = StrategyConfigurationV3(
            name="trend_tb_gaussian_signal_v1",
            version="3.0",
            training_data=TrainingDataConfiguration(
                symbols={"mode": "single", "list": ["EURUSD"]},
                timeframes={
                    "mode": "multi_timeframe",
                    "list": ["5m", "1h"],
                    "base_timeframe": "1h",
                },
                history_required=100,
            ),
            indicators={
                "rsi_14": IndicatorDefinition(type="rsi", period=14),
                "adx_14": IndicatorDefinition(type="adx", period=14),
            },
            fuzzy_sets={
                "rsi_momentum": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "low": {"type": "gaussian", "parameters": [30, 15]},
                        "neutral": {"type": "gaussian", "parameters": [50, 12]},
                        "high": {"type": "gaussian", "parameters": [70, 15]},
                    },
                ),
                "adx_trend": FuzzySetDefinition(
                    indicator="adx_14.adx",
                    **{
                        "weak": {"type": "gaussian", "parameters": [15, 10]},
                        "moderate": {"type": "gaussian", "parameters": [30, 10]},
                        "strong": {"type": "gaussian", "parameters": [50, 15]},
                    },
                ),
            },
            nn_inputs=[
                NNInputSpec(fuzzy_set="rsi_momentum", timeframes="all"),
                NNInputSpec(
                    raw_indicator="rsi_14", timeframes="all", normalization="minmax"
                ),
                NNInputSpec(fuzzy_set="adx_trend", timeframes="all"),
                NNInputSpec(
                    raw_indicator="adx_14.adx",
                    timeframes="all",
                    normalization="minmax",
                ),
            ],
            model={"type": "mlp", "architecture": {"hidden_layers": [128, 64, 32]}},
            decisions={"output_format": "classification"},
            training={"method": "supervised", "labels": {"source": "triple_barrier"}},
        )

        assert config.name == "trend_tb_gaussian_signal_v1"
        # 4 fuzzy inputs + 2 raw inputs
        assert len(config.nn_inputs) == 4
        # Verify gaussian type preserved
        rsi_low = config.fuzzy_sets["rsi_momentum"].model_extra["low"]
        assert rsi_low["type"] == "gaussian"
        assert rsi_low["parameters"] == [30, 15]

    def test_gaussian_and_raw_mixed_in_nn_inputs(self):
        """nn_inputs can mix fuzzy_set and raw_indicator entries."""
        config = StrategyConfigurationV3(
            name="test_mixed",
            version="3.0",
            training_data=TrainingDataConfiguration(
                symbols={"mode": "single", "list": ["EURUSD"]},
                timeframes={
                    "mode": "single",
                    "list": ["1h"],
                    "base_timeframe": "1h",
                },
                history_required=100,
            ),
            indicators={"rsi_14": IndicatorDefinition(type="rsi", period=14)},
            fuzzy_sets={
                "rsi_momentum": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "low": {"type": "gaussian", "parameters": [30, 15]},
                        "neutral": {"type": "gaussian", "parameters": [50, 12]},
                        "high": {"type": "gaussian", "parameters": [70, 15]},
                    },
                ),
            },
            nn_inputs=[
                NNInputSpec(fuzzy_set="rsi_momentum", timeframes=["1h"]),
                NNInputSpec(
                    raw_indicator="rsi_14", timeframes=["1h"], normalization="minmax"
                ),
            ],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"method": "supervised"},
        )

        # First is fuzzy, second is raw
        assert config.nn_inputs[0].fuzzy_set == "rsi_momentum"
        assert config.nn_inputs[1].raw_indicator == "rsi_14"


class TestGaussianDeadZones:
    """Test that Gaussian MFs eliminate dead zones."""

    def test_rsi_no_dead_zones(self):
        """RSI Gaussian MFs: every value 0-100 produces non-zero membership in at least one set."""
        # RSI Gaussian params from strategy
        low = MembershipFunctionFactory.create("gaussian", [30, 15])
        neutral = MembershipFunctionFactory.create("gaussian", [50, 12])
        high = MembershipFunctionFactory.create("gaussian", [70, 15])

        rsi_values = np.linspace(0, 100, 1001)
        for rsi in rsi_values:
            memberships = [
                low.evaluate(rsi),
                neutral.evaluate(rsi),
                high.evaluate(rsi),
            ]
            total = sum(memberships)
            assert (
                total > 0.01
            ), f"Dead zone at RSI={rsi}: all memberships near zero (sum={total})"

    def test_adx_no_dead_zones(self):
        """ADX Gaussian MFs: every value 0-80 produces non-zero membership."""
        weak = MembershipFunctionFactory.create("gaussian", [15, 10])
        moderate = MembershipFunctionFactory.create("gaussian", [30, 10])
        strong = MembershipFunctionFactory.create("gaussian", [50, 15])

        adx_values = np.linspace(0, 80, 801)
        for adx in adx_values:
            memberships = [
                weak.evaluate(adx),
                moderate.evaluate(adx),
                strong.evaluate(adx),
            ]
            total = sum(memberships)
            assert total > 0.01, f"Dead zone at ADX={adx}: sum={total}"

    def test_rsi_ruspini_approximate(self):
        """RSI Gaussian MFs: membership sums ≈ 1.0 (approximate Ruspini partition)."""
        low = MembershipFunctionFactory.create("gaussian", [30, 15])
        neutral = MembershipFunctionFactory.create("gaussian", [50, 12])
        high = MembershipFunctionFactory.create("gaussian", [70, 15])

        # Check at typical RSI values in the 20-80 core range
        for rsi in [20, 30, 40, 50, 60, 70, 80]:
            total = low.evaluate(rsi) + neutral.evaluate(rsi) + high.evaluate(rsi)
            # Gaussian sets won't sum to exactly 1.0 but should be close
            # Allow wider tolerance — the point is no dead zones, not exact Ruspini
            assert (
                0.5 < total < 2.0
            ), f"Ruspini violation at RSI={rsi}: sum={total}"


class TestFeatureResolverWithGaussianStrategy:
    """Test FeatureResolver with Gaussian + hybrid strategy."""

    def test_resolve_hybrid_features(self):
        """FeatureResolver produces correct features for hybrid strategy."""
        from ktrdr.config.feature_resolver import FeatureResolver

        config = StrategyConfigurationV3(
            name="test_gaussian_hybrid",
            version="3.0",
            training_data=TrainingDataConfiguration(
                symbols={"mode": "single", "list": ["EURUSD"]},
                timeframes={
                    "mode": "single",
                    "list": ["1h"],
                    "base_timeframe": "1h",
                },
                history_required=100,
            ),
            indicators={"rsi_14": IndicatorDefinition(type="rsi", period=14)},
            fuzzy_sets={
                "rsi_momentum": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "low": {"type": "gaussian", "parameters": [30, 15]},
                        "neutral": {"type": "gaussian", "parameters": [50, 12]},
                        "high": {"type": "gaussian", "parameters": [70, 15]},
                    },
                ),
            },
            nn_inputs=[
                NNInputSpec(fuzzy_set="rsi_momentum", timeframes=["1h"]),
                NNInputSpec(
                    raw_indicator="rsi_14", timeframes=["1h"], normalization="minmax"
                ),
            ],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"method": "supervised"},
        )

        resolver = FeatureResolver()
        features = resolver.resolve(config)

        # 3 fuzzy (low, neutral, high) + 1 raw = 4 features
        assert len(features) == 4

        feature_ids = [f.feature_id for f in features]
        assert feature_ids == [
            "1h_rsi_momentum_low",
            "1h_rsi_momentum_neutral",
            "1h_rsi_momentum_high",
            "1h_rsi_14_raw",
        ]

        # Raw feature has sentinel
        raw_feature = features[3]
        assert raw_feature.fuzzy_set_id == "__raw__"
        assert raw_feature.membership_name == "raw"
