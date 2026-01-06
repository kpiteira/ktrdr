"""Unit tests for FeatureResolver (v3 strategy config)."""

import pytest

from ktrdr.config.feature_resolver import FeatureResolver, ResolvedFeature
from ktrdr.config.models import (
    FuzzySetDefinition,
    IndicatorDefinition,
    NNInputSpec,
    StrategyConfigurationV3,
    TrainingDataConfiguration,
)


@pytest.fixture
def simple_config() -> StrategyConfigurationV3:
    """Create a simple v3 config for testing."""
    return StrategyConfigurationV3(
        name="test_strategy",
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
            "rsi_14": IndicatorDefinition(type="rsi", **{"period": 14}),
            "bbands_20_2": IndicatorDefinition(
                type="bbands", **{"period": 20, "multiplier": 2.0}
            ),
        },
        fuzzy_sets={
            "rsi_fast": FuzzySetDefinition(
                indicator="rsi_14",
                **{
                    "oversold": {"type": "triangular", "parameters": [0, 25, 40]},
                    "overbought": {"type": "triangular", "parameters": [60, 75, 100]},
                },
            ),
            "bbands_squeeze": FuzzySetDefinition(
                indicator="bbands_20_2.middle",
                **{
                    "tight": {"type": "triangular", "parameters": [0, 0.5, 1.0]},
                    "wide": {"type": "triangular", "parameters": [1.5, 2.5, 5.0]},
                },
            ),
        },
        nn_inputs=[
            NNInputSpec(fuzzy_set="rsi_fast", timeframes=["5m"]),
            NNInputSpec(fuzzy_set="bbands_squeeze", timeframes="all"),
        ],
        model={"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
        decisions={"output_format": "classification"},
        training={"method": "supervised", "labels": {"source": "zigzag"}},
    )


class TestResolvedFeature:
    """Test ResolvedFeature dataclass."""

    def test_resolved_feature_creation(self):
        """Test creating a ResolvedFeature."""
        feature = ResolvedFeature(
            feature_id="5m_rsi_fast_oversold",
            timeframe="5m",
            fuzzy_set_id="rsi_fast",
            membership_name="oversold",
            indicator_id="rsi_14",
            indicator_output=None,
        )

        assert feature.feature_id == "5m_rsi_fast_oversold"
        assert feature.timeframe == "5m"
        assert feature.fuzzy_set_id == "rsi_fast"
        assert feature.membership_name == "oversold"
        assert feature.indicator_id == "rsi_14"
        assert feature.indicator_output is None

    def test_resolved_feature_with_dot_notation(self):
        """Test ResolvedFeature with multi-output indicator."""
        feature = ResolvedFeature(
            feature_id="1h_bbands_squeeze_tight",
            timeframe="1h",
            fuzzy_set_id="bbands_squeeze",
            membership_name="tight",
            indicator_id="bbands_20_2",
            indicator_output="middle",
        )

        assert feature.indicator_id == "bbands_20_2"
        assert feature.indicator_output == "middle"


