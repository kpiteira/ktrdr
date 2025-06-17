"""
Tests for multi-timeframe label generation.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from ktrdr.training.multi_timeframe_label_generator import (
    MultiTimeframeLabelGenerator,
    MultiTimeframeLabelConfig,
    TimeframeLabelConfig,
    LabelClass,
    LabelValidationResult,
    MultiTimeframeLabelResult,
    create_multi_timeframe_label_generator,
)


class TestMultiTimeframeLabelGenerator:
    """Tests for MultiTimeframeLabelGenerator."""

    @pytest.fixture
    def sample_multi_timeframe_data(self):
        """Sample multi-timeframe price data."""
        np.random.seed(42)

        # Create realistic price data with trends
        base_dates = pd.date_range("2024-01-01", periods=200, freq="1h")
        base_price = 100.0

        data = {}

        # 1h data - most granular
        h1_prices = []
        current_price = base_price
        for i in range(200):
            change = np.random.normal(0, 0.5)  # 0.5% volatility
            current_price *= 1 + change / 100
            h1_prices.append(current_price)

        data["1h"] = pd.DataFrame(
            {
                "open": h1_prices,
                "high": [
                    p * (1 + abs(np.random.normal(0, 0.2) / 100)) for p in h1_prices
                ],
                "low": [
                    p * (1 - abs(np.random.normal(0, 0.2) / 100)) for p in h1_prices
                ],
                "close": h1_prices,
                "volume": np.random.randint(1000, 10000, 200),
            },
            index=base_dates,
        )

        # 4h data - aggregated from 1h
        h4_dates = base_dates[::4]  # Every 4 hours
        h4_data = []
        for i in range(0, len(h1_prices), 4):
            chunk = h1_prices[i : i + 4]
            if len(chunk) > 0:
                h4_data.append(
                    {
                        "open": chunk[0],
                        "high": max(chunk),
                        "low": min(chunk),
                        "close": chunk[-1],
                        "volume": sum([1000] * len(chunk)),  # Simplified volume
                    }
                )

        data["4h"] = pd.DataFrame(h4_data, index=h4_dates[: len(h4_data)])

        # 1d data - aggregated from 1h
        d1_dates = base_dates[::24]  # Every 24 hours
        d1_data = []
        for i in range(0, len(h1_prices), 24):
            chunk = h1_prices[i : i + 24]
            if len(chunk) > 0:
                d1_data.append(
                    {
                        "open": chunk[0],
                        "high": max(chunk),
                        "low": min(chunk),
                        "close": chunk[-1],
                        "volume": sum([1000] * len(chunk)),  # Simplified volume
                    }
                )

        data["1d"] = pd.DataFrame(d1_data, index=d1_dates[: len(d1_data)])

        return data

    @pytest.fixture
    def basic_config(self):
        """Basic multi-timeframe label configuration."""
        return MultiTimeframeLabelConfig(
            timeframe_configs={
                "1h": TimeframeLabelConfig(threshold=0.02, lookahead=10, weight=0.5),
                "4h": TimeframeLabelConfig(threshold=0.05, lookahead=5, weight=0.3),
                "1d": TimeframeLabelConfig(threshold=0.08, lookahead=3, weight=0.2),
            },
            consensus_method="weighted_majority",
            consistency_threshold=0.6,
            min_confidence_score=0.5,
        )

    @pytest.fixture
    def hierarchical_config(self):
        """Hierarchical multi-timeframe label configuration."""
        return MultiTimeframeLabelConfig(
            timeframe_configs={
                "1h": TimeframeLabelConfig(threshold=0.02, lookahead=10, weight=0.3),
                "4h": TimeframeLabelConfig(threshold=0.05, lookahead=5, weight=0.4),
                "1d": TimeframeLabelConfig(threshold=0.08, lookahead=3, weight=0.3),
            },
            consensus_method="hierarchy",
            consistency_threshold=0.7,
            min_confidence_score=0.6,
        )

    def test_generator_initialization(self, basic_config):
        """Test label generator initialization."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        assert generator.config == basic_config
        assert len(generator.timeframe_labelers) == 3
        assert "1h" in generator.timeframe_labelers
        assert "4h" in generator.timeframe_labelers
        assert "1d" in generator.timeframe_labelers

    def test_basic_label_generation(self, sample_multi_timeframe_data, basic_config):
        """Test basic multi-timeframe label generation."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(
            sample_multi_timeframe_data, method="consensus"
        )

        assert isinstance(result, MultiTimeframeLabelResult)
        assert len(result.labels) > 0
        assert len(result.timeframe_labels) == 3
        assert len(result.confidence_scores) == len(result.labels)
        assert len(result.consistency_scores) == len(result.labels)
        assert isinstance(result.label_distribution, dict)
        assert isinstance(result.metadata, dict)

    def test_hierarchical_label_generation(
        self, sample_multi_timeframe_data, hierarchical_config
    ):
        """Test hierarchical label generation method."""
        generator = MultiTimeframeLabelGenerator(hierarchical_config)

        result = generator.generate_labels(
            sample_multi_timeframe_data, method="hierarchy"
        )

        assert isinstance(result, MultiTimeframeLabelResult)
        assert len(result.labels) > 0
        assert "consensus" in result.label_distribution
        assert "timeframes" in result.label_distribution

    def test_weighted_label_generation(self, sample_multi_timeframe_data, basic_config):
        """Test weighted label generation method."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(
            sample_multi_timeframe_data, method="weighted"
        )

        assert isinstance(result, MultiTimeframeLabelResult)
        assert len(result.labels) > 0

        # Check that confidence scores are reasonable
        assert result.confidence_scores.min() >= 0.0
        assert result.confidence_scores.max() <= 1.0

    def test_label_validation(self, sample_multi_timeframe_data, basic_config):
        """Test cross-timeframe label validation."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(sample_multi_timeframe_data)

        # Check validation results
        assert len(result.validation_results) > 0

        # Check individual validation result structure
        sample_validation = next(iter(result.validation_results.values()))
        assert isinstance(sample_validation, LabelValidationResult)
        assert hasattr(sample_validation, "is_valid")
        assert hasattr(sample_validation, "consistency_score")
        assert hasattr(sample_validation, "confidence_score")
        assert isinstance(sample_validation.timeframe_agreement, dict)

    def test_temporal_consistency_validation(
        self, sample_multi_timeframe_data, basic_config
    ):
        """Test temporal consistency validation."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(sample_multi_timeframe_data)

        # Test temporal consistency analysis
        temporal_metrics = generator.validate_temporal_consistency(
            result.labels, result.timeframe_labels
        )

        assert "temporal_consistency" in temporal_metrics
        assert "total_label_changes" in temporal_metrics
        assert "change_frequency" in temporal_metrics
        assert "longest_stable_sequence" in temporal_metrics

        # Consistency should be between 0 and 1
        assert 0.0 <= temporal_metrics["temporal_consistency"] <= 1.0

    def test_label_quality_analysis(self, sample_multi_timeframe_data, basic_config):
        """Test label quality analysis."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(sample_multi_timeframe_data)

        # Analyze label quality
        quality_metrics = generator.analyze_label_quality(result)

        assert "label_count" in quality_metrics
        assert "average_confidence" in quality_metrics
        assert "average_consistency" in quality_metrics
        assert "class_balance" in quality_metrics
        assert "temporal_quality" in quality_metrics
        assert "cross_timeframe_agreement" in quality_metrics

        # Check class balance metrics
        balance_metrics = quality_metrics["class_balance"]
        assert "buy_ratio" in balance_metrics
        assert "hold_ratio" in balance_metrics
        assert "sell_ratio" in balance_metrics
        assert "balance_score" in balance_metrics

        # Ratios should sum to approximately 1.0
        total_ratio = (
            balance_metrics["buy_ratio"]
            + balance_metrics["hold_ratio"]
            + balance_metrics["sell_ratio"]
        )
        assert abs(total_ratio - 1.0) < 0.01

    def test_label_distribution_calculation(
        self, sample_multi_timeframe_data, basic_config
    ):
        """Test label distribution calculation."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        result = generator.generate_labels(sample_multi_timeframe_data)

        distribution = result.label_distribution

        # Check consensus distribution
        assert "consensus" in distribution
        consensus_dist = distribution["consensus"]
        assert "buy_count" in consensus_dist
        assert "hold_count" in consensus_dist
        assert "sell_count" in consensus_dist
        assert "total" in consensus_dist

        # Check that counts sum to total
        total_count = (
            consensus_dist["buy_count"]
            + consensus_dist["hold_count"]
            + consensus_dist["sell_count"]
        )
        assert total_count == consensus_dist["total"]

        # Check timeframe distributions
        assert "timeframes" in distribution
        for timeframe in basic_config.timeframe_configs.keys():
            assert timeframe in distribution["timeframes"]

    def test_label_smoothing(self, sample_multi_timeframe_data, basic_config):
        """Test label smoothing functionality."""
        # Enable label smoothing
        basic_config.label_smoothing = True

        generator = MultiTimeframeLabelGenerator(basic_config)
        result = generator.generate_labels(sample_multi_timeframe_data)

        # Generate labels without smoothing for comparison
        basic_config.label_smoothing = False
        generator_no_smooth = MultiTimeframeLabelGenerator(basic_config)
        result_no_smooth = generator_no_smooth.generate_labels(
            sample_multi_timeframe_data
        )

        # Labels should be the same length
        assert len(result.labels) == len(result_no_smooth.labels)

        # Can't guarantee they'll be different since smoothing depends on confidence
        # But we can check that smoothing didn't break anything
        assert all(label in [0, 1, 2] for label in result.labels)

    def test_empty_data_handling(self, basic_config):
        """Test handling of empty data."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        empty_data = {}
        result = generator.generate_labels(empty_data)

        # Should handle empty data gracefully
        assert isinstance(result, MultiTimeframeLabelResult)
        assert len(result.labels) == 0
        assert len(result.timeframe_labels) == 0

    def test_single_timeframe_data(self, basic_config):
        """Test handling of single timeframe data."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        # Create single timeframe data
        single_tf_data = {
            "1h": pd.DataFrame(
                {
                    "open": [100, 101, 102, 103, 104],
                    "high": [100.5, 101.5, 102.5, 103.5, 104.5],
                    "low": [99.5, 100.5, 101.5, 102.5, 103.5],
                    "close": [100, 101, 102, 103, 104],
                    "volume": [1000, 1000, 1000, 1000, 1000],
                },
                index=pd.date_range("2024-01-01", periods=5, freq="1h"),
            )
        }

        result = generator.generate_labels(single_tf_data)

        assert isinstance(result, MultiTimeframeLabelResult)
        assert len(result.timeframe_labels) == 1
        assert "1h" in result.timeframe_labels

    def test_mismatched_timeframes(self, basic_config):
        """Test handling of data with different timeframes than config."""
        generator = MultiTimeframeLabelGenerator(basic_config)

        # Create data with only some configured timeframes
        partial_data = {
            "1h": pd.DataFrame(
                {
                    "open": [100, 101, 102],
                    "high": [100.5, 101.5, 102.5],
                    "low": [99.5, 100.5, 101.5],
                    "close": [100, 101, 102],
                    "volume": [1000, 1000, 1000],
                },
                index=pd.date_range("2024-01-01", periods=3, freq="1h"),
            ),
            "2h": pd.DataFrame(
                {  # Not in config
                    "open": [100, 102],
                    "high": [100.5, 102.5],
                    "low": [99.5, 101.5],
                    "close": [100, 102],
                    "volume": [2000, 2000],
                },
                index=pd.date_range("2024-01-01", periods=2, freq="2h"),
            ),
        }

        result = generator.generate_labels(partial_data)

        # Should handle gracefully and only process configured timeframes
        assert isinstance(result, MultiTimeframeLabelResult)
        # Only 1h should be processed (2h is not in config)
        assert len(result.timeframe_labels) <= 1

    def test_factory_function(self):
        """Test factory function for creating label generator."""
        config_dict = {
            "timeframe_configs": {
                "1h": {"threshold": 0.02, "lookahead": 10, "weight": 0.5},
                "4h": {"threshold": 0.05, "lookahead": 5, "weight": 0.3},
                "1d": {"threshold": 0.08, "lookahead": 3, "weight": 0.2},
            },
            "consensus_method": "weighted_majority",
            "consistency_threshold": 0.7,
            "min_confidence_score": 0.6,
        }

        generator = create_multi_timeframe_label_generator(config_dict)

        assert isinstance(generator, MultiTimeframeLabelGenerator)
        assert len(generator.config.timeframe_configs) == 3
        assert generator.config.consensus_method == "weighted_majority"
        assert generator.config.consistency_threshold == 0.7

    def test_confidence_threshold_filtering(self, sample_multi_timeframe_data):
        """Test that low confidence labels are filtered to HOLD."""
        # Create config with high confidence threshold
        high_confidence_config = MultiTimeframeLabelConfig(
            timeframe_configs={
                "1h": TimeframeLabelConfig(threshold=0.02, lookahead=10, weight=1.0)
            },
            min_confidence_score=0.9,  # Very high threshold
        )

        generator = MultiTimeframeLabelGenerator(high_confidence_config)
        result = generator.generate_labels(sample_multi_timeframe_data)

        # Most labels should be HOLD due to high confidence threshold
        hold_count = (result.labels == LabelClass.HOLD.value).sum()
        total_count = len(result.labels)

        # At least 50% should be HOLD with such a high threshold
        assert hold_count / total_count >= 0.5

    def test_label_metadata_creation(self, sample_multi_timeframe_data, basic_config):
        """Test comprehensive metadata creation."""
        generator = MultiTimeframeLabelGenerator(basic_config)
        result = generator.generate_labels(sample_multi_timeframe_data)

        metadata = result.metadata

        assert "timeframes" in metadata
        assert "consensus_method" in metadata
        assert "generation_timestamp" in metadata
        assert "data_statistics" in metadata
        assert "validation_statistics" in metadata
        assert "timeframe_coverage" in metadata

        # Check data statistics
        data_stats = metadata["data_statistics"]
        for timeframe in basic_config.timeframe_configs.keys():
            if timeframe in sample_multi_timeframe_data:
                assert timeframe in data_stats
                assert "total_bars" in data_stats[timeframe]
                assert "start_time" in data_stats[timeframe]
                assert "end_time" in data_stats[timeframe]


class TestTimeframeLabelConfig:
    """Tests for TimeframeLabelConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TimeframeLabelConfig()

        assert config.threshold == 0.05
        assert config.lookahead == 20
        assert config.min_swing_length == 3
        assert config.weight == 1.0
        assert config.method == "zigzag"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TimeframeLabelConfig(
            threshold=0.03,
            lookahead=15,
            min_swing_length=5,
            weight=0.7,
            method="simple_return",
        )

        assert config.threshold == 0.03
        assert config.lookahead == 15
        assert config.min_swing_length == 5
        assert config.weight == 0.7
        assert config.method == "simple_return"


class TestMultiTimeframeLabelConfig:
    """Tests for MultiTimeframeLabelConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MultiTimeframeLabelConfig(
            timeframe_configs={"1h": TimeframeLabelConfig()}
        )

        assert config.consensus_method == "weighted_majority"
        assert config.consistency_threshold == 0.7
        assert config.require_alignment is True
        assert config.temporal_gap_tolerance == 2
        assert config.min_confidence_score == 0.6
        assert config.label_smoothing is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MultiTimeframeLabelConfig(
            timeframe_configs={
                "1h": TimeframeLabelConfig(weight=0.5),
                "4h": TimeframeLabelConfig(weight=0.3),
            },
            consensus_method="hierarchy",
            consistency_threshold=0.8,
            require_alignment=False,
            min_confidence_score=0.7,
            label_smoothing=False,
        )

        assert len(config.timeframe_configs) == 2
        assert config.consensus_method == "hierarchy"
        assert config.consistency_threshold == 0.8
        assert config.require_alignment is False
        assert config.min_confidence_score == 0.7
        assert config.label_smoothing is False


class TestLabelValidationResult:
    """Tests for LabelValidationResult."""

    def test_validation_result_creation(self):
        """Test creating LabelValidationResult objects."""
        result = LabelValidationResult(
            is_valid=True,
            consistency_score=0.8,
            timeframe_agreement={"1h": True, "4h": False},
            confidence_score=0.7,
            temporal_alignment_score=0.9,
            validation_details={"test": "value"},
        )

        assert result.is_valid is True
        assert result.consistency_score == 0.8
        assert result.timeframe_agreement["1h"] is True
        assert result.confidence_score == 0.7
        assert result.temporal_alignment_score == 0.9
        assert result.validation_details["test"] == "value"


class TestMultiTimeframeLabelResult:
    """Tests for MultiTimeframeLabelResult."""

    def test_result_creation(self):
        """Test creating MultiTimeframeLabelResult objects."""
        labels = pd.Series([0, 1, 2], index=pd.date_range("2024-01-01", periods=3))
        confidence_scores = pd.Series(
            [0.8, 0.6, 0.9], index=pd.date_range("2024-01-01", periods=3)
        )

        result = MultiTimeframeLabelResult(
            labels=labels,
            timeframe_labels={"1h": labels},
            confidence_scores=confidence_scores,
            consistency_scores=confidence_scores,
            validation_results={},
            label_distribution={"consensus": {"total": 3}},
            metadata={"timeframes": ["1h"]},
        )

        assert len(result.labels) == 3
        assert len(result.timeframe_labels) == 1
        assert len(result.confidence_scores) == 3
        assert isinstance(result.label_distribution, dict)
        assert isinstance(result.metadata, dict)


class TestLabelClass:
    """Tests for LabelClass enum."""

    def test_label_values(self):
        """Test label class values."""
        assert LabelClass.BUY.value == 0
        assert LabelClass.HOLD.value == 1
        assert LabelClass.SELL.value == 2

    def test_label_names(self):
        """Test label class names."""
        assert LabelClass.BUY.name == "BUY"
        assert LabelClass.HOLD.name == "HOLD"
        assert LabelClass.SELL.name == "SELL"
