"""
Unit Tests for Results Analyzer and Fitness Scoring System

Tests the comprehensive performance analysis and fitness calculation system
following the implementation plan's quality-first approach.
"""

from datetime import datetime
from uuid import uuid4

import numpy as np
import pytest

from research_agents.services.results_analyzer import (
    AnalysisResult,
    FitnessComponents,
    PerformanceMetrics,
    ResultsAnalyzer,
    RiskProfile,
    create_results_analyzer,
)


@pytest.fixture
def analyzer_config():
    """Create analyzer configuration"""
    return {
        "return_weight": 0.25,
        "risk_weight": 0.25,
        "consistency_weight": 0.20,
        "efficiency_weight": 0.15,
        "robustness_weight": 0.15,
        "max_acceptable_drawdown": 0.15,
        "min_sharpe_ratio": 0.5,
        "min_profit_factor": 1.0,
        "min_trade_count": 50,
        "target_annual_return": 0.12,
        "risk_free_rate": 0.02,
    }


@pytest.fixture
def results_analyzer(analyzer_config):
    """Create results analyzer instance"""
    return ResultsAnalyzer(**analyzer_config)


@pytest.fixture
def sample_training_results():
    """Create sample training results"""
    return {
        "training_id": "train-123",
        "epochs_completed": 100,
        "final_loss": 0.0234,
        "validation_loss": 0.0198,
        "training_time_minutes": 45.2,
        "accuracy": 0.7234,
        "model_path": "/models/test_model.h5",
    }


@pytest.fixture
def sample_backtesting_results():
    """Create sample backtesting results"""
    return {
        "backtest_id": "backtest-456",
        "total_trades": 150,
        "profitable_trades": 90,
        "losing_trades": 60,
        "win_rate": 0.6,
        "total_return": 0.15,
        "profit_factor": 1.25,
        "sharpe_ratio": 1.4,
        "sortino_ratio": 1.8,
        "max_drawdown": -0.08,
        "avg_trade_return": 0.001,
        "volatility": 0.12,
        "var_95": -0.02,
        "max_consecutive_losses": 5,
        "daily_returns": [0.001, -0.002, 0.003, -0.001, 0.002] * 50,  # 250 days
        "trade_returns": [0.005, -0.003, 0.007, -0.002, 0.004] * 30,  # 150 trades
    }


@pytest.fixture
def excellent_backtesting_results():
    """Create excellent backtesting results for testing high fitness scores"""
    return {
        "total_trades": 200,
        "profitable_trades": 140,
        "losing_trades": 60,
        "win_rate": 0.7,
        "total_return": 0.25,
        "profit_factor": 2.5,
        "sharpe_ratio": 2.2,
        "sortino_ratio": 2.8,
        "max_drawdown": -0.04,
        "avg_trade_return": 0.00125,
        "volatility": 0.08,
        "var_95": -0.015,
        "max_consecutive_losses": 3,
        "daily_returns": [0.002] * 250,  # Consistent positive returns
        "trade_returns": [0.005] * 200,  # All positive trades
    }


@pytest.fixture
def poor_backtesting_results():
    """Create poor backtesting results for testing low fitness scores"""
    return {
        "total_trades": 30,  # Too few trades
        "profitable_trades": 10,
        "losing_trades": 20,
        "win_rate": 0.33,
        "total_return": -0.05,
        "profit_factor": 0.8,
        "sharpe_ratio": -0.2,
        "sortino_ratio": -0.3,
        "max_drawdown": -0.25,  # Excessive drawdown
        "avg_trade_return": -0.0017,
        "volatility": 0.35,  # High volatility
        "var_95": -0.08,
        "max_consecutive_losses": 8,
        "daily_returns": [-0.002] * 250,  # Consistent losses
        "trade_returns": [-0.005] * 30,  # All losing trades
    }


class TestResultsAnalyzerInitialization:
    """Test analyzer initialization and configuration"""

    def test_initialization_with_defaults(self):
        """Test analyzer initialization with default parameters"""
        analyzer = ResultsAnalyzer()

        # Verify default weights
        assert analyzer.return_weight == 0.25
        assert analyzer.risk_weight == 0.25
        assert analyzer.consistency_weight == 0.20
        assert analyzer.efficiency_weight == 0.15
        assert analyzer.robustness_weight == 0.15

        # Verify default thresholds
        assert analyzer.max_acceptable_drawdown == 0.20
        assert analyzer.min_sharpe_ratio == 0.5
        assert analyzer.min_profit_factor == 1.0
        assert analyzer.min_trade_count == 50
        assert analyzer.target_annual_return == 0.15
        assert analyzer.risk_free_rate == 0.02

    def test_initialization_with_custom_config(self, analyzer_config):
        """Test analyzer initialization with custom configuration"""
        analyzer = ResultsAnalyzer(**analyzer_config)

        # Verify custom configuration
        assert analyzer.max_acceptable_drawdown == 0.15
        assert analyzer.target_annual_return == 0.12
        assert analyzer.min_trade_count == 50

        # Verify weights sum to 1.0
        total_weight = (
            analyzer.return_weight
            + analyzer.risk_weight
            + analyzer.consistency_weight
            + analyzer.efficiency_weight
            + analyzer.robustness_weight
        )
        assert abs(total_weight - 1.0) < 0.01  # Allow small floating point errors


class TestPerformanceMetricsCalculation:
    """Test performance metrics calculation"""

    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_success(
        self, results_analyzer, sample_training_results, sample_backtesting_results
    ):
        """Test successful performance metrics calculation"""
        metrics = await results_analyzer._calculate_performance_metrics(
            sample_training_results, sample_backtesting_results
        )

        # Verify basic metrics
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return == 0.15
        assert metrics.sharpe_ratio == 1.4
        assert metrics.max_drawdown == -0.08
        assert metrics.profit_factor == 1.25
        assert metrics.total_trades == 150
        assert metrics.win_rate == 0.6
        assert metrics.volatility == 0.12

        # Verify calculated metrics
        assert metrics.avg_trade_return == 0.001
        assert metrics.annualized_return > 0  # Should be positive
        assert metrics.calmar_ratio > 0  # Should be positive
        assert abs(metrics.sortino_ratio - 1.8) < 0.1  # Should be close to input

    @pytest.mark.asyncio
    async def test_calculate_performance_metrics_with_missing_data(
        self, results_analyzer
    ):
        """Test performance metrics calculation with missing data"""
        training_results = {"training_id": "test"}
        backtesting_results = {
            "total_return": 0.1,
            "total_trades": 100,
            # Missing many fields
        }

        metrics = await results_analyzer._calculate_performance_metrics(
            training_results, backtesting_results
        )

        # Should handle missing data gracefully
        assert metrics.total_return == 0.1
        assert metrics.total_trades == 100
        assert metrics.sharpe_ratio == 0.0  # Default for missing
        assert metrics.profit_factor == 1.0  # Default for missing
        assert metrics.win_rate == 0.0  # Default for missing

    @pytest.mark.asyncio
    async def test_calculate_sortino_ratio(self, results_analyzer):
        """Test Sortino ratio calculation"""
        backtesting_results = {
            "daily_returns": [0.01, -0.02, 0.03, -0.01, 0.02, -0.005, 0.015]
        }

        sortino = await results_analyzer._calculate_sortino_ratio(backtesting_results)

        # Should calculate properly
        assert isinstance(sortino, float)
        assert sortino > 0  # Should be positive for this data

    @pytest.mark.asyncio
    async def test_calculate_sortino_ratio_no_downside(self, results_analyzer):
        """Test Sortino ratio with no downside returns"""
        backtesting_results = {
            "daily_returns": [0.01, 0.02, 0.03, 0.01, 0.02]  # All positive
        }

        sortino = await results_analyzer._calculate_sortino_ratio(backtesting_results)

        # Should return high ratio when no downside
        assert sortino == 10.0

    @pytest.mark.asyncio
    async def test_calculate_var_95(self, results_analyzer):
        """Test 95% Value at Risk calculation"""
        backtesting_results = {
            "daily_returns": list(np.random.normal(0.001, 0.02, 1000))  # 1000 returns
        }

        var_95 = await results_analyzer._calculate_var_95(backtesting_results)

        # Should be in reasonable range for normal distribution
        assert isinstance(var_95, float)
        assert var_95 < 0  # VaR should be negative
        assert var_95 > -0.1  # Should not be too extreme

    @pytest.mark.asyncio
    async def test_calculate_skewness_and_kurtosis(self, results_analyzer):
        """Test skewness and kurtosis calculations"""
        # Normal distribution returns
        normal_returns = [0.001, 0.002, 0.0, -0.001, 0.001, 0.0, 0.002] * 10

        skewness = await results_analyzer._calculate_skewness(normal_returns)
        kurtosis = await results_analyzer._calculate_kurtosis(normal_returns)

        # Should be reasonable values
        assert isinstance(skewness, float)
        assert isinstance(kurtosis, float)
        assert abs(skewness) < 2.0  # Reasonable skewness
        assert 1.0 < kurtosis < 6.0  # Reasonable kurtosis (broader range)

    @pytest.mark.asyncio
    async def test_skewness_kurtosis_insufficient_data(self, results_analyzer):
        """Test skewness and kurtosis with insufficient data"""
        few_returns = [0.001, 0.002]  # Too few for kurtosis

        skewness = await results_analyzer._calculate_skewness(few_returns)
        kurtosis = await results_analyzer._calculate_kurtosis(few_returns)

        # Should return defaults
        assert skewness == 0.0
        assert kurtosis == 3.0


class TestFitnessComponents:
    """Test individual fitness component calculations"""

    @pytest.mark.asyncio
    async def test_calculate_return_component(self, results_analyzer):
        """Test return component calculation"""
        # Good return metrics
        good_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            max_drawdown=-0.05,
            calmar_ratio=3.0,
            profit_factor=1.5,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.02,
            skewness=0.1,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        return_comp = await results_analyzer._calculate_return_component(good_metrics)

        # Should be close to 1.0 for target return
        assert 0.8 < return_comp < 1.5

    @pytest.mark.asyncio
    async def test_calculate_risk_component(self, results_analyzer):
        """Test risk component calculation"""
        # Low risk metrics
        low_risk_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.05,
            sharpe_ratio=2.0,
            sortino_ratio=2.2,
            max_drawdown=-0.03,
            calmar_ratio=5.0,
            profit_factor=1.5,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.01,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        risk_comp = await results_analyzer._calculate_risk_component(low_risk_metrics)

        # Should be high for low risk
        assert risk_comp > 0.5

    @pytest.mark.asyncio
    async def test_calculate_consistency_component(self, results_analyzer):
        """Test consistency component calculation"""
        # Consistent metrics
        consistent_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=-0.05,
            calmar_ratio=3.0,
            profit_factor=2.0,
            win_rate=0.7,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.02,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        consistency_comp = await results_analyzer._calculate_consistency_component(
            consistent_metrics
        )

        # Should be high for consistent performance
        assert consistency_comp > 0.8

    @pytest.mark.asyncio
    async def test_calculate_efficiency_component(self, results_analyzer):
        """Test efficiency component calculation"""
        # Efficient metrics
        efficient_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            max_drawdown=-0.05,
            calmar_ratio=3.0,
            profit_factor=1.5,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.002,
            var_95=-0.02,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=2.0,  # Good frequency
        )

        efficiency_comp = await results_analyzer._calculate_efficiency_component(
            efficient_metrics
        )

        # Should be reasonable for good efficiency
        assert efficiency_comp > 0.5

    @pytest.mark.asyncio
    async def test_calculate_robustness_component(self, results_analyzer):
        """Test robustness component calculation"""
        # Robust metrics
        robust_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            max_drawdown=-0.05,
            calmar_ratio=3.0,
            profit_factor=1.5,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.02,
            skewness=0.1,
            kurtosis=3.2,
            trade_frequency=1.0,
        )

        additional_data = {"out_of_sample_return": 0.12}  # Good out-of-sample

        robustness_comp = await results_analyzer._calculate_robustness_component(
            robust_metrics, additional_data
        )

        # Should be reasonable for robust metrics
        assert robustness_comp > 0.5

    @pytest.mark.asyncio
    async def test_calculate_penalty_component_good_metrics(self, results_analyzer):
        """Test penalty component with good metrics (no penalties)"""
        good_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.1,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            max_drawdown=-0.05,
            calmar_ratio=3.0,
            profit_factor=1.5,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.02,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        penalty_comp = await results_analyzer._calculate_penalty_component(good_metrics)

        # Should be close to 1.0 (no penalties)
        assert penalty_comp > 0.9

    @pytest.mark.asyncio
    async def test_calculate_penalty_component_poor_metrics(self, results_analyzer):
        """Test penalty component with poor metrics (heavy penalties)"""
        poor_metrics = PerformanceMetrics(
            total_return=-0.05,
            annualized_return=-0.05,
            volatility=0.4,
            sharpe_ratio=-0.2,
            sortino_ratio=-0.3,
            max_drawdown=-0.25,
            calmar_ratio=-0.2,
            profit_factor=0.8,
            win_rate=0.3,
            total_trades=20,
            avg_trade_return=-0.0025,
            var_95=-0.08,
            skewness=-1.0,
            kurtosis=5.0,
            trade_frequency=0.1,
        )

        penalty_comp = await results_analyzer._calculate_penalty_component(poor_metrics)

        # Should be heavily penalized
        assert penalty_comp < 0.5


class TestFitnessScoreCalculation:
    """Test overall fitness score calculation"""

    @pytest.mark.asyncio
    async def test_calculate_overall_fitness_excellent(self, results_analyzer):
        """Test fitness calculation for excellent strategy"""
        excellent_components = FitnessComponents(
            return_component=2.0,
            risk_component=1.8,
            consistency_component=1.5,
            trade_efficiency_component=1.3,
            robustness_component=1.2,
            penalty_component=1.0,
        )

        fitness = await results_analyzer._calculate_overall_fitness(
            excellent_components
        )

        # Should be high for excellent components
        assert fitness > 1.5
        assert fitness <= 5.0  # Cap at 5.0

    @pytest.mark.asyncio
    async def test_calculate_overall_fitness_poor(self, results_analyzer):
        """Test fitness calculation for poor strategy"""
        poor_components = FitnessComponents(
            return_component=0.2,
            risk_component=0.3,
            consistency_component=0.1,
            trade_efficiency_component=0.2,
            robustness_component=0.3,
            penalty_component=0.5,  # Heavy penalty
        )

        fitness = await results_analyzer._calculate_overall_fitness(poor_components)

        # Should be low for poor components
        assert fitness < 0.5
        assert fitness >= 0.0  # Floor at 0.0

    @pytest.mark.asyncio
    async def test_fitness_component_weights(self, results_analyzer):
        """Test that fitness components use correct weights"""
        # Create components where only one is high
        test_components = FitnessComponents(
            return_component=2.0,  # Only this is high
            risk_component=0.0,
            consistency_component=0.0,
            trade_efficiency_component=0.0,
            robustness_component=0.0,
            penalty_component=1.0,
        )

        fitness = await results_analyzer._calculate_overall_fitness(test_components)

        # Should be approximately return_weight * return_component
        expected = results_analyzer.return_weight * 2.0
        assert abs(fitness - expected) < 0.1


class TestRiskProfileClassification:
    """Test risk profile classification"""

    @pytest.mark.asyncio
    async def test_classify_conservative_profile(self, results_analyzer):
        """Test conservative risk profile classification"""
        conservative_metrics = PerformanceMetrics(
            total_return=0.08,
            annualized_return=0.08,
            volatility=0.03,
            sharpe_ratio=2.0,
            sortino_ratio=2.2,
            max_drawdown=-0.015,
            calmar_ratio=5.3,
            profit_factor=1.3,
            win_rate=0.65,
            total_trades=100,
            avg_trade_return=0.0008,
            var_95=-0.01,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        profile = await results_analyzer._classify_risk_profile(conservative_metrics)
        assert profile == RiskProfile.CONSERVATIVE

    @pytest.mark.asyncio
    async def test_classify_aggressive_profile(self, results_analyzer):
        """Test aggressive risk profile classification"""
        aggressive_metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            volatility=0.25,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            max_drawdown=-0.15,
            calmar_ratio=1.7,
            profit_factor=1.8,
            win_rate=0.55,
            total_trades=200,
            avg_trade_return=0.00125,
            var_95=-0.05,
            skewness=0.5,
            kurtosis=4.0,
            trade_frequency=2.0,
        )

        profile = await results_analyzer._classify_risk_profile(aggressive_metrics)
        assert profile == RiskProfile.AGGRESSIVE

    @pytest.mark.asyncio
    async def test_classify_speculative_profile(self, results_analyzer):
        """Test speculative risk profile classification"""
        speculative_metrics = PerformanceMetrics(
            total_return=0.5,
            annualized_return=0.5,
            volatility=0.4,
            sharpe_ratio=1.25,
            sortino_ratio=1.5,
            max_drawdown=-0.3,
            calmar_ratio=1.7,
            profit_factor=2.5,
            win_rate=0.5,
            total_trades=300,
            avg_trade_return=0.00167,
            var_95=-0.08,
            skewness=1.0,
            kurtosis=5.0,
            trade_frequency=3.0,
        )

        profile = await results_analyzer._classify_risk_profile(speculative_metrics)
        assert profile == RiskProfile.SPECULATIVE


class TestInsightsAndRecommendations:
    """Test insight and recommendation generation"""

    @pytest.mark.asyncio
    async def test_generate_insights_excellent_performance(self, results_analyzer):
        """Test insight generation for excellent performance"""
        excellent_metrics = PerformanceMetrics(
            total_return=0.25,
            annualized_return=0.25,
            volatility=0.1,
            sharpe_ratio=2.5,
            sortino_ratio=3.0,
            max_drawdown=-0.03,
            calmar_ratio=8.3,
            profit_factor=2.5,
            win_rate=0.7,
            total_trades=150,
            avg_trade_return=0.00167,
            var_95=-0.015,
            skewness=0.1,
            kurtosis=3.0,
            trade_frequency=1.5,
        )

        excellent_components = FitnessComponents(
            return_component=2.0,
            risk_component=1.8,
            consistency_component=1.5,
            trade_efficiency_component=1.3,
            robustness_component=1.2,
            penalty_component=1.0,
        )

        insights = await results_analyzer._generate_insights(
            excellent_metrics, excellent_components
        )

        # Should generate positive insights
        assert len(insights) > 0
        assert any(
            "Excellent" in insight or "High" in insight or "Strong" in insight
            for insight in insights
        )

    @pytest.mark.asyncio
    async def test_generate_warnings_poor_performance(self, results_analyzer):
        """Test warning generation for poor performance"""
        poor_metrics = PerformanceMetrics(
            total_return=-0.05,
            annualized_return=-0.05,
            volatility=0.35,
            sharpe_ratio=-0.14,
            sortino_ratio=-0.2,
            max_drawdown=-0.25,
            calmar_ratio=-0.2,
            profit_factor=0.8,
            win_rate=0.3,
            total_trades=25,
            avg_trade_return=-0.002,
            var_95=-0.08,
            skewness=-1.0,
            kurtosis=5.0,
            trade_frequency=0.2,
        )

        warnings = await results_analyzer._generate_warnings(poor_metrics)

        # Should generate multiple warnings
        assert len(warnings) > 3
        assert any("drawdown" in warning.lower() for warning in warnings)
        assert any("sharpe" in warning.lower() for warning in warnings)
        assert any("trade count" in warning.lower() for warning in warnings)

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, results_analyzer):
        """Test recommendation generation"""
        mediocre_metrics = PerformanceMetrics(
            total_return=0.08,
            annualized_return=0.08,
            volatility=0.15,
            sharpe_ratio=0.53,
            sortino_ratio=0.6,
            max_drawdown=-0.12,
            calmar_ratio=0.67,
            profit_factor=1.1,
            win_rate=0.45,
            total_trades=75,
            avg_trade_return=0.00107,
            var_95=-0.03,
            skewness=0.2,
            kurtosis=3.5,
            trade_frequency=0.8,
        )

        recommendations = await results_analyzer._generate_recommendations(
            mediocre_metrics, RiskProfile.MODERATE
        )

        # Should generate actionable recommendations
        assert len(recommendations) > 0
        assert any(
            "improve" in rec.lower() or "consider" in rec.lower()
            for rec in recommendations
        )


class TestCompleteAnalysisWorkflow:
    """Test complete analysis workflow"""

    @pytest.mark.asyncio
    async def test_analyze_experiment_results_complete(
        self, results_analyzer, sample_training_results, sample_backtesting_results
    ):
        """Test complete experiment analysis workflow"""
        experiment_id = uuid4()

        result = await results_analyzer.analyze_experiment_results(
            experiment_id, sample_training_results, sample_backtesting_results
        )

        # Verify complete result structure
        assert isinstance(result, AnalysisResult)
        assert result.experiment_id == experiment_id
        assert isinstance(result.fitness_score, float)
        assert result.fitness_score >= 0.0

        # Verify components
        assert isinstance(result.fitness_components, FitnessComponents)
        assert isinstance(result.performance_metrics, PerformanceMetrics)
        assert isinstance(result.risk_profile, RiskProfile)

        # Verify insights and recommendations
        assert isinstance(result.insights, list)
        assert isinstance(result.warnings, list)
        assert isinstance(result.recommendations, list)
        assert isinstance(result.analysis_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_analyze_experiment_results_excellent(
        self, results_analyzer, sample_training_results, excellent_backtesting_results
    ):
        """Test analysis of excellent results"""
        experiment_id = uuid4()

        result = await results_analyzer.analyze_experiment_results(
            experiment_id, sample_training_results, excellent_backtesting_results
        )

        # Should produce high fitness score (adjusted for realistic expectations)
        assert result.fitness_score > 1.0  # Good but not perfect score
        assert result.risk_profile in [RiskProfile.CONSERVATIVE, RiskProfile.MODERATE]
        assert len(result.insights) > 0
        assert len(result.warnings) == 0  # Should have no warnings

    @pytest.mark.asyncio
    async def test_analyze_experiment_results_poor(
        self, results_analyzer, sample_training_results, poor_backtesting_results
    ):
        """Test analysis of poor results"""
        experiment_id = uuid4()

        result = await results_analyzer.analyze_experiment_results(
            experiment_id, sample_training_results, poor_backtesting_results
        )

        # Should produce low fitness score
        assert result.fitness_score < 1.0
        assert result.risk_profile == RiskProfile.SPECULATIVE
        assert len(result.warnings) > 0
        assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_analyze_experiment_results_with_additional_data(
        self, results_analyzer, sample_training_results, sample_backtesting_results
    ):
        """Test analysis with additional out-of-sample data"""
        experiment_id = uuid4()
        additional_data = {
            "out_of_sample_return": 0.12,
            "walk_forward_results": {"avg_return": 0.10},
        }

        result = await results_analyzer.analyze_experiment_results(
            experiment_id,
            sample_training_results,
            sample_backtesting_results,
            additional_data,
        )

        # Should incorporate additional data in robustness component
        assert result.fitness_components.robustness_component > 0.5


class TestStrategyComparison:
    """Test strategy comparison functionality"""

    @pytest.mark.asyncio
    async def test_compare_strategies_multiple_results(
        self, results_analyzer, sample_training_results
    ):
        """Test comparison of multiple strategy results"""
        # Create multiple analysis results
        results = []

        for _i, (return_val, sharpe) in enumerate(
            [(0.15, 1.4), (0.20, 1.8), (0.10, 1.0)]
        ):
            backtest_results = {
                "total_return": return_val,
                "sharpe_ratio": sharpe,
                "total_trades": 100,
                "profitable_trades": 60,
                "max_drawdown": -0.05,
                "profit_factor": 1.2,
                "volatility": 0.1,
                "var_95": -0.02,
                "daily_returns": [0.001] * 250,
                "trade_returns": [0.001] * 100,
            }

            result = await results_analyzer.analyze_experiment_results(
                uuid4(), sample_training_results, backtest_results
            )
            results.append(result)

        comparison = await results_analyzer.compare_strategies(results)

        # Verify comparison structure
        assert comparison["total_strategies"] == 3
        assert "best_strategy" in comparison
        assert "statistics" in comparison
        assert "risk_profile_distribution" in comparison
        assert "top_performers" in comparison

        # Verify best strategy identification
        best_strategy = comparison["best_strategy"]
        assert (
            best_strategy["total_return"] == 0.20
        )  # Should be highest return strategy
        assert best_strategy["sharpe_ratio"] == 1.8

        # Verify statistics
        stats = comparison["statistics"]
        assert stats["avg_return"] == 0.15  # Average of 0.15, 0.20, 0.10
        assert stats["success_rate"] >= 0.0  # Should be calculated

        # Verify top performers
        assert len(comparison["top_performers"]) == 3
        assert comparison["top_performers"][0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_compare_strategies_empty_list(self, results_analyzer):
        """Test strategy comparison with empty results list"""
        comparison = await results_analyzer.compare_strategies([])

        # Should return empty comparison
        assert comparison == {}

    @pytest.mark.asyncio
    async def test_compare_strategies_single_result(
        self, results_analyzer, sample_training_results, sample_backtesting_results
    ):
        """Test strategy comparison with single result"""
        result = await results_analyzer.analyze_experiment_results(
            uuid4(), sample_training_results, sample_backtesting_results
        )

        comparison = await results_analyzer.compare_strategies([result])

        # Should handle single result
        assert comparison["total_strategies"] == 1
        assert comparison["best_strategy"]["experiment_id"] == str(result.experiment_id)
        assert len(comparison["top_performers"]) == 1


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_analyze_experiment_results_error_handling(self, results_analyzer):
        """Test error handling in analysis"""
        experiment_id = uuid4()

        # Invalid training results
        invalid_training = None
        invalid_backtesting = {"total_return": "invalid"}  # Wrong type

        with pytest.raises(Exception):
            await results_analyzer.analyze_experiment_results(
                experiment_id, invalid_training, invalid_backtesting
            )

    @pytest.mark.asyncio
    async def test_performance_metrics_zero_division(self, results_analyzer):
        """Test handling of zero division in metrics calculation"""
        training_results = {"training_id": "test"}
        backtesting_results = {
            "total_trades": 0,  # Zero trades
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
        }

        metrics = await results_analyzer._calculate_performance_metrics(
            training_results, backtesting_results
        )

        # Should handle zero division gracefully
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.avg_trade_return == 0.0
        assert metrics.calmar_ratio == 0.0  # When max_drawdown is 0

    @pytest.mark.asyncio
    async def test_fitness_calculation_extreme_values(self, results_analyzer):
        """Test fitness calculation with extreme values"""
        extreme_components = FitnessComponents(
            return_component=10.0,  # Extreme high
            risk_component=-5.0,  # Extreme low (negative)
            consistency_component=100.0,  # Extreme high
            trade_efficiency_component=0.0,
            robustness_component=0.0,
            penalty_component=0.01,  # Heavy penalty
        )

        fitness = await results_analyzer._calculate_overall_fitness(extreme_components)

        # Should be bounded between 0 and 5
        assert 0.0 <= fitness <= 5.0

    @pytest.mark.asyncio
    async def test_missing_optional_data_fields(
        self, results_analyzer, sample_training_results
    ):
        """Test handling of missing optional data fields"""
        minimal_backtesting = {
            "total_return": 0.1,
            "total_trades": 50,
            # Missing most optional fields
        }

        result = await results_analyzer.analyze_experiment_results(
            uuid4(), sample_training_results, minimal_backtesting
        )

        # Should complete analysis with defaults
        assert isinstance(result, AnalysisResult)
        assert result.fitness_score >= 0.0
        assert isinstance(result.performance_metrics, PerformanceMetrics)


class TestAdvancedMetrics:
    """Test advanced metric calculations"""

    @pytest.mark.asyncio
    async def test_skewness_calculation_edge_cases(self, results_analyzer):
        """Test skewness calculation with edge cases"""
        # Perfectly symmetric returns
        symmetric_returns = [-0.01, -0.005, 0.0, 0.005, 0.01] * 20
        skewness = await results_analyzer._calculate_skewness(symmetric_returns)
        assert abs(skewness) < 0.1  # Should be close to 0

        # Highly skewed returns
        skewed_returns = [0.01] * 90 + [-0.1] * 10  # Negative skew
        skewness = await results_analyzer._calculate_skewness(skewed_returns)
        assert skewness < -0.5  # Should be negative

    @pytest.mark.asyncio
    async def test_kurtosis_calculation_distributions(self, results_analyzer):
        """Test kurtosis calculation for different distributions"""
        # Normal-like distribution
        normal_returns = list(np.random.normal(0, 0.01, 1000))
        kurtosis = await results_analyzer._calculate_kurtosis(normal_returns)
        assert 2.5 < kurtosis < 3.5  # Should be close to 3 for normal

        # Fat-tailed distribution
        fat_tail_returns = (
            [0.0] * 900
            + [0.05, -0.05] * 25  # Fat tails
            + list(np.random.normal(0, 0.005, 50))
        )
        kurtosis = await results_analyzer._calculate_kurtosis(fat_tail_returns)
        assert kurtosis > 3.5  # Should be higher than normal


class TestConfigurationAndCustomization:
    """Test configuration and customization options"""

    def test_custom_weights_configuration(self):
        """Test analyzer with custom weight configuration"""
        custom_config = {
            "return_weight": 0.4,
            "risk_weight": 0.3,
            "consistency_weight": 0.2,
            "efficiency_weight": 0.05,
            "robustness_weight": 0.05,
        }

        analyzer = ResultsAnalyzer(**custom_config)

        # Verify custom weights
        assert analyzer.return_weight == 0.4
        assert analyzer.risk_weight == 0.3
        assert analyzer.consistency_weight == 0.2

        # Verify they sum to 1.0
        total = (
            analyzer.return_weight
            + analyzer.risk_weight
            + analyzer.consistency_weight
            + analyzer.efficiency_weight
            + analyzer.robustness_weight
        )
        assert abs(total - 1.0) < 0.01

    def test_custom_threshold_configuration(self):
        """Test analyzer with custom threshold configuration"""
        custom_config = {
            "max_acceptable_drawdown": 0.10,
            "min_sharpe_ratio": 1.0,
            "min_profit_factor": 1.5,
            "target_annual_return": 0.20,
        }

        analyzer = ResultsAnalyzer(**custom_config)

        # Verify custom thresholds
        assert analyzer.max_acceptable_drawdown == 0.10
        assert analyzer.min_sharpe_ratio == 1.0
        assert analyzer.min_profit_factor == 1.5
        assert analyzer.target_annual_return == 0.20

    @pytest.mark.asyncio
    async def test_threshold_impact_on_penalties(self):
        """Test that custom thresholds impact penalty calculations"""
        strict_analyzer = ResultsAnalyzer(
            max_acceptable_drawdown=0.05,  # Very strict
            min_sharpe_ratio=2.0,  # Very high
        )

        lenient_analyzer = ResultsAnalyzer(
            max_acceptable_drawdown=0.30,  # Very lenient
            min_sharpe_ratio=0.1,  # Very low
        )

        # Same mediocre metrics
        mediocre_metrics = PerformanceMetrics(
            total_return=0.1,
            annualized_return=0.1,
            volatility=0.15,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            max_drawdown=-0.10,
            calmar_ratio=1.0,
            profit_factor=1.2,
            win_rate=0.5,
            total_trades=100,
            avg_trade_return=0.001,
            var_95=-0.02,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        strict_penalty = await strict_analyzer._calculate_penalty_component(
            mediocre_metrics
        )
        lenient_penalty = await lenient_analyzer._calculate_penalty_component(
            mediocre_metrics
        )

        # Strict analyzer should penalize more
        assert strict_penalty < lenient_penalty


class TestFactoryFunction:
    """Test factory function"""

    def test_create_results_analyzer_defaults(self):
        """Test factory function with defaults"""
        analyzer = create_results_analyzer()

        assert isinstance(analyzer, ResultsAnalyzer)
        assert analyzer.return_weight == 0.25  # Default

    def test_create_results_analyzer_custom(self):
        """Test factory function with custom config"""
        analyzer = create_results_analyzer(return_weight=0.5, target_annual_return=0.25)

        assert isinstance(analyzer, ResultsAnalyzer)
        assert analyzer.return_weight == 0.5
        assert analyzer.target_annual_return == 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
