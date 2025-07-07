"""
Results Analysis and Fitness Scoring System

This module provides comprehensive analysis of experiment results and 
calculates fitness scores for trading strategies, enabling the research
system to evaluate and compare different approaches.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from enum import Enum
from dataclasses import dataclass
import statistics

import numpy as np
from ktrdr import get_logger

logger = get_logger(__name__)


class AnalysisMetric(str, Enum):
    """Available analysis metrics"""
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    TOTAL_RETURN = "total_return"
    VOLATILITY = "volatility"
    CALMAR_RATIO = "calmar_ratio"
    VAR_95 = "var_95"
    TRADE_FREQUENCY = "trade_frequency"


class RiskProfile(str, Enum):
    """Risk profile classifications"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    SPECULATIVE = "speculative"


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float
    profit_factor: float
    win_rate: float
    total_trades: int
    avg_trade_return: float
    var_95: float
    skewness: float
    kurtosis: float
    trade_frequency: float  # trades per day


@dataclass
class FitnessComponents:
    """Individual components of fitness score"""
    return_component: float
    risk_component: float
    consistency_component: float
    trade_efficiency_component: float
    robustness_component: float
    penalty_component: float


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    experiment_id: UUID
    fitness_score: float
    fitness_components: FitnessComponents
    performance_metrics: PerformanceMetrics
    risk_profile: RiskProfile
    insights: List[str]
    warnings: List[str]
    recommendations: List[str]
    analysis_timestamp: datetime


class ResultsAnalyzer:
    """
    Advanced results analysis and fitness scoring system
    
    Evaluates trading strategy performance using multiple metrics
    and calculates comprehensive fitness scores for optimization.
    """
    
    def __init__(self, **config):
        # Fitness calculation weights
        self.return_weight = config.get("return_weight", 0.25)
        self.risk_weight = config.get("risk_weight", 0.25)
        self.consistency_weight = config.get("consistency_weight", 0.20)
        self.efficiency_weight = config.get("efficiency_weight", 0.15)
        self.robustness_weight = config.get("robustness_weight", 0.15)
        
        # Risk tolerance parameters
        self.max_acceptable_drawdown = config.get("max_acceptable_drawdown", 0.20)
        self.min_sharpe_ratio = config.get("min_sharpe_ratio", 0.5)
        self.min_profit_factor = config.get("min_profit_factor", 1.0)
        self.min_trade_count = config.get("min_trade_count", 50)
        
        # Target benchmarks
        self.target_annual_return = config.get("target_annual_return", 0.15)
        self.risk_free_rate = config.get("risk_free_rate", 0.02)
        
        logger.info(f"Results analyzer initialized with weights: return={self.return_weight}, risk={self.risk_weight}, consistency={self.consistency_weight}, efficiency={self.efficiency_weight}, robustness={self.robustness_weight}")
    
    async def analyze_experiment_results(
        self,
        experiment_id: UUID,
        training_results: Dict[str, Any],
        backtesting_results: Dict[str, Any],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """
        Perform comprehensive analysis of experiment results
        """
        try:
            logger.info(f"Starting experiment analysis for experiment_id: {experiment_id}")
            
            # Extract performance data
            performance_metrics = await self._calculate_performance_metrics(
                training_results, backtesting_results
            )
            
            # Calculate fitness components
            fitness_components = await self._calculate_fitness_components(
                performance_metrics, additional_data or {}
            )
            
            # Calculate overall fitness score
            fitness_score = await self._calculate_overall_fitness(fitness_components)
            
            # Classify risk profile
            risk_profile = await self._classify_risk_profile(performance_metrics)
            
            # Generate insights and recommendations
            insights = await self._generate_insights(performance_metrics, fitness_components)
            warnings = await self._generate_warnings(performance_metrics)
            recommendations = await self._generate_recommendations(performance_metrics, risk_profile)
            
            result = AnalysisResult(
                experiment_id=experiment_id,
                fitness_score=fitness_score,
                fitness_components=fitness_components,
                performance_metrics=performance_metrics,
                risk_profile=risk_profile,
                insights=insights,
                warnings=warnings,
                recommendations=recommendations,
                analysis_timestamp=datetime.now(timezone.utc)
            )
            
            logger.info(f"Experiment analysis completed for experiment_id: {experiment_id}, fitness_score: {fitness_score}, risk_profile: {risk_profile.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"Experiment analysis failed for experiment_id: {experiment_id}, error: {e}")
            raise
    
    async def _calculate_performance_metrics(
        self,
        training_results: Dict[str, Any],
        backtesting_results: Dict[str, Any]
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        
        # Extract basic metrics from backtesting results
        total_return = backtesting_results.get("total_return", 0.0)
        sharpe_ratio = backtesting_results.get("sharpe_ratio", 0.0)
        max_drawdown = backtesting_results.get("max_drawdown", 0.0)
        profit_factor = backtesting_results.get("profit_factor", 1.0)
        total_trades = backtesting_results.get("total_trades", 0)
        profitable_trades = backtesting_results.get("profitable_trades", 0)
        volatility = backtesting_results.get("volatility", 0.0)
        
        # Calculate derived metrics
        win_rate = profitable_trades / total_trades if total_trades > 0 else 0.0
        avg_trade_return = total_return / total_trades if total_trades > 0 else 0.0
        
        # Estimate annualized return (assuming backtesting period)
        backtest_days = 252  # Default trading days per year
        annualized_return = total_return * (252 / backtest_days) if backtest_days > 0 else total_return
        
        # Calculate advanced metrics
        # Use provided Sortino ratio if available, otherwise calculate it
        provided_sortino = backtesting_results.get("sortino_ratio")
        if provided_sortino is not None:
            sortino_ratio = provided_sortino
        else:
            sortino_ratio = await self._calculate_sortino_ratio(backtesting_results)
        
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        var_95 = await self._calculate_var_95(backtesting_results)
        
        # Trading statistics
        trade_frequency = total_trades / (backtest_days / 252) if backtest_days > 0 else 0.0
        
        # Calculate distribution statistics if trade data available
        skewness = 0.0
        kurtosis = 0.0
        trade_returns = backtesting_results.get("trade_returns", [])
        if trade_returns and len(trade_returns) > 2:
            skewness = await self._calculate_skewness(trade_returns)
            kurtosis = await self._calculate_kurtosis(trade_returns)
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            profit_factor=profit_factor,
            win_rate=win_rate,
            total_trades=total_trades,
            avg_trade_return=avg_trade_return,
            var_95=var_95,
            skewness=skewness,
            kurtosis=kurtosis,
            trade_frequency=trade_frequency
        )
    
    async def _calculate_fitness_components(
        self,
        metrics: PerformanceMetrics,
        additional_data: Dict[str, Any]
    ) -> FitnessComponents:
        """Calculate individual fitness components"""
        
        # Return Component (0-1 scale)
        return_component = await self._calculate_return_component(metrics)
        
        # Risk Component (0-1 scale, higher is better)
        risk_component = await self._calculate_risk_component(metrics)
        
        # Consistency Component (0-1 scale)
        consistency_component = await self._calculate_consistency_component(metrics)
        
        # Trade Efficiency Component (0-1 scale)
        efficiency_component = await self._calculate_efficiency_component(metrics)
        
        # Robustness Component (0-1 scale)
        robustness_component = await self._calculate_robustness_component(metrics, additional_data)
        
        # Penalty Component (0-1 scale, penalties reduce this)
        penalty_component = await self._calculate_penalty_component(metrics)
        
        return FitnessComponents(
            return_component=return_component,
            risk_component=risk_component,
            consistency_component=consistency_component,
            trade_efficiency_component=efficiency_component,
            robustness_component=robustness_component,
            penalty_component=penalty_component
        )
    
    async def _calculate_overall_fitness(self, components: FitnessComponents) -> float:
        """Calculate weighted overall fitness score"""
        
        # Weighted sum of components
        fitness = (
            components.return_component * self.return_weight +
            components.risk_component * self.risk_weight +
            components.consistency_component * self.consistency_weight +
            components.trade_efficiency_component * self.efficiency_weight +
            components.robustness_component * self.robustness_weight
        )
        
        # Apply penalties
        fitness *= components.penalty_component
        
        # Ensure fitness is between 0 and 5 (allowing for exceptional strategies)
        fitness = max(0.0, min(5.0, fitness))
        
        return fitness
    
    async def _calculate_return_component(self, metrics: PerformanceMetrics) -> float:
        """Calculate return-based fitness component"""
        # Normalize annual return relative to target
        return_score = metrics.annualized_return / self.target_annual_return
        
        # Apply diminishing returns for very high returns
        if return_score > 2.0:
            return_score = 2.0 + np.log(return_score - 1.0)
        
        return max(0.0, min(3.0, return_score))
    
    async def _calculate_risk_component(self, metrics: PerformanceMetrics) -> float:
        """Calculate risk-adjusted fitness component"""
        # Sharpe ratio component (primary risk-adjusted metric)
        sharpe_score = metrics.sharpe_ratio / 2.0  # Normalize assuming good Sharpe > 2
        
        # Drawdown component (penalty for large drawdowns)
        dd_score = 1.0 - (abs(metrics.max_drawdown) / self.max_acceptable_drawdown)
        dd_score = max(0.0, dd_score)
        
        # Volatility component (moderate volatility preferred)
        vol_score = 1.0 / (1.0 + metrics.volatility)  # Lower volatility is better
        
        # Combined risk score
        risk_score = (sharpe_score * 0.5 + dd_score * 0.3 + vol_score * 0.2)
        
        return max(0.0, min(2.0, risk_score))
    
    async def _calculate_consistency_component(self, metrics: PerformanceMetrics) -> float:
        """Calculate consistency-based fitness component"""
        # Win rate component
        win_rate_score = metrics.win_rate * 2.0  # Scale to 0-2 range
        
        # Profit factor component
        pf_score = min(metrics.profit_factor / 2.0, 2.0)  # Cap at 2.0
        
        # Sortino ratio component (downside risk focus)
        sortino_score = metrics.sortino_ratio / 3.0  # Normalize
        
        # Combined consistency score
        consistency_score = (win_rate_score * 0.4 + pf_score * 0.4 + sortino_score * 0.2)
        
        return max(0.0, min(2.0, consistency_score))
    
    async def _calculate_efficiency_component(self, metrics: PerformanceMetrics) -> float:
        """Calculate trade efficiency component"""
        # Trade frequency component (moderate frequency preferred)
        if metrics.trade_frequency < 0.1:  # Too few trades
            freq_score = metrics.trade_frequency * 10
        elif metrics.trade_frequency > 10:  # Too many trades
            freq_score = 1.0 / (metrics.trade_frequency / 10)
        else:
            freq_score = 1.0
        
        # Average trade return component
        avg_trade_score = min(abs(metrics.avg_trade_return) * 100, 2.0)
        
        # Trade count adequacy
        trade_count_score = min(metrics.total_trades / self.min_trade_count, 1.0)
        
        # Combined efficiency score
        efficiency_score = (freq_score * 0.4 + avg_trade_score * 0.3 + trade_count_score * 0.3)
        
        return max(0.0, min(2.0, efficiency_score))
    
    async def _calculate_robustness_component(
        self,
        metrics: PerformanceMetrics,
        additional_data: Dict[str, Any]
    ) -> float:
        """Calculate robustness component"""
        # Distribution characteristics
        skew_score = 1.0 / (1.0 + abs(metrics.skewness))  # Prefer low skewness
        kurtosis_score = 1.0 / (1.0 + abs(metrics.kurtosis - 3.0))  # Prefer normal kurtosis
        
        # VAR component
        var_score = 1.0 / (1.0 + abs(metrics.var_95))
        
        # Out-of-sample performance (if available)
        oos_score = 1.0
        if "out_of_sample_return" in additional_data:
            oos_return = additional_data["out_of_sample_return"]
            in_sample_return = metrics.total_return
            if in_sample_return != 0:
                oos_ratio = oos_return / in_sample_return
                oos_score = min(oos_ratio, 2.0) if oos_ratio > 0 else 0.0
        
        # Combined robustness score
        robustness_score = (skew_score * 0.25 + kurtosis_score * 0.25 + 
                           var_score * 0.25 + oos_score * 0.25)
        
        return max(0.0, min(2.0, robustness_score))
    
    async def _calculate_penalty_component(self, metrics: PerformanceMetrics) -> float:
        """Calculate penalty multiplier (1.0 = no penalty, <1.0 = penalty)"""
        penalty_multiplier = 1.0
        
        # Severe drawdown penalty
        if abs(metrics.max_drawdown) > self.max_acceptable_drawdown:
            penalty_multiplier *= 0.5
        
        # Low Sharpe ratio penalty
        if metrics.sharpe_ratio < self.min_sharpe_ratio:
            penalty_multiplier *= 0.7
        
        # Poor profit factor penalty
        if metrics.profit_factor < self.min_profit_factor:
            penalty_multiplier *= 0.8
        
        # Insufficient trades penalty
        if metrics.total_trades < self.min_trade_count:
            penalty_multiplier *= 0.6
        
        # Extreme volatility penalty
        if metrics.volatility > 0.5:  # >50% volatility
            penalty_multiplier *= 0.7
        
        return max(0.1, penalty_multiplier)  # Minimum 10% of original score
    
    async def _classify_risk_profile(self, metrics: PerformanceMetrics) -> RiskProfile:
        """Classify strategy risk profile"""
        # Calculate risk score based on multiple factors
        vol_score = metrics.volatility
        dd_score = abs(metrics.max_drawdown)
        sharpe_score = metrics.sharpe_ratio
        
        # Weighted risk assessment
        risk_score = vol_score * 0.4 + dd_score * 0.4 + (1.0 / max(sharpe_score, 0.1)) * 0.2
        
        if risk_score < 0.15:
            return RiskProfile.CONSERVATIVE
        elif risk_score < 0.25:
            return RiskProfile.MODERATE
        elif risk_score < 0.4:
            return RiskProfile.AGGRESSIVE
        else:
            return RiskProfile.SPECULATIVE
    
    async def _generate_insights(
        self,
        metrics: PerformanceMetrics,
        components: FitnessComponents
    ) -> List[str]:
        """Generate analytical insights"""
        insights = []
        
        # Performance insights
        if metrics.sharpe_ratio > 2.0:
            insights.append("Excellent risk-adjusted returns with high Sharpe ratio")
        elif metrics.sharpe_ratio > 1.0:
            insights.append("Good risk-adjusted returns")
        
        if metrics.max_drawdown < -0.05:
            insights.append("Low drawdown strategy with good capital preservation")
        
        if metrics.win_rate > 0.6:
            insights.append("High win rate indicates consistent profitability")
        
        if metrics.profit_factor > 2.0:
            insights.append("Strong profit factor shows good trade selection")
        
        # Component-specific insights
        if components.return_component > 1.5:
            insights.append("Strong return generation capability")
        
        if components.risk_component > 1.0:
            insights.append("Well-balanced risk management")
        
        if components.consistency_component > 1.0:
            insights.append("Consistent performance across different metrics")
        
        return insights
    
    async def _generate_warnings(self, metrics: PerformanceMetrics) -> List[str]:
        """Generate performance warnings"""
        warnings = []
        
        if abs(metrics.max_drawdown) > self.max_acceptable_drawdown:
            warnings.append(f"Maximum drawdown ({metrics.max_drawdown:.1%}) exceeds acceptable threshold")
        
        if metrics.sharpe_ratio < self.min_sharpe_ratio:
            warnings.append(f"Low Sharpe ratio ({metrics.sharpe_ratio:.2f}) indicates poor risk-adjusted returns")
        
        if metrics.total_trades < self.min_trade_count:
            warnings.append(f"Insufficient trade count ({metrics.total_trades}) for statistical significance")
        
        if metrics.profit_factor < self.min_profit_factor:
            warnings.append(f"Profit factor ({metrics.profit_factor:.2f}) below minimum threshold")
        
        if metrics.volatility > 0.4:
            warnings.append(f"High volatility ({metrics.volatility:.1%}) may indicate unstable strategy")
        
        return warnings
    
    async def _generate_recommendations(
        self,
        metrics: PerformanceMetrics,
        risk_profile: RiskProfile
    ) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        if metrics.sharpe_ratio < 1.0:
            recommendations.append("Consider improving risk management to enhance Sharpe ratio")
        
        if abs(metrics.max_drawdown) > 0.15:
            recommendations.append("Implement position sizing or stop-loss mechanisms to reduce drawdown")
        
        if metrics.win_rate < 0.4:
            recommendations.append("Review entry/exit criteria to improve win rate")
        
        if metrics.total_trades < 100:
            recommendations.append("Increase sample size by extending backtesting period")
        
        if risk_profile == RiskProfile.SPECULATIVE:
            recommendations.append("Consider risk reduction measures for better long-term sustainability")
        
        return recommendations
    
    # Helper calculation methods
    
    async def _calculate_sortino_ratio(self, backtesting_results: Dict[str, Any]) -> float:
        """Calculate Sortino ratio from backtesting results"""
        returns = backtesting_results.get("daily_returns", [])
        if not returns:
            return 0.0
        
        excess_returns = [r - self.risk_free_rate/252 for r in returns]
        downside_returns = [r for r in excess_returns if r < 0]
        
        if not downside_returns:
            return 10.0  # Very high ratio if no downside
        
        downside_deviation = np.std(downside_returns) * np.sqrt(252)
        mean_excess_return = np.mean(excess_returns) * 252
        
        return mean_excess_return / downside_deviation if downside_deviation > 0 else 0.0
    
    async def _calculate_var_95(self, backtesting_results: Dict[str, Any]) -> float:
        """Calculate 95% Value at Risk"""
        returns = backtesting_results.get("daily_returns", [])
        if not returns:
            return 0.0
        
        return np.percentile(returns, 5)  # 5th percentile for 95% VaR
    
    async def _calculate_skewness(self, returns: List[float]) -> float:
        """Calculate skewness of returns"""
        if len(returns) < 3:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        skew = np.mean([((r - mean_return) / std_return) ** 3 for r in returns])
        return skew
    
    async def _calculate_kurtosis(self, returns: List[float]) -> float:
        """Calculate kurtosis of returns"""
        if len(returns) < 4:
            return 3.0  # Normal distribution kurtosis
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 3.0
        
        kurt = np.mean([((r - mean_return) / std_return) ** 4 for r in returns])
        return kurt
    
    async def compare_strategies(
        self,
        results: List[AnalysisResult]
    ) -> Dict[str, Any]:
        """Compare multiple strategy results"""
        if not results:
            return {}
        
        # Sort by fitness score
        sorted_results = sorted(results, key=lambda x: x.fitness_score, reverse=True)
        
        # Calculate statistics
        fitness_scores = [r.fitness_score for r in results]
        returns = [r.performance_metrics.total_return for r in results]
        sharpe_ratios = [r.performance_metrics.sharpe_ratio for r in results]
        
        comparison = {
            "total_strategies": len(results),
            "best_strategy": {
                "experiment_id": str(sorted_results[0].experiment_id),
                "fitness_score": sorted_results[0].fitness_score,
                "total_return": sorted_results[0].performance_metrics.total_return,
                "sharpe_ratio": sorted_results[0].performance_metrics.sharpe_ratio
            },
            "statistics": {
                "avg_fitness": np.mean(fitness_scores),
                "std_fitness": np.std(fitness_scores),
                "avg_return": np.mean(returns),
                "avg_sharpe": np.mean(sharpe_ratios),
                "success_rate": len([s for s in fitness_scores if s > 1.0]) / len(fitness_scores)
            },
            "risk_profile_distribution": {},
            "top_performers": []
        }
        
        # Risk profile distribution
        risk_profiles = [r.risk_profile.value for r in results]
        for profile in RiskProfile:
            comparison["risk_profile_distribution"][profile.value] = risk_profiles.count(profile.value)
        
        # Top 3 performers
        for i, result in enumerate(sorted_results[:3]):
            comparison["top_performers"].append({
                "rank": i + 1,
                "experiment_id": str(result.experiment_id),
                "fitness_score": result.fitness_score,
                "risk_profile": result.risk_profile.value,
                "key_insights": result.insights[:2]  # Top 2 insights
            })
        
        return comparison


# Factory function for creating results analyzer
def create_results_analyzer(**config) -> ResultsAnalyzer:
    """Create a results analyzer instance"""
    return ResultsAnalyzer(**config)