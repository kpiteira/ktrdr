"""Tests for regression-specific metrics collection."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ktrdr.training.analytics.metrics_collector import MetricsCollector  # noqa: E402


class TestCollectRegressionMetrics:
    """Tests for MetricsCollector.collect_regression_metrics()."""

    def setup_method(self):
        self.collector = MetricsCollector()

    def test_mse_calculated_correctly(self):
        """MSE should be mean of squared errors."""
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.1, 2.2, 2.7])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        expected_mse = np.mean((y_true - y_pred) ** 2)
        assert abs(result["mse"] - expected_mse) < 1e-6

    def test_mae_calculated_correctly(self):
        """MAE should be mean of absolute errors."""
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.1, 2.2, 2.7])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        expected_mae = np.mean(np.abs(y_true - y_pred))
        assert abs(result["mae"] - expected_mae) < 1e-6

    def test_r_squared_perfect_predictions(self):
        """R-squared should be 1.0 for perfect predictions."""
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert abs(result["r_squared"] - 1.0) < 1e-6

    def test_r_squared_mean_prediction(self):
        """R-squared should be 0.0 when predicting the mean."""
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        mean_val = np.mean(y_true)
        y_pred = np.full_like(y_true, mean_val)
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert abs(result["r_squared"] - 0.0) < 1e-6

    def test_r_squared_worse_than_mean(self):
        """R-squared should be negative for worse-than-mean predictions."""
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([10.0, -5.0, 20.0, -10.0])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert result["r_squared"] < 0.0

    def test_r_squared_constant_true_values(self):
        """R-squared should be 0.0 when SS_tot is 0 (constant true values)."""
        y_true = np.array([2.0, 2.0, 2.0, 2.0])
        y_pred = np.array([2.1, 1.9, 2.0, 2.2])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert result["r_squared"] == 0.0

    def test_directional_accuracy_all_correct(self):
        """Directional accuracy should be 1.0 when all signs match."""
        y_true = np.array([0.01, -0.02, 0.03, -0.01])
        y_pred = np.array([0.005, -0.01, 0.02, -0.005])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert abs(result["directional_accuracy"] - 1.0) < 1e-6

    def test_directional_accuracy_half_correct(self):
        """Directional accuracy should be 0.5 for half correct signs."""
        y_true = np.array([0.01, -0.02, 0.03, -0.01])
        y_pred = np.array([0.005, 0.01, 0.02, 0.005])  # 2 of 4 correct
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert abs(result["directional_accuracy"] - 0.5) < 1e-6

    def test_distribution_stats_included(self):
        """Result should include predicted return distribution stats."""
        y_true = np.array([0.01, -0.02, 0.03, -0.01])
        y_pred = np.array([0.005, -0.01, 0.02, -0.005])
        result = self.collector.collect_regression_metrics(y_true, y_pred)
        assert "mean_predicted_return" in result
        assert "std_predicted_return" in result
        assert abs(result["mean_predicted_return"] - np.mean(y_pred)) < 1e-6
        assert abs(result["std_predicted_return"] - float(np.std(y_pred))) < 1e-6

    def test_classification_metrics_unchanged(self):
        """collect_class_metrics should still work for classification."""
        y_true = torch.tensor([0, 1, 2, 0, 1])
        y_pred = torch.tensor([0, 1, 2, 1, 1])
        result = self.collector.collect_class_metrics(y_true, y_pred)
        assert "class_precisions" in result
        assert "BUY" in result["class_precisions"]
        assert "HOLD" in result["class_precisions"]
        assert "SELL" in result["class_precisions"]
