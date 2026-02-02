/**
 * BacktestResultsPanel - Pure presentation component for displaying backtest results.
 * 
 * This component shows performance metrics, trade summary, and provides navigation
 * to Research mode for detailed analysis.
 */

import React from 'react';
import { useTrainModeStore, trainModeActions } from '../../store/trainModeStore';
import { sharedContextActions } from '../../store/sharedContextStore';
import { BacktestResults, BacktestMetrics, BacktestSummary } from '../../types/trainMode';
import './BacktestResultsPanel.css';

export const BacktestResultsPanel: React.FC = () => {
  const state = useTrainModeStore();
  
  if (!state.activeBacktest || state.activeBacktest.status !== 'completed') {
    return null;
  }
  
  const results = state.backtestResults[state.activeBacktest.id];
  const strategy = state.strategies.find(s => s.name === state.activeBacktest?.strategyName);
  
  if (!results || !strategy) {
    return null;
  }
  
  const handleViewInResearch = () => {
    // Prepare transition to Research mode
    trainModeActions.prepareResearchTransition(state.activeBacktest!.id, strategy);
    
    // Switch to Research mode without React Router
    // This app doesn't use React Router - use existing mode switching logic
    window.dispatchEvent(new CustomEvent('switchMode', { detail: { mode: 'research', backtest: state.activeBacktest!.id } }));
  };
  
  return (
    <div className="backtest-results-panel">
      <div className="results-header">
        <div className="header-content">
          <h2>Backtest Results</h2>
          <div className="strategy-info">
            <span className="strategy-name">{strategy.name}</span>
            <span className="symbol-timeframe">{results.symbol} - {results.timeframe}</span>
          </div>
        </div>
        <button 
          onClick={handleViewInResearch}
          className="view-research-btn"
        >
          📊 Analyze in Research Mode
        </button>
      </div>
      
      <div className="results-content">
        <div className="results-tabs">
          <button 
            className={`tab ${state.resultsPanel.selectedTab === 'metrics' ? 'active' : ''}`}
            onClick={() => trainModeActions.setResultsTab('metrics')}
          >
            Metrics
          </button>
          <button 
            className={`tab ${state.resultsPanel.selectedTab === 'trades' ? 'active' : ''}`}
            onClick={() => trainModeActions.setResultsTab('trades')}
          >
            Trades
          </button>
          <button 
            className={`tab ${state.resultsPanel.selectedTab === 'chart' ? 'active' : ''}`}
            onClick={() => trainModeActions.setResultsTab('chart')}
          >
            Chart
          </button>
        </div>
        
        <div className="tab-content">
          {state.resultsPanel.selectedTab === 'metrics' && (
            <MetricsTab results={results} />
          )}
          {state.resultsPanel.selectedTab === 'trades' && (
            <TradesTab backtestId={state.activeBacktest.id} />
          )}
          {state.resultsPanel.selectedTab === 'chart' && (
            <ChartTab backtestId={state.activeBacktest.id} />
          )}
        </div>
      </div>
    </div>
  );
};

// Performance Metrics Tab
interface MetricsTabProps {
  results: BacktestResults;
}

const MetricsTab: React.FC<MetricsTabProps> = ({ results }) => {
  return (
    <div className="metrics-tab">
      <PerformanceMetricsCard metrics={results.metrics} />
      <TradeSummaryCard summary={results.summary} />
    </div>
  );
};

// Performance Metrics Card
interface PerformanceMetricsCardProps {
  metrics: BacktestMetrics;
}