class TestFeatureResolver:
    """Test FeatureResolver class."""

    def test_resolver_instantiation(self):
        """Test creating a FeatureResolver."""
        resolver = FeatureResolver()
        assert resolver is not None

    def test_resolve_simple_config(self, simple_config):
        """Test resolving a simple config with explicit timeframes."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        # Should have 6 features total:
        # - rsi_fast × [5m] × [oversold, overbought] = 2
        # - bbands_squeeze × [5m, 1h] × [tight, wide] = 4
        assert len(features) == 6

        # Check feature IDs
        feature_ids = [f.feature_id for f in features]
        assert "5m_rsi_fast_oversold" in feature_ids
        assert "5m_rsi_fast_overbought" in feature_ids
        assert "5m_bbands_squeeze_tight" in feature_ids
        assert "5m_bbands_squeeze_wide" in feature_ids
        assert "1h_bbands_squeeze_tight" in feature_ids
        assert "1h_bbands_squeeze_wide" in feature_ids

    def test_resolve_all_timeframes(self):
        """Test resolving with timeframes: 'all'."""
        config = StrategyConfigurationV3(
            name="test_all_tf",
            version="3.0",
            training_data=TrainingDataConfiguration(
                symbols={"mode": "single", "list": ["EURUSD"]},
                timeframes={
                    "mode": "multi_timeframe",
                    "list": ["5m", "1h", "1d"],
                    "base_timeframe": "1h",
                },
                history_required=100,
            ),
            indicators={"rsi_14": IndicatorDefinition(type="rsi", **{"period": 14})},
            fuzzy_sets={
                "rsi_fast": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{"oversold": {"type": "triangular", "parameters": [0, 25, 40]}},
                )
            },
            nn_inputs=[NNInputSpec(fuzzy_set="rsi_fast", timeframes="all")],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"method": "supervised"},
        )

        resolver = FeatureResolver()
        features = resolver.resolve(config)

        # Should have 3 features: rsi_fast × [5m, 1h, 1d] × [oversold] = 3
        assert len(features) == 3

        feature_ids = [f.feature_id for f in features]
        assert "5m_rsi_fast_oversold" in feature_ids
        assert "1h_rsi_fast_oversold" in feature_ids
        assert "1d_rsi_fast_oversold" in feature_ids

    def test_feature_order_deterministic(self, simple_config):
        """Test that feature order is deterministic."""
        resolver = FeatureResolver()

        features1 = resolver.resolve(simple_config)
        features2 = resolver.resolve(simple_config)

        # Same input should produce same order
        assert [f.feature_id for f in features1] == [f.feature_id for f in features2]

    def test_feature_order_matches_nn_inputs_order(self, simple_config):
        """Test that feature order follows nn_inputs list order."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        feature_ids = [f.feature_id for f in features]

        # First nn_input is rsi_fast with timeframes=[5m]
        # Should produce first 2 features
        assert feature_ids[0] == "5m_rsi_fast_oversold"
        assert feature_ids[1] == "5m_rsi_fast_overbought"

        # Second nn_input is bbands_squeeze with timeframes=all (5m, 1h)
        # Should produce next 4 features
        assert feature_ids[2] == "5m_bbands_squeeze_tight"
        assert feature_ids[3] == "5m_bbands_squeeze_wide"
        assert feature_ids[4] == "1h_bbands_squeeze_tight"
        assert feature_ids[5] == "1h_bbands_squeeze_wide"

    def test_dot_notation_parsing(self, simple_config):
        """Test parsing of dot notation for multi-output indicators."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        # Find bbands_squeeze features
        bbands_features = [f for f in features if f.fuzzy_set_id == "bbands_squeeze"]

        # All bbands_squeeze features should have indicator_id=bbands_20_2
        # and indicator_output=middle
        for feature in bbands_features:
            assert feature.indicator_id == "bbands_20_2"
            assert feature.indicator_output == "middle"

    def test_dot_notation_no_output(self, simple_config):
        """Test indicators without dot notation have None output."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        # Find rsi_fast features (no dot notation)
        rsi_features = [f for f in features if f.fuzzy_set_id == "rsi_fast"]

        for feature in rsi_features:
            assert feature.indicator_id == "rsi_14"
            assert feature.indicator_output is None

    def test_get_indicators_for_timeframe(self, simple_config):
        """Test getting indicators needed for a specific timeframe."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        indicators_5m = resolver.get_indicators_for_timeframe(features, "5m")
        indicators_1h = resolver.get_indicators_for_timeframe(features, "1h")

        # 5m needs both rsi_14 and bbands_20_2
        assert indicators_5m == {"rsi_14", "bbands_20_2"}

        # 1h only needs bbands_20_2
        assert indicators_1h == {"bbands_20_2"}

    def test_get_fuzzy_sets_for_timeframe(self, simple_config):
        """Test getting fuzzy sets needed for a specific timeframe."""
        resolver = FeatureResolver()
        features = resolver.resolve(simple_config)

        fuzzy_sets_5m = resolver.get_fuzzy_sets_for_timeframe(features, "5m")
        fuzzy_sets_1h = resolver.get_fuzzy_sets_for_timeframe(features, "1h")

        # 5m needs both fuzzy sets
        assert fuzzy_sets_5m == {"rsi_fast", "bbands_squeeze"}

        # 1h only needs bbands_squeeze
        assert fuzzy_sets_1h == {"bbands_squeeze"}

    def test_multiple_fuzzy_sets_same_indicator(self):
        """Test multiple fuzzy sets referencing the same indicator."""
        config = StrategyConfigurationV3(
            name="test_multiple",
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
            indicators={"rsi_14": IndicatorDefinition(type="rsi", **{"period": 14})},
            fuzzy_sets={
                "rsi_fast": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "oversold": {"type": "triangular", "parameters": [0, 25, 40]},
                        "overbought": {
                            "type": "triangular",
                            "parameters": [60, 75, 100],
                        },
                    },
                ),
                "rsi_slow": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "oversold": {"type": "triangular", "parameters": [0, 15, 25]},
                        "overbought": {
                            "type": "triangular",
                            "parameters": [75, 85, 100],
                        },
                    },
                ),
            },
            nn_inputs=[
                NNInputSpec(fuzzy_set="rsi_fast", timeframes=["1h"]),
                NNInputSpec(fuzzy_set="rsi_slow", timeframes=["1h"]),
            ],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"method": "supervised"},
        )

        resolver = FeatureResolver()
        features = resolver.resolve(config)

        # Should have 4 features: 2 fuzzy sets × 1 timeframe × 2 memberships each
        assert len(features) == 4

        feature_ids = [f.feature_id for f in features]
        assert "1h_rsi_fast_oversold" in feature_ids
        assert "1h_rsi_fast_overbought" in feature_ids
        assert "1h_rsi_slow_oversold" in feature_ids
        assert "1h_rsi_slow_overbought" in feature_ids

        # All should reference the same indicator
        for feature in features:
            assert feature.indicator_id == "rsi_14"

    def test_membership_order_preserved(self):
        """Test that membership function order is preserved from fuzzy_set."""
        config = StrategyConfigurationV3(
            name="test_order",
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
            indicators={"rsi_14": IndicatorDefinition(type="rsi", **{"period": 14})},
            fuzzy_sets={
                "rsi_levels": FuzzySetDefinition(
                    indicator="rsi_14",
                    **{
                        "low": {"type": "triangular", "parameters": [0, 20, 40]},
                        "medium": {"type": "triangular", "parameters": [30, 50, 70]},
                        "high": {"type": "triangular", "parameters": [60, 80, 100]},
                    },
                )
            },
            nn_inputs=[NNInputSpec(fuzzy_set="rsi_levels", timeframes=["1h"])],
            model={"type": "mlp"},
            decisions={"output_format": "classification"},
            training={"method": "supervised"},
        )

        resolver = FeatureResolver()
        features = resolver.resolve(config)

        # Should have 3 features in order: low, medium, high
        assert len(features) == 3
        assert features[0].membership_name == "low"
        assert features[1].membership_name == "medium"
        assert features[2].membership_name == "high"
