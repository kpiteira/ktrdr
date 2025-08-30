"""
Simple Tests for Results Analyzer

Basic tests to verify core functionality works.
"""


import pytest

from research_agents.services.results_analyzer import (
    AnalysisMetric,
    FitnessComponents,
    PerformanceMetrics,
    ResultsAnalyzer,
    RiskProfile,
    create_results_analyzer,
)


class TestBasicResultsAnalyzer:
    """Test basic results analyzer functionality"""

    def test_analyzer_creation(self):
        """Test creating analyzer instance"""
        analyzer = ResultsAnalyzer()

        # Check default weights
        assert analyzer.return_weight == 0.25
        assert analyzer.risk_weight == 0.25
        assert analyzer.consistency_weight == 0.20
        assert analyzer.efficiency_weight == 0.15
        assert analyzer.robustness_weight == 0.15

        # Check default thresholds
        assert analyzer.max_acceptable_drawdown == 0.20
        assert analyzer.min_sharpe_ratio == 0.5
        assert analyzer.target_annual_return == 0.15

    def test_analyzer_custom_config(self):
        """Test analyzer with custom configuration"""
        analyzer = ResultsAnalyzer(
            return_weight=0.4,
            risk_weight=0.3,
            max_acceptable_drawdown=0.1,
            target_annual_return=0.2,
        )

        assert analyzer.return_weight == 0.4
        assert analyzer.risk_weight == 0.3
        assert analyzer.max_acceptable_drawdown == 0.1
        assert analyzer.target_annual_return == 0.2

    def test_performance_metrics_creation(self):
        """Test creating performance metrics"""
        metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            volatility=0.12,
            sharpe_ratio=1.25,
            sortino_ratio=1.5,
            max_drawdown=-0.08,
            calmar_ratio=1.875,
            profit_factor=1.4,
            win_rate=0.6,
            total_trades=100,
            avg_trade_return=0.0015,
            var_95=-0.025,
            skewness=0.1,
            kurtosis=3.2,
            trade_frequency=1.2,
        )

        assert metrics.total_return == 0.15
        assert metrics.sharpe_ratio == 1.25
        assert metrics.total_trades == 100
        assert metrics.win_rate == 0.6

    def test_fitness_components_creation(self):
        """Test creating fitness components"""
        components = FitnessComponents(
            return_component=1.2,
            risk_component=1.1,
            consistency_component=0.9,
            trade_efficiency_component=1.0,
            robustness_component=0.8,
            penalty_component=1.0,
        )

        assert components.return_component == 1.2
        assert components.risk_component == 1.1
        assert components.penalty_component == 1.0

    def test_risk_profile_enum(self):
        """Test risk profile enum values"""
        assert RiskProfile.CONSERVATIVE == "conservative"
        assert RiskProfile.MODERATE == "moderate"
        assert RiskProfile.AGGRESSIVE == "aggressive"
        assert RiskProfile.SPECULATIVE == "speculative"

    def test_analysis_metric_enum(self):
        """Test analysis metric enum values"""
        assert AnalysisMetric.PROFIT_FACTOR == "profit_factor"
        assert AnalysisMetric.SHARPE_RATIO == "sharpe_ratio"
        assert AnalysisMetric.MAX_DRAWDOWN == "max_drawdown"

    @pytest.mark.asyncio
    async def test_calculate_skewness_basic(self):
        """Test basic skewness calculation"""
        analyzer = ResultsAnalyzer()

        # Symmetric data should have low skewness
        symmetric_returns = [-0.01, -0.005, 0.0, 0.005, 0.01] * 10
        skewness = await analyzer._calculate_skewness(symmetric_returns)

        assert isinstance(skewness, float)
        assert abs(skewness) < 0.5  # Should be relatively symmetric

    @pytest.mark.asyncio
    async def test_calculate_kurtosis_basic(self):
        """Test basic kurtosis calculation"""
        analyzer = ResultsAnalyzer()

        # Normal-ish data should have kurtosis around 3
        normal_returns = [0.001, -0.001, 0.002, -0.002, 0.0] * 20
        kurtosis = await analyzer._calculate_kurtosis(normal_returns)

        assert isinstance(kurtosis, float)
        assert 1.0 < kurtosis < 6.0  # Reasonable range

    @pytest.mark.asyncio
    async def test_calculate_var_95_basic(self):
        """Test basic VaR calculation"""
        analyzer = ResultsAnalyzer()

        # Create some returns data
        returns = [0.01, -0.02, 0.015, -0.005, 0.008, -0.012, 0.003] * 20
        var_95 = await analyzer._calculate_var_95({"daily_returns": returns})

        assert isinstance(var_95, float)
        assert var_95 < 0  # VaR should be negative

    @pytest.mark.asyncio
    async def test_overall_fitness_calculation(self):
        """Test overall fitness score calculation"""
        analyzer = ResultsAnalyzer()

        components = FitnessComponents(
            return_component=1.0,
            risk_component=1.0,
            consistency_component=1.0,
            trade_efficiency_component=1.0,
            robustness_component=1.0,
            penalty_component=1.0,
        )

        fitness = await analyzer._calculate_overall_fitness(components)

        assert isinstance(fitness, float)
        assert 0.0 <= fitness <= 5.0  # Should be bounded
        assert abs(fitness - 1.0) < 0.1  # Should be close to 1.0 for unit components

    @pytest.mark.asyncio
    async def test_classify_risk_profile_basic(self):
        """Test basic risk profile classification"""
        analyzer = ResultsAnalyzer()

        # Conservative metrics
        conservative_metrics = PerformanceMetrics(
            total_return=0.08,
            annualized_return=0.08,
            volatility=0.05,
            sharpe_ratio=1.6,
            sortino_ratio=1.8,
            max_drawdown=-0.02,
            calmar_ratio=4.0,
            profit_factor=1.3,
            win_rate=0.65,
            total_trades=100,
            avg_trade_return=0.0008,
            var_95=-0.01,
            skewness=0.0,
            kurtosis=3.0,
            trade_frequency=1.0,
        )

        profile = await analyzer._classify_risk_profile(conservative_metrics)
        assert isinstance(profile, RiskProfile)

    def test_factory_function(self):
        """Test factory function"""
        analyzer = create_results_analyzer()
        assert isinstance(analyzer, ResultsAnalyzer)

        # Test with custom config
        analyzer2 = create_results_analyzer(return_weight=0.5)
        assert analyzer2.return_weight == 0.5

    @pytest.mark.asyncio
    async def test_performance_metrics_calculation_basic(self):
        """Test basic performance metrics calculation"""
        analyzer = ResultsAnalyzer()

        training_results = {"training_id": "test-123", "epochs_completed": 100}

        backtesting_results = {
            "total_return": 0.15,
            "sharpe_ratio": 1.4,
            "max_drawdown": -0.08,
            "profit_factor": 1.25,
            "total_trades": 150,
            "profitable_trades": 90,
            "volatility": 0.12,
            "sortino_ratio": 1.6,
            "var_95": -0.025,
        }

        metrics = await analyzer._calculate_performance_metrics(
            training_results, backtesting_results
        )

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_return == 0.15
        assert metrics.sharpe_ratio == 1.4
        assert metrics.total_trades == 150
        assert metrics.win_rate == 0.6  # 90/150


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