const PerformanceMetricsCard: React.FC<PerformanceMetricsCardProps> = ({ metrics }) => {
  const formatPercentage = (value: number) => `${(value * 100).toFixed(2)}%`;
  const formatCurrency = (value: number) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  const formatRatio = (value: number) => value.toFixed(3);
  
  return (
    <div className="performance-metrics-card">
      <h3>Performance Metrics</h3>
      <div className="metrics-grid">
        <div className="metric-item">
          <span className="metric-label">Total Return</span>
          <span className={`metric-value ${metrics.totalReturn >= 0 ? 'positive' : 'negative'}`}>
            {formatCurrency(metrics.totalReturn)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Annualized Return</span>
          <span className={`metric-value ${metrics.annualizedReturn >= 0 ? 'positive' : 'negative'}`}>
            {formatPercentage(metrics.annualizedReturn)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Sharpe Ratio</span>
          <span className={`metric-value ${metrics.sharpeRatio >= 1 ? 'positive' : metrics.sharpeRatio >= 0 ? 'neutral' : 'negative'}`}>
            {formatRatio(metrics.sharpeRatio)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Max Drawdown</span>
          <span className="metric-value negative">
            {formatCurrency(metrics.maxDrawdown)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Win Rate</span>
          <span className={`metric-value ${metrics.winRate >= 0.5 ? 'positive' : 'negative'}`}>
            {formatPercentage(metrics.winRate)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Profit Factor</span>
          <span className={`metric-value ${metrics.profitFactor >= 1 ? 'positive' : 'negative'}`}>
            {formatRatio(metrics.profitFactor)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Total Trades</span>
          <span className="metric-value neutral">
            {metrics.totalTrades}
          </span>
        </div>
      </div>
    </div>
  );
};

// Trade Summary Card
interface TradeSummaryCardProps {
  summary: BacktestSummary;
}

const TradeSummaryCard: React.FC<TradeSummaryCardProps> = ({ summary }) => {
  const formatCurrency = (value: number) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  
  return (
    <div className="trade-summary-card">
      <h3>Trade Summary</h3>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Initial Capital</span>
          <span className="summary-value">{formatCurrency(summary.initialCapital)}</span>
        </div>
        
        <div className="summary-item">
          <span className="summary-label">Final Value</span>
          <span className={`summary-value ${summary.finalValue >= summary.initialCapital ? 'positive' : 'negative'}`}>
            {formatCurrency(summary.finalValue)}
          </span>
        </div>
        
        <div className="summary-item">
          <span className="summary-label">Total P&L</span>
          <span className={`summary-value ${summary.totalPnl >= 0 ? 'positive' : 'negative'}`}>
            {formatCurrency(summary.totalPnl)}
          </span>
        </div>
        
        <div className="summary-item">
          <span className="summary-label">Winning Trades</span>
          <span className="summary-value positive">{summary.winningTrades}</span>
        </div>
        
        <div className="summary-item">
          <span className="summary-label">Losing Trades</span>
          <span className="summary-value negative">{summary.losingTrades}</span>
        </div>
      </div>
    </div>
  );
};

// Trades Tab
interface TradesTabProps {
  backtestId: string;
}

const TradesTab: React.FC<TradesTabProps> = ({ backtestId }) => {
  const state = useTrainModeStore();
  const trades = state.backtestTrades[backtestId] || [];
  
  
  if (trades.length === 0) {
    return (
      <div className="trades-tab">
        <div className="empty-state">
          <p>No trades found for this backtest</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="trades-tab">
      <div className="trades-header">
        <h3>Trade History ({trades.length} trades)</h3>
      </div>
      <div className="trades-table">
        <div className="table-header">
          <span>Entry Time</span>
          <span>Exit Time</span>
          <span>Side</span>
          <span>Entry Price</span>
          <span>Exit Price</span>
          <span>Quantity</span>
          <span>P&L</span>
        </div>
        <div className="table-body">
          {trades.map((trade, index) => (
            <div key={trade.tradeId || index} className="table-row">
              <span>{new Date(trade.entryTime).toLocaleString()}</span>
              <span>{new Date(trade.exitTime).toLocaleString()}</span>
              <span className={`side ${trade.side.toLowerCase()}`}>{trade.side}</span>
              <span>${trade.entryPrice.toFixed(4)}</span>
              <span>${trade.exitPrice.toFixed(4)}</span>
              <span>{trade.quantity}</span>
              <span className={trade.pnl >= 0 ? 'positive' : 'negative'}>
                ${trade.pnl.toFixed(2)} ({trade.pnlPercent.toFixed(2)}%)
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Chart Tab (placeholder for equity curve)
interface ChartTabProps {
  backtestId: string;
}

const ChartTab: React.FC<ChartTabProps> = ({ backtestId }) => {
  const state = useTrainModeStore();
  const equityCurve = state.equityCurves[backtestId];
  
  return (
    <div className="chart-tab">
      <h3>Equity Curve</h3>
      {equityCurve ? (
        <div className="equity-chart-placeholder">
          <p>Equity curve chart will be displayed here</p>
          <p>Data points: {equityCurve.timestamps.length}</p>
          <button className="view-research-btn-small">
            📊 View Interactive Chart in Research Mode
          </button>
        </div>
      ) : (
        <div className="empty-state">
          <p>No equity curve data available</p>
        </div>
      )}
    </div>
  );
};