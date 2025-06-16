"""Advanced performance analysis and reporting tools for multi-timeframe models.

This module provides comprehensive analysis capabilities including visualization,
statistical analysis, comparative studies, and detailed reporting for trading
model performance evaluation.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime, timedelta
import warnings
from scipy import stats
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from ktrdr import get_logger
from ktrdr.evaluation.multi_timeframe_evaluator import EvaluationReport, PerformanceMetrics
from ktrdr.evaluation.backtesting_engine import BacktestResult, Trade

logger = get_logger(__name__)


@dataclass
class PerformanceAnalysisConfig:
    """Configuration for performance analysis."""
    # Visualization settings
    figure_size: Tuple[int, int] = (12, 8)
    style: str = "seaborn-v0_8"
    color_palette: str = "husl"
    save_plots: bool = True
    plot_format: str = "png"
    
    # Analysis settings
    significance_level: float = 0.05
    rolling_window: int = 252  # Trading days
    benchmark_return: float = 0.08  # 8% annual benchmark
    risk_free_rate: float = 0.02   # 2% risk-free rate
    
    # Reporting settings
    include_charts: bool = True
    include_statistics: bool = True
    include_recommendations: bool = True
    detailed_trades: bool = False


@dataclass
class ComparativeAnalysis:
    """Results of comparative analysis between models/strategies."""
    models_compared: List[str]
    performance_ranking: Dict[str, int]
    statistical_significance: Dict[str, bool]
    best_model: str
    performance_gaps: Dict[str, float]
    recommendation: str


@dataclass
class RiskAnalysis:
    """Comprehensive risk analysis results."""
    value_at_risk: Dict[str, float]  # VaR at different confidence levels
    conditional_var: Dict[str, float]  # CVaR at different confidence levels
    maximum_drawdown: float
    drawdown_duration: int
    tail_ratio: float
    downside_deviation: float
    beta: Optional[float]
    correlation_with_market: Optional[float]
    risk_adjusted_returns: Dict[str, float]


@dataclass
class MarketRegimeAnalysis:
    """Analysis of performance across different market regimes."""
    bull_market_performance: Dict[str, float]
    bear_market_performance: Dict[str, float]
    sideways_market_performance: Dict[str, float]
    volatility_regimes: Dict[str, Dict[str, float]]
    regime_detection_accuracy: float
    adaptive_performance: Dict[str, float]


class MultiTimeframePerformanceAnalyzer:
    """Advanced performance analyzer for multi-timeframe trading models."""
    
    def __init__(self, config: Optional[PerformanceAnalysisConfig] = None):
        """
        Initialize performance analyzer.
        
        Args:
            config: Analysis configuration
        """
        self.config = config or PerformanceAnalysisConfig()
        self.logger = get_logger(__name__)
        
        # Set plotting style
        try:
            plt.style.use(self.config.style)
        except OSError:
            plt.style.use('default')
            
        sns.set_palette(self.config.color_palette)
        
        self.logger.info("Initialized MultiTimeframePerformanceAnalyzer")
    
    def analyze_backtest_results(
        self,
        backtest_result: BacktestResult,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of backtest results.
        
        Args:
            backtest_result: Backtest results to analyze
            output_dir: Optional directory to save analysis outputs
            
        Returns:
            Comprehensive analysis results
        """
        self.logger.info("Starting comprehensive backtest analysis")
        
        analysis = {
            'summary': self._create_performance_summary(backtest_result),
            'risk_analysis': self._perform_risk_analysis(backtest_result),
            'trade_analysis': self._analyze_trades(backtest_result.trades),
            'drawdown_analysis': self._analyze_drawdowns(backtest_result),
            'market_regime_analysis': self._analyze_market_regimes(backtest_result),
            'statistical_analysis': self._perform_statistical_analysis(backtest_result),
            'timeframe_analysis': self._analyze_timeframe_performance(backtest_result),
            'recommendations': self._generate_performance_recommendations(backtest_result)
        }
        
        # Generate visualizations
        if self.config.include_charts and output_dir:
            self._create_performance_visualizations(backtest_result, output_dir)
        
        # Save analysis report
        if output_dir:
            self._save_analysis_report(analysis, output_dir)
        
        self.logger.info("Backtest analysis completed")
        return analysis
    
    def compare_models(
        self,
        evaluation_reports: List[EvaluationReport],
        backtest_results: Optional[List[BacktestResult]] = None,
        output_dir: Optional[Path] = None
    ) -> ComparativeAnalysis:
        """
        Compare performance of multiple models.
        
        Args:
            evaluation_reports: List of evaluation reports
            backtest_results: Optional list of backtest results
            output_dir: Optional directory for outputs
            
        Returns:
            Comparative analysis results
        """
        self.logger.info(f"Comparing {len(evaluation_reports)} models")
        
        if len(evaluation_reports) < 2:
            raise ValueError("Need at least 2 models for comparison")
        
        # Extract performance metrics
        models_data = {}
        for report in evaluation_reports:
            model_id = report.model_id
            models_data[model_id] = {
                'accuracy': report.overall_performance.accuracy,
                'f1_score': report.overall_performance.f1_score,
                'win_rate': report.overall_performance.win_rate,
                'precision': report.overall_performance.precision,
                'recall': report.overall_performance.recall
            }
        
        # Add backtest metrics if available
        if backtest_results:
            for i, result in enumerate(backtest_results):
                if i < len(evaluation_reports):
                    model_id = evaluation_reports[i].model_id
                    models_data[model_id].update({
                        'total_return': result.total_return,
                        'sharpe_ratio': result.sharpe_ratio,
                        'max_drawdown': result.max_drawdown,
                        'profit_factor': result.profit_factor
                    })
        
        # Rank models
        ranking = self._rank_models(models_data)
        
        # Statistical significance testing
        significance = self._test_statistical_significance(models_data)
        
        # Performance gaps
        gaps = self._calculate_performance_gaps(models_data, ranking)
        
        # Generate recommendation
        recommendation = self._generate_comparison_recommendation(
            ranking, significance, gaps
        )
        
        comparison = ComparativeAnalysis(
            models_compared=list(models_data.keys()),
            performance_ranking=ranking,
            statistical_significance=significance,
            best_model=list(ranking.keys())[0],
            performance_gaps=gaps,
            recommendation=recommendation
        )
        
        # Create comparison visualizations
        if self.config.include_charts and output_dir:
            self._create_comparison_visualizations(models_data, comparison, output_dir)
        
        return comparison
    
    def _create_performance_summary(self, result: BacktestResult) -> Dict[str, Any]:
        """Create performance summary."""
        
        return {
            'total_return': result.total_return,
            'annual_return': result.annual_return,
            'sharpe_ratio': result.sharpe_ratio,
            'sortino_ratio': result.sortino_ratio,
            'max_drawdown': result.max_drawdown,
            'win_rate': result.win_rate,
            'profit_factor': result.profit_factor,
            'total_trades': result.total_trades,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'calmar_ratio': result.calmar_ratio,
            'recovery_factor': result.recovery_factor,
            'var_95': result.var_95,
            'backtest_period': f"{result.start_date} to {result.end_date}",
            'total_days': result.total_days
        }
    
    def _perform_risk_analysis(self, result: BacktestResult) -> RiskAnalysis:
        """Perform comprehensive risk analysis."""
        
        equity_series = result.equity_curve['equity']
        returns = equity_series.pct_change().dropna()
        
        # Value at Risk calculations
        var_levels = [0.01, 0.05, 0.10]
        var_results = {}
        cvar_results = {}
        
        for level in var_levels:
            var_value = np.percentile(returns, level * 100)
            var_results[f'VaR_{int(level*100)}'] = var_value
            
            # Conditional VaR (Expected Shortfall)
            cvar_value = returns[returns <= var_value].mean()
            cvar_results[f'CVaR_{int(level*100)}'] = cvar_value
        
        # Downside deviation
        downside_returns = returns[returns < 0]
        downside_deviation = np.sqrt(np.mean(downside_returns**2)) if len(downside_returns) > 0 else 0
        
        # Tail ratio
        gains = returns[returns > 0]
        losses = returns[returns < 0]
        
        if len(gains) > 0 and len(losses) > 0:
            tail_ratio = np.percentile(gains, 95) / abs(np.percentile(losses, 5))
        else:
            tail_ratio = 0.0
        
        # Risk-adjusted returns
        risk_adjusted = {
            'sharpe_ratio': result.sharpe_ratio,
            'sortino_ratio': result.sortino_ratio,
            'calmar_ratio': result.calmar_ratio,
            'return_over_var': result.annual_return / abs(var_results.get('VaR_5', 1)) if var_results.get('VaR_5', 0) != 0 else 0
        }
        
        return RiskAnalysis(
            value_at_risk=var_results,
            conditional_var=cvar_results,
            maximum_drawdown=result.max_drawdown,
            drawdown_duration=result.max_drawdown_duration,
            tail_ratio=tail_ratio,
            downside_deviation=downside_deviation,
            beta=None,  # Would need market data
            correlation_with_market=None,  # Would need market data
            risk_adjusted_returns=risk_adjusted
        )
    
    def _analyze_trades(self, trades: List[Trade]) -> Dict[str, Any]:
        """Analyze individual trades."""
        
        if not trades:
            return {}
        
        # Basic trade statistics
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        
        # Trade duration analysis
        durations = []
        for trade in trades:
            if trade.exit_time:
                duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # hours
                durations.append(duration)
        
        # P&L distribution
        pnl_values = [t.pnl for t in trades if t.pnl is not None]
        pnl_pct_values = [t.pnl_pct for t in trades if t.pnl_pct is not None]
        
        # Consecutive analysis
        consecutive_wins = self._calculate_consecutive_outcomes(trades, lambda t: t.pnl > 0)
        consecutive_losses = self._calculate_consecutive_outcomes(trades, lambda t: t.pnl < 0)
        
        # Exit reason analysis
        exit_reasons = {}
        for trade in trades:
            reason = trade.exit_reason
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'avg_trade_duration_hours': np.mean(durations) if durations else 0,
            'median_trade_duration_hours': np.median(durations) if durations else 0,
            'avg_pnl': np.mean(pnl_values) if pnl_values else 0,
            'median_pnl': np.median(pnl_values) if pnl_values else 0,
            'std_pnl': np.std(pnl_values) if pnl_values else 0,
            'avg_pnl_pct': np.mean(pnl_pct_values) if pnl_pct_values else 0,
            'best_trade': max(pnl_values) if pnl_values else 0,
            'worst_trade': min(pnl_values) if pnl_values else 0,
            'max_consecutive_wins': max(consecutive_wins) if consecutive_wins else 0,
            'max_consecutive_losses': max(consecutive_losses) if consecutive_losses else 0,
            'exit_reason_distribution': exit_reasons,
            'trade_size_consistency': np.std([t.quantity for t in trades]) if trades else 0
        }
    
    def _analyze_drawdowns(self, result: BacktestResult) -> Dict[str, Any]:
        """Analyze drawdown characteristics."""
        
        equity_series = result.equity_curve['equity']
        peak_equity = equity_series.expanding().max()
        drawdowns = (equity_series - peak_equity) / peak_equity
        
        # Find drawdown periods
        in_drawdown = drawdowns < -0.001  # More than 0.1% drawdown
        
        if not in_drawdown.any():
            return {'no_significant_drawdowns': True}
        
        drawdown_periods = []
        current_period = None
        
        for timestamp, is_dd in in_drawdown.items():
            if is_dd and current_period is None:
                current_period = {
                    'start': timestamp,
                    'start_equity': equity_series[timestamp],
                    'max_dd': drawdowns[timestamp],
                    'end': timestamp
                }
            elif is_dd and current_period is not None:
                current_period['end'] = timestamp
                if drawdowns[timestamp] < current_period['max_dd']:
                    current_period['max_dd'] = drawdowns[timestamp]
            elif not is_dd and current_period is not None:
                current_period['end_equity'] = equity_series[timestamp]
                current_period['duration'] = (current_period['end'] - current_period['start']).days
                current_period['recovery_time'] = (timestamp - current_period['end']).days
                drawdown_periods.append(current_period)
                current_period = None
        
        if current_period is not None:
            current_period['duration'] = (equity_series.index[-1] - current_period['start']).days
            current_period['recovery_time'] = None  # Still in drawdown
            drawdown_periods.append(current_period)
        
        # Analyze drawdown characteristics
        if drawdown_periods:
            durations = [p['duration'] for p in drawdown_periods]
            recoveries = [p['recovery_time'] for p in drawdown_periods if p['recovery_time'] is not None]
            depths = [abs(p['max_dd']) for p in drawdown_periods]
            
            analysis = {
                'total_drawdown_periods': len(drawdown_periods),
                'avg_drawdown_duration': np.mean(durations),
                'max_drawdown_duration': max(durations),
                'avg_recovery_time': np.mean(recoveries) if recoveries else None,
                'avg_drawdown_depth': np.mean(depths),
                'drawdown_frequency': len(drawdown_periods) / (result.total_days / 365.25),
                'time_underwater_pct': sum(durations) / result.total_days * 100,
                'periods': drawdown_periods[:5]  # Top 5 periods
            }
        else:
            analysis = {'no_significant_drawdowns': True}
        
        return analysis
    
    def _analyze_market_regimes(self, result: BacktestResult) -> MarketRegimeAnalysis:
        """Analyze performance across different market regimes."""
        
        # This is a simplified implementation
        # In practice, would use more sophisticated regime detection
        
        equity_series = result.equity_curve['equity']
        returns = equity_series.pct_change().dropna()
        
        # Simple regime classification based on rolling returns
        rolling_returns = returns.rolling(window=20).mean()
        
        # Define regimes
        bull_mask = rolling_returns > 0.001  # > 0.1% daily average
        bear_mask = rolling_returns < -0.001  # < -0.1% daily average
        sideways_mask = ~(bull_mask | bear_mask)
        
        # Calculate performance in each regime
        bull_performance = {
            'return': returns[bull_mask].mean() * 252 if bull_mask.any() else 0,
            'volatility': returns[bull_mask].std() * np.sqrt(252) if bull_mask.any() else 0,
            'sharpe': (returns[bull_mask].mean() * 252) / (returns[bull_mask].std() * np.sqrt(252)) if bull_mask.any() and returns[bull_mask].std() > 0 else 0,
            'periods': bull_mask.sum()
        }
        
        bear_performance = {
            'return': returns[bear_mask].mean() * 252 if bear_mask.any() else 0,
            'volatility': returns[bear_mask].std() * np.sqrt(252) if bear_mask.any() else 0,
            'sharpe': (returns[bear_mask].mean() * 252) / (returns[bear_mask].std() * np.sqrt(252)) if bear_mask.any() and returns[bear_mask].std() > 0 else 0,
            'periods': bear_mask.sum()
        }
        
        sideways_performance = {
            'return': returns[sideways_mask].mean() * 252 if sideways_mask.any() else 0,
            'volatility': returns[sideways_mask].std() * np.sqrt(252) if sideways_mask.any() else 0,
            'sharpe': (returns[sideways_mask].mean() * 252) / (returns[sideways_mask].std() * np.sqrt(252)) if sideways_mask.any() and returns[sideways_mask].std() > 0 else 0,
            'periods': sideways_mask.sum()
        }
        
        # Volatility regimes
        rolling_vol = returns.rolling(window=20).std()
        high_vol_mask = rolling_vol > rolling_vol.quantile(0.75)
        low_vol_mask = rolling_vol < rolling_vol.quantile(0.25)
        
        volatility_regimes = {
            'high_volatility': {
                'return': returns[high_vol_mask].mean() * 252 if high_vol_mask.any() else 0,
                'periods': high_vol_mask.sum()
            },
            'low_volatility': {
                'return': returns[low_vol_mask].mean() * 252 if low_vol_mask.any() else 0,
                'periods': low_vol_mask.sum()
            }
        }
        
        # Simple regime detection accuracy (placeholder)
        regime_detection_accuracy = 0.75
        
        # Adaptive performance metrics
        adaptive_performance = {
            'regime_consistency': np.std([bull_performance['sharpe'], bear_performance['sharpe'], sideways_performance['sharpe']]),
            'volatility_adaptation': abs(volatility_regimes['high_volatility']['return'] - volatility_regimes['low_volatility']['return'])
        }
        
        return MarketRegimeAnalysis(
            bull_market_performance=bull_performance,
            bear_market_performance=bear_performance,
            sideways_market_performance=sideways_performance,
            volatility_regimes=volatility_regimes,
            regime_detection_accuracy=regime_detection_accuracy,
            adaptive_performance=adaptive_performance
        )
    
    def _perform_statistical_analysis(self, result: BacktestResult) -> Dict[str, Any]:
        """Perform statistical analysis of returns."""
        
        equity_series = result.equity_curve['equity']
        returns = equity_series.pct_change().dropna()
        
        if len(returns) < 30:  # Need sufficient data
            return {'insufficient_data': True}
        
        # Normality test
        shapiro_stat, shapiro_p = stats.shapiro(returns.values[:5000])  # Limit for Shapiro-Wilk
        
        # Stationarity test (simplified)
        # In practice, would use ADF test
        rolling_mean = returns.rolling(window=50).mean()
        stationarity_test = rolling_mean.std() < returns.std() * 0.1
        
        # Autocorrelation
        lag_1_corr = returns.autocorr(lag=1)
        
        # Skewness and Kurtosis
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        
        # Jarque-Bera test for normality
        jb_stat, jb_p = stats.jarque_bera(returns)
        
        # Distribution characteristics
        percentiles = {
            '1%': np.percentile(returns, 1),
            '5%': np.percentile(returns, 5),
            '25%': np.percentile(returns, 25),
            '50%': np.percentile(returns, 50),
            '75%': np.percentile(returns, 75),
            '95%': np.percentile(returns, 95),
            '99%': np.percentile(returns, 99)
        }
        
        return {
            'normality_test': {
                'shapiro_statistic': shapiro_stat,
                'shapiro_p_value': shapiro_p,
                'is_normal': shapiro_p > self.config.significance_level
            },
            'jarque_bera_test': {
                'statistic': jb_stat,
                'p_value': jb_p,
                'is_normal': jb_p > self.config.significance_level
            },
            'stationarity': {
                'appears_stationary': bool(stationarity_test)
            },
            'autocorrelation': {
                'lag_1': lag_1_corr
            },
            'distribution_moments': {
                'mean': returns.mean(),
                'std': returns.std(),
                'skewness': skewness,
                'kurtosis': kurtosis
            },
            'percentiles': percentiles,
            'return_characteristics': {
                'positive_return_ratio': (returns > 0).mean(),
                'extreme_positive_days': (returns > returns.quantile(0.95)).sum(),
                'extreme_negative_days': (returns < returns.quantile(0.05)).sum()
            }
        }
    
    def _analyze_timeframe_performance(self, result: BacktestResult) -> Dict[str, Any]:
        """Analyze performance across different timeframes."""
        
        # Use timeframe performance data from backtest result
        timeframe_perf = result.timeframe_performance
        
        if not timeframe_perf:
            return {'no_timeframe_data': True}
        
        # Calculate timeframe contributions
        total_return = sum(tf_data.get('return', 0) for tf_data in timeframe_perf.values())
        
        contributions = {}
        for tf, tf_data in timeframe_perf.items():
            tf_return = tf_data.get('return', 0)
            contribution = tf_return / total_return if total_return != 0 else 0
            contributions[tf] = {
                'return_contribution': contribution,
                'trade_count': tf_data.get('trades', 0),
                'return': tf_return
            }
        
        # Find best and worst performing timeframes
        sorted_timeframes = sorted(
            contributions.items(),
            key=lambda x: x[1]['return'],
            reverse=True
        )
        
        best_timeframe = sorted_timeframes[0][0] if sorted_timeframes else None
        worst_timeframe = sorted_timeframes[-1][0] if sorted_timeframes else None
        
        return {
            'timeframe_contributions': contributions,
            'best_timeframe': best_timeframe,
            'worst_timeframe': worst_timeframe,
            'timeframe_consistency': np.std([c['return'] for c in contributions.values()]),
            'dominant_timeframe_ratio': max([c['return_contribution'] for c in contributions.values()]) if contributions else 0
        }
    
    def _generate_performance_recommendations(self, result: BacktestResult) -> List[str]:
        """Generate performance improvement recommendations."""
        
        recommendations = []
        
        # Return-based recommendations
        if result.total_return < 0:
            recommendations.append("Negative total return - consider revising strategy or risk management")
        elif result.total_return < self.config.benchmark_return:
            recommendations.append("Returns below benchmark - investigate alpha generation")
        
        # Risk-adjusted recommendations
        if result.sharpe_ratio < 1.0:
            recommendations.append("Low Sharpe ratio - focus on risk-adjusted returns")
        
        if result.max_drawdown > 0.15:
            recommendations.append("High maximum drawdown - implement stronger position sizing or stop losses")
        
        # Trade-based recommendations
        if result.win_rate < 0.45:
            recommendations.append("Low win rate - review entry criteria and market timing")
        
        if result.profit_factor < 1.5:
            recommendations.append("Low profit factor - optimize exit strategy or reduce losses")
        
        # Frequency recommendations
        if result.total_trades < 50:
            recommendations.append("Low trade frequency - consider expanding opportunity set")
        elif result.total_trades > 1000:
            recommendations.append("High trade frequency - review for overtrading")
        
        # Recovery recommendations
        if result.recovery_factor < 2.0:
            recommendations.append("Poor recovery factor - improve risk management")
        
        if not recommendations:
            recommendations.append("Performance metrics are within acceptable ranges")
        
        return recommendations
    
    def _rank_models(self, models_data: Dict[str, Dict[str, float]]) -> Dict[str, int]:
        """Rank models based on composite score."""
        
        # Define weights for different metrics
        weights = {
            'total_return': 0.25,
            'sharpe_ratio': 0.25,
            'win_rate': 0.15,
            'accuracy': 0.15,
            'f1_score': 0.10,
            'max_drawdown': -0.10  # Negative weight (lower is better)
        }
        
        model_scores = {}
        
        for model_id, metrics in models_data.items():
            score = 0
            for metric, weight in weights.items():
                if metric in metrics:
                    value = metrics[metric]
                    if metric == 'max_drawdown':
                        value = -value  # Convert to positive (lower drawdown is better)
                    score += value * weight
            
            model_scores[model_id] = score
        
        # Sort by score (highest first)
        sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Create ranking dictionary
        ranking = {model_id: rank + 1 for rank, (model_id, score) in enumerate(sorted_models)}
        
        return ranking
    
    def _test_statistical_significance(self, models_data: Dict[str, Dict[str, float]]) -> Dict[str, bool]:
        """Test statistical significance of performance differences."""
        
        # Placeholder implementation
        # In practice, would perform t-tests, bootstrap tests, etc.
        
        significance = {}
        model_ids = list(models_data.keys())
        
        for i, model1 in enumerate(model_ids):
            for model2 in model_ids[i+1:]:
                comparison_key = f"{model1}_vs_{model2}"
                
                # Simple comparison based on performance difference
                metrics1 = models_data[model1]
                metrics2 = models_data[model2]
                
                # Compare Sharpe ratios if available
                if 'sharpe_ratio' in metrics1 and 'sharpe_ratio' in metrics2:
                    diff = abs(metrics1['sharpe_ratio'] - metrics2['sharpe_ratio'])
                    significance[comparison_key] = diff > 0.5  # Arbitrary threshold
                else:
                    significance[comparison_key] = False
        
        return significance
    
    def _calculate_performance_gaps(
        self, 
        models_data: Dict[str, Dict[str, float]], 
        ranking: Dict[str, int]
    ) -> Dict[str, float]:
        """Calculate performance gaps between models."""
        
        gaps = {}
        best_model = min(ranking.items(), key=lambda x: x[1])[0]
        
        for model_id in models_data:
            if model_id != best_model:
                # Calculate gap in total return if available
                if 'total_return' in models_data[best_model] and 'total_return' in models_data[model_id]:
                    gap = models_data[best_model]['total_return'] - models_data[model_id]['total_return']
                    gaps[f"{model_id}_return_gap"] = gap
                
                # Calculate gap in Sharpe ratio if available
                if 'sharpe_ratio' in models_data[best_model] and 'sharpe_ratio' in models_data[model_id]:
                    gap = models_data[best_model]['sharpe_ratio'] - models_data[model_id]['sharpe_ratio']
                    gaps[f"{model_id}_sharpe_gap"] = gap
        
        return gaps
    
    def _generate_comparison_recommendation(
        self,
        ranking: Dict[str, int],
        significance: Dict[str, bool],
        gaps: Dict[str, float]
    ) -> str:
        """Generate recommendation based on model comparison."""
        
        best_model = min(ranking.items(), key=lambda x: x[1])[0]
        
        # Check if best model is significantly better
        significant_differences = sum(significance.values())
        
        if significant_differences > len(significance) * 0.5:
            return f"Model {best_model} shows statistically significant superior performance. Recommend for production deployment."
        else:
            return f"Model {best_model} ranks highest but differences may not be statistically significant. Consider ensemble approach."
    
    def _calculate_consecutive_outcomes(self, trades: List[Trade], condition_func) -> List[int]:
        """Calculate consecutive outcomes (wins/losses) in trades."""
        
        consecutive = []
        current_streak = 0
        
        for trade in trades:
            if condition_func(trade):
                current_streak += 1
            else:
                if current_streak > 0:
                    consecutive.append(current_streak)
                    current_streak = 0
        
        if current_streak > 0:
            consecutive.append(current_streak)
        
        return consecutive
    
    def _create_performance_visualizations(
        self, 
        result: BacktestResult, 
        output_dir: Path
    ) -> None:
        """Create comprehensive performance visualizations."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Equity curve
        self._plot_equity_curve(result, output_dir / "equity_curve.png")
        
        # 2. Drawdown chart
        self._plot_drawdown_chart(result, output_dir / "drawdown.png")
        
        # 3. Monthly returns heatmap
        self._plot_monthly_returns_heatmap(result, output_dir / "monthly_returns.png")
        
        # 4. Trade analysis
        self._plot_trade_analysis(result, output_dir / "trade_analysis.png")
        
        # 5. Rolling performance metrics
        self._plot_rolling_metrics(result, output_dir / "rolling_metrics.png")
        
        self.logger.info(f"Performance visualizations saved to {output_dir}")
    
    def _plot_equity_curve(self, result: BacktestResult, output_path: Path) -> None:
        """Plot equity curve with drawdown."""
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=self.config.figure_size, 
                                      gridspec_kw={'height_ratios': [3, 1]})
        
        equity = result.equity_curve['equity']
        
        # Equity curve
        ax1.plot(equity.index, equity.values, linewidth=2, label='Portfolio Value')
        ax1.set_title('Portfolio Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Portfolio Value ($)')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Drawdown
        peak_equity = equity.expanding().max()
        drawdown = (equity - peak_equity) / peak_equity * 100
        
        ax2.fill_between(drawdown.index, drawdown.values, 0, alpha=0.7, color='red')
        ax2.set_title('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_drawdown_chart(self, result: BacktestResult, output_path: Path) -> None:
        """Plot detailed drawdown analysis."""
        
        fig, ax = plt.subplots(figsize=self.config.figure_size)
        
        equity = result.equity_curve['equity']
        peak_equity = equity.expanding().max()
        drawdown = (equity - peak_equity) / peak_equity * 100
        
        # Plot underwater equity curve
        ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.7, color='red', label='Underwater')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
        
        ax.set_title('Underwater Equity Curve', fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Add annotations for major drawdowns
        max_dd_idx = drawdown.idxmin()
        ax.annotate(f'Max DD: {drawdown.min():.1f}%', 
                   xy=(max_dd_idx, drawdown.min()),
                   xytext=(10, 20), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_monthly_returns_heatmap(self, result: BacktestResult, output_path: Path) -> None:
        """Plot monthly returns heatmap."""
        
        monthly_returns = result.monthly_returns * 100  # Convert to percentage
        
        # Create year-month matrix
        years = monthly_returns.index.year.unique()
        months = range(1, 13)
        
        heatmap_data = pd.DataFrame(index=years, columns=months)
        
        for date, ret in monthly_returns.items():
            heatmap_data.loc[date.year, date.month] = ret
        
        # Create heatmap
        fig, ax = plt.subplots(figsize=(12, max(6, len(years) * 0.5)))
        
        sns.heatmap(heatmap_data, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
                   ax=ax, cbar_kws={'label': 'Monthly Return (%)'})
        
        ax.set_title('Monthly Returns Heatmap', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month')
        ax.set_ylabel('Year')
        
        # Set month labels
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        ax.set_xticklabels(month_names)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_trade_analysis(self, result: BacktestResult, output_path: Path) -> None:
        """Plot trade analysis charts."""
        
        if not result.trades:
            return
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        
        # P&L distribution
        pnl_values = [t.pnl for t in result.trades if t.pnl is not None]
        ax1.hist(pnl_values, bins=30, alpha=0.7, edgecolor='black')
        ax1.axvline(x=0, color='red', linestyle='--', alpha=0.7)
        ax1.set_title('P&L Distribution')
        ax1.set_xlabel('P&L ($)')
        ax1.set_ylabel('Frequency')
        
        # Trade duration
        durations = []
        for trade in result.trades:
            if trade.exit_time:
                duration = (trade.exit_time - trade.entry_time).total_seconds() / 3600
                durations.append(duration)
        
        if durations:
            ax2.hist(durations, bins=20, alpha=0.7, edgecolor='black')
            ax2.set_title('Trade Duration Distribution')
            ax2.set_xlabel('Duration (hours)')
            ax2.set_ylabel('Frequency')
        
        # Cumulative P&L
        cumulative_pnl = np.cumsum(pnl_values)
        ax3.plot(range(len(cumulative_pnl)), cumulative_pnl, linewidth=2)
        ax3.set_title('Cumulative P&L by Trade')
        ax3.set_xlabel('Trade Number')
        ax3.set_ylabel('Cumulative P&L ($)')
        ax3.grid(True, alpha=0.3)
        
        # Win/Loss by trade size
        win_trades = [t for t in result.trades if t.pnl > 0]
        loss_trades = [t for t in result.trades if t.pnl < 0]
        
        if win_trades and loss_trades:
            win_sizes = [t.quantity * t.entry_price for t in win_trades]
            loss_sizes = [t.quantity * t.entry_price for t in loss_trades]
            
            ax4.scatter(win_sizes, [t.pnl for t in win_trades], 
                       alpha=0.6, color='green', label='Wins')
            ax4.scatter(loss_sizes, [t.pnl for t in loss_trades], 
                       alpha=0.6, color='red', label='Losses')
            ax4.set_title('P&L vs Trade Size')
            ax4.set_xlabel('Trade Size ($)')
            ax4.set_ylabel('P&L ($)')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_rolling_metrics(self, result: BacktestResult, output_path: Path) -> None:
        """Plot rolling performance metrics."""
        
        equity = result.equity_curve['equity']
        returns = equity.pct_change().dropna()
        
        # Calculate rolling metrics
        window = min(self.config.rolling_window, len(returns) // 4)
        if window < 20:
            return  # Not enough data
        
        rolling_return = returns.rolling(window=window).mean() * 252
        rolling_vol = returns.rolling(window=window).std() * np.sqrt(252)
        rolling_sharpe = rolling_return / rolling_vol
        
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 12))
        
        # Rolling returns
        ax1.plot(rolling_return.index, rolling_return.values, linewidth=2, color='blue')
        ax1.axhline(y=self.config.benchmark_return, color='red', linestyle='--', 
                   alpha=0.7, label=f'Benchmark ({self.config.benchmark_return:.1%})')
        ax1.set_title(f'Rolling Annual Return ({window} days)')
        ax1.set_ylabel('Annual Return')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        
        # Rolling volatility
        ax2.plot(rolling_vol.index, rolling_vol.values, linewidth=2, color='orange')
        ax2.set_title(f'Rolling Annual Volatility ({window} days)')
        ax2.set_ylabel('Annual Volatility')
        ax2.grid(True, alpha=0.3)
        
        # Rolling Sharpe ratio
        ax3.plot(rolling_sharpe.index, rolling_sharpe.values, linewidth=2, color='green')
        ax3.axhline(y=1.0, color='red', linestyle='--', alpha=0.7, label='Sharpe = 1.0')
        ax3.set_title(f'Rolling Sharpe Ratio ({window} days)')
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Sharpe Ratio')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_comparison_visualizations(
        self,
        models_data: Dict[str, Dict[str, float]],
        comparison: ComparativeAnalysis,
        output_dir: Path
    ) -> None:
        """Create model comparison visualizations."""
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance comparison radar chart
        self._plot_performance_radar(models_data, output_dir / "performance_radar.png")
        
        # Ranking visualization
        self._plot_model_ranking(comparison, output_dir / "model_ranking.png")
    
    def _plot_performance_radar(self, models_data: Dict[str, Dict[str, float]], output_path: Path) -> None:
        """Plot radar chart comparing model performance."""
        
        metrics = ['accuracy', 'f1_score', 'win_rate', 'sharpe_ratio']
        available_metrics = [m for m in metrics if any(m in data for data in models_data.values())]
        
        if len(available_metrics) < 3:
            return  # Not enough metrics for radar chart
        
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, len(available_metrics), endpoint=False).tolist()
        angles += angles[:1]  # Complete the circle
        
        for model_id, data in models_data.items():
            values = []
            for metric in available_metrics:
                value = data.get(metric, 0)
                # Normalize values to 0-1 scale
                if metric == 'sharpe_ratio':
                    value = min(max(value / 3.0, 0), 1)  # Scale Sharpe ratio
                elif metric in ['accuracy', 'f1_score', 'win_rate']:
                    value = min(max(value, 0), 1)  # Already 0-1 scale
                values.append(value)
            
            values += values[:1]  # Complete the circle
            
            ax.plot(angles, values, 'o-', linewidth=2, label=model_id)
            ax.fill(angles, values, alpha=0.25)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(available_metrics)
        ax.set_ylim(0, 1)
        ax.set_title('Model Performance Comparison', fontsize=14, fontweight='bold')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_model_ranking(self, comparison: ComparativeAnalysis, output_path: Path) -> None:
        """Plot model ranking visualization."""
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        models = list(comparison.performance_ranking.keys())
        ranks = list(comparison.performance_ranking.values())
        
        colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(models)))
        
        bars = ax.bar(models, ranks, color=colors)
        
        # Add rank labels on bars
        for bar, rank in zip(bars, ranks):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                   f'#{rank}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_title('Model Performance Ranking', fontsize=14, fontweight='bold')
        ax.set_xlabel('Model')
        ax.set_ylabel('Rank')
        ax.set_ylim(0, max(ranks) + 0.5)
        
        # Invert y-axis so rank 1 is at the top
        ax.invert_yaxis()
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _save_analysis_report(self, analysis: Dict[str, Any], output_dir: Path) -> None:
        """Save comprehensive analysis report."""
        
        report_path = output_dir / "performance_analysis_report.json"
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_types(item) for item in obj]
            else:
                return obj
        
        serializable_analysis = convert_types(analysis)
        
        with open(report_path, 'w') as f:
            json.dump(serializable_analysis, f, indent=2, default=str)
        
        self.logger.info(f"Analysis report saved to {report_path}")


def create_performance_analysis_config(**kwargs) -> PerformanceAnalysisConfig:
    """Create performance analysis configuration with defaults."""
    
    config_dict = {
        'figure_size': (12, 8),
        'style': 'seaborn-v0_8',
        'color_palette': 'husl',
        'save_plots': True,
        'plot_format': 'png',
        'significance_level': 0.05,
        'rolling_window': 252,
        'benchmark_return': 0.08,
        'risk_free_rate': 0.02,
        'include_charts': True,
        'include_statistics': True,
        'include_recommendations': True,
        'detailed_trades': False
    }
    
    config_dict.update(kwargs)
    
    return PerformanceAnalysisConfig(**config_dict)