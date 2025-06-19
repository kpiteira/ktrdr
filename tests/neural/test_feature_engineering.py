"""
Tests for multi-timeframe feature engineering.
"""

import pytest
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ktrdr.neural.feature_engineering import (
    MultiTimeframeFeatureEngineer,
    FeatureStats,
    FeatureEngineeringResult,
    create_feature_engineer,
)


class TestMultiTimeframeFeatureEngineer:
    """Tests for MultiTimeframeFeatureEngineer."""

    @pytest.fixture
    def sample_features(self):
        """Sample multi-timeframe features."""
        np.random.seed(42)
        return {
            "1h": np.random.randn(100, 10),
            "4h": np.random.randn(100, 8),
            "1d": np.random.randn(100, 5),
        }

    @pytest.fixture
    def sample_labels(self):
        """Sample labels for supervised feature selection."""
        np.random.seed(42)
        return np.random.choice([0, 1, 2], size=100, p=[0.3, 0.4, 0.3])

    @pytest.fixture
    def basic_config(self):
        """Basic feature engineering configuration."""
        return {
            "scaling": {"method": "standard"},
            "selection": {"method": "none"},
            "dimensionality_reduction": {"method": "none"},
        }

    @pytest.fixture
    def advanced_config(self):
        """Advanced feature engineering configuration."""
        return {
            "scaling": {"method": "standard"},
            "selection": {"method": "kbest_f", "k": 15},
            "dimensionality_reduction": {"method": "pca", "n_components": 10},
        }

    def test_engineer_initialization(self, basic_config):
        """Test feature engineer initialization."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)

        assert engineer.config == basic_config
        assert engineer.scaler is None
        assert engineer.feature_selector is None
        assert engineer.dimensionality_reducer is None
        assert not engineer.is_fitted

    def test_basic_fit_transform(self, sample_features, sample_labels, basic_config):
        """Test basic fit_transform without selection or reduction."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)

        result = engineer.fit_transform(sample_features, sample_labels)

        assert isinstance(result, FeatureEngineeringResult)
        assert result.transformed_features.shape[0] == 100  # Same number of samples
        assert len(result.feature_names) > 0
        assert result.scaler is not None
        assert result.feature_stats is not None
        assert engineer.is_fitted

    def test_advanced_fit_transform(
        self, sample_features, sample_labels, advanced_config
    ):
        """Test advanced fit_transform with selection and reduction."""
        engineer = MultiTimeframeFeatureEngineer(advanced_config)

        result = engineer.fit_transform(sample_features, sample_labels)

        assert isinstance(result, FeatureEngineeringResult)
        assert result.transformed_features.shape[0] == 100
        assert result.transformed_features.shape[1] == 10  # PCA components
        assert result.selected_features_mask is not None
        assert result.dimensionality_reducer is not None
        assert engineer.is_fitted

    def test_transform_after_fit(self, sample_features, sample_labels, advanced_config):
        """Test transform method after fit_transform."""
        engineer = MultiTimeframeFeatureEngineer(advanced_config)

        # Fit on original data
        fit_result = engineer.fit_transform(sample_features, sample_labels)

        # Transform new data
        new_features = {
            "1h": np.random.randn(50, 10),
            "4h": np.random.randn(50, 8),
            "1d": np.random.randn(50, 5),
        }

        transformed = engineer.transform(new_features)

        assert transformed.shape[0] == 50
        assert transformed.shape[1] == fit_result.transformed_features.shape[1]

    def test_transform_before_fit_error(self, sample_features, basic_config):
        """Test that transform raises error before fit."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)

        with pytest.raises(ValueError) as exc_info:
            engineer.transform(sample_features)
        assert "not fitted" in str(exc_info.value)

    def test_feature_stats_calculation(
        self, sample_features, sample_labels, basic_config
    ):
        """Test feature statistics calculation."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)
        result = engineer.fit_transform(sample_features, sample_labels)

        assert result.feature_stats is not None
        assert len(result.feature_stats) == len(result.feature_names)

        # Check a sample feature stat
        first_feature_name = result.feature_names[0]
        first_stat = result.feature_stats[first_feature_name]

        assert isinstance(first_stat, FeatureStats)
        assert hasattr(first_stat, "mean")
        assert hasattr(first_stat, "std")
        assert hasattr(first_stat, "correlation_with_target")

    def test_different_scaling_methods(self, sample_features, sample_labels):
        """Test different scaling methods."""
        scaling_methods = ["standard", "minmax", "robust", "quantile", "none"]

        for method in scaling_methods:
            config = {
                "scaling": {"method": method},
                "selection": {"method": "none"},
                "dimensionality_reduction": {"method": "none"},
            }

            engineer = MultiTimeframeFeatureEngineer(config)
            result = engineer.fit_transform(sample_features, sample_labels)

            assert result.transformed_features.shape[0] == 100
            if method != "none":
                assert result.scaler is not None
            else:
                assert result.scaler is None

    def test_different_selection_methods(self, sample_features, sample_labels):
        """Test different feature selection methods."""
        selection_methods = [
            {"method": "kbest_f", "k": 15},
            {"method": "kbest_mutual_info", "k": 15},
            {"method": "rfe", "n_features": 15},
            {"method": "variance_threshold", "threshold": 0.01},
        ]

        for selection_config in selection_methods:
            config = {
                "scaling": {"method": "standard"},
                "selection": selection_config,
                "dimensionality_reduction": {"method": "none"},
            }

            engineer = MultiTimeframeFeatureEngineer(config)
            result = engineer.fit_transform(sample_features, sample_labels)

            assert result.transformed_features.shape[0] == 100
            assert result.selected_features_mask is not None
            assert engineer.feature_selector is not None

    def test_different_reduction_methods(self, sample_features, sample_labels):
        """Test different dimensionality reduction methods."""
        reduction_methods = [
            {"method": "pca", "n_components": 8},
            {"method": "ica", "n_components": 8},
            {"method": "svd", "n_components": 8},
        ]

        for reduction_config in reduction_methods:
            config = {
                "scaling": {"method": "standard"},
                "selection": {"method": "none"},
                "dimensionality_reduction": reduction_config,
            }

            engineer = MultiTimeframeFeatureEngineer(config)
            result = engineer.fit_transform(sample_features, sample_labels)

            assert result.transformed_features.shape[0] == 100
            assert result.transformed_features.shape[1] == 8
            assert result.dimensionality_reducer is not None

    def test_timeframe_weights(self, sample_features, sample_labels, basic_config):
        """Test timeframe weighting functionality."""
        timeframe_weights = {"1h": 2.0, "4h": 1.0, "1d": 0.5}

        engineer = MultiTimeframeFeatureEngineer(basic_config)
        result = engineer.fit_transform(
            sample_features, sample_labels, timeframe_weights
        )

        assert result.transformed_features.shape[0] == 100
        assert (
            len(result.feature_names) == 10 + 8 + 5
        )  # Total features from all timeframes

    def test_feature_importance_calculation(
        self, sample_features, sample_labels, basic_config
    ):
        """Test feature importance calculation."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)
        result = engineer.fit_transform(sample_features, sample_labels)

        assert result.feature_importance is not None
        assert len(result.feature_importance) == len(result.feature_names)

        # Check that importances sum to approximately 1.0
        total_importance = sum(result.feature_importance.values())
        assert 0.8 <= total_importance <= 1.2  # Allow some numerical tolerance

    def test_analyze_timeframe_contributions(
        self, sample_features, sample_labels, basic_config
    ):
        """Test timeframe contribution analysis."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)
        engineer.fit_transform(sample_features, sample_labels)

        analysis = engineer.analyze_timeframe_contributions(
            sample_features, sample_labels
        )

        assert "timeframe_feature_counts" in analysis
        assert "timeframe_importance_scores" in analysis
        assert "recommended_weights" in analysis

        # Check feature counts
        assert analysis["timeframe_feature_counts"]["1h"] == 10
        assert analysis["timeframe_feature_counts"]["4h"] == 8
        assert analysis["timeframe_feature_counts"]["1d"] == 5

        # Check that recommended weights sum to 1.0
        total_weight = sum(analysis["recommended_weights"].values())
        assert abs(total_weight - 1.0) < 0.01

    def test_empty_features_error(self, basic_config):
        """Test error handling for empty features."""
        engineer = MultiTimeframeFeatureEngineer(basic_config)

        with pytest.raises(ValueError) as exc_info:
            engineer.fit_transform({})
        assert "No features provided" in str(exc_info.value)

    def test_feature_ranking(self, sample_features, sample_labels):
        """Test feature ranking functionality."""
        config = {
            "scaling": {"method": "standard"},
            "selection": {"method": "kbest_f", "k": 15},
            "dimensionality_reduction": {"method": "none"},
        }

        engineer = MultiTimeframeFeatureEngineer(config)
        engineer.fit_transform(sample_features, sample_labels)

        ranking = engineer.get_feature_ranking()

        assert ranking is not None
        assert len(ranking) == 15  # k=15 features selected

        # Check that ranking is sorted (higher scores first)
        scores = [score for _, score in ranking]
        assert scores == sorted(scores, reverse=True)

    def test_transformation_metadata(
        self, sample_features, sample_labels, advanced_config
    ):
        """Test transformation metadata."""
        engineer = MultiTimeframeFeatureEngineer(advanced_config)
        result = engineer.fit_transform(sample_features, sample_labels)

        metadata = result.transformation_metadata

        assert "original_feature_count" in metadata
        assert "selected_feature_count" in metadata
        assert "final_feature_count" in metadata
        assert "scaling_method" in metadata
        assert "selection_method" in metadata
        assert "reduction_method" in metadata
        assert "timeframes" in metadata

        assert metadata["original_feature_count"] == 23  # 10+8+5
        assert metadata["selected_feature_count"] == 15  # k=15
        assert metadata["final_feature_count"] == 10  # PCA components
        assert metadata["scaling_method"] == "standard"
        assert metadata["selection_method"] == "kbest_f"
        assert metadata["reduction_method"] == "pca"

    def test_factory_function(self, basic_config):
        """Test factory function for creating feature engineer."""
        engineer = create_feature_engineer(basic_config)

        assert isinstance(engineer, MultiTimeframeFeatureEngineer)
        assert engineer.config == basic_config


class TestFeatureStats:
    """Tests for FeatureStats dataclass."""

    def test_feature_stats_creation(self):
        """Test creating FeatureStats objects."""
        stats = FeatureStats(
            mean=0.5,
            std=0.2,
            min_val=0.0,
            max_val=1.0,
            percentile_25=0.3,
            percentile_75=0.7,
            skewness=0.1,
            correlation_with_target=0.3,
        )

        assert stats.mean == 0.5
        assert stats.std == 0.2
        assert stats.correlation_with_target == 0.3


class TestFeatureEngineeringResult:
    """Tests for FeatureEngineeringResult dataclass."""

    def test_result_creation(self):
        """Test creating FeatureEngineeringResult objects."""
        features = np.random.randn(50, 10)
        feature_names = [f"feature_{i}" for i in range(10)]

        result = FeatureEngineeringResult(
            transformed_features=features,
            feature_names=feature_names,
            selected_features_mask=np.ones(10, dtype=bool),
            scaler=StandardScaler(),
            feature_importance={"feature_0": 0.5, "feature_1": 0.3},
            transformation_metadata={"method": "test"},
        )

        assert result.transformed_features.shape == (50, 10)
        assert len(result.feature_names) == 10
        assert result.selected_features_mask is not None
        assert result.scaler is not None
        assert len(result.feature_importance) == 2
        assert result.transformation_metadata["method"] == "test"
