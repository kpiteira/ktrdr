/**
 * TrainModeView - Main container for Train Mode UI.
 * 
 * This component orchestrates the entire Train mode interface, managing the layout
 * and coordinating between strategy list, backtest execution, and results display.
 */

import React, { useEffect } from 'react';
import { useTrainModeStore } from '../../store/trainModeStore';
import { useSharedContext } from '../../store/sharedContextStore';
import { StrategyListPanel } from './StrategyListPanel';
import { BacktestResultsPanel } from './BacktestResultsPanel';
import { BacktestProgressPanel } from './BacktestProgressPanel';
import { createLogger } from '../../utils/logger';
import './TrainModeView.css';

const logger = createLogger('TrainModeView');

export const TrainModeView: React.FC = () => {
  const state = useTrainModeStore();
  const { backtestContext } = useSharedContext();
  
  // Determine which panel to show in the main content area
  const renderMainContent = () => {
    // Show progress panel when backtest is running OR failed
    if (state.activeBacktest && ['starting', 'running', 'failed'].includes(state.activeBacktest.status)) {
      return <BacktestProgressPanel />;
    }
    
    // Show results panel when backtest is completed
    if (state.activeBacktest && state.activeBacktest.status === 'completed' && state.viewMode === 'results') {
      return <BacktestResultsPanel />;
    }
    
    // Show results panel if returning from Research mode with backtest context
    if (backtestContext && !state.activeBacktest) {
      return <BacktestContextPanel />;
    }
    
    // Default: Show welcome/instruction panel
    return <WelcomePanel />;
  };
  
  return (
    <div className="train-mode-view">
      <div className="train-mode-header">
        <h1>Strategy Training & Backtesting</h1>
        <p className="mode-description">
          Train neural network models and run backtests to evaluate trading strategy performance
        </p>
      </div>
      
      <div className="train-mode-content">
        <div className="strategy-sidebar">
          <StrategyListPanel />
        </div>
        
        <div className="main-content">
          {renderMainContent()}
        </div>
      </div>
    </div>
  );
};

// Welcome panel shown when no backtest is active
const WelcomePanel: React.FC = () => {
  const state = useTrainModeStore();
  
  return (
    <div className="welcome-panel">
      <div className="welcome-content">
        <div className="welcome-header">
          <h2>Welcome to Train Mode</h2>
          <p>Select a strategy from the sidebar to begin backtesting</p>
        </div>
        
        <div className="feature-cards">
          <div className="feature-card">
            <div className="feature-icon">🧠</div>
            <h3>Neural Network Training</h3>
            <p>Train advanced neural networks on historical data to learn market patterns and generate trading signals.</p>
            <div className="feature-command">
              <code>uv run ktrdr train &lt;strategy&gt;</code>
            </div>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">📊</div>
            <h3>Strategy Backtesting</h3>
            <p>Test your trained strategies against historical data to evaluate performance and risk metrics.</p>
            <div className="feature-command">
              <code>uv run ktrdr backtest &lt;strategy&gt;</code>
            </div>
          </div>
          
          <div className="feature-card">
            <div className="feature-icon">🔬</div>
            <h3>Research Analysis</h3>
            <p>Dive deep into backtest results with interactive charts, trade analysis, and fuzzy logic visualization.</p>
            <div className="feature-action">
              Available after backtesting
            </div>
          </div>
        </div>
        
        {state.strategies.length === 0 && (
          <div className="getting-started">
            <h3>Getting Started</h3>
            <ol>
              <li>Create a strategy configuration file in the <code>strategies/</code> directory</li>
              <li>Train your strategy using the CLI: <code>uv run ktrdr train &lt;strategy-name&gt;</code></li>
              <li>Return here to run backtests and analyze results</li>
            </ol>
            <p className="hint">
              See the examples in <code>strategies/</code> directory for configuration templates.
            </p>
          </div>
        )}
        
        {state.selectedStrategyName && (
          <div className="selected-strategy-info">
            <h3>Selected Strategy: {state.selectedStrategyName}</h3>
            <p>Click "Run Backtest" on the strategy card to begin performance analysis.</p>
          </div>
        )}
      </div>
    </div>
  );
};

// Panel to show when returning from Research mode with backtest context
const BacktestContextPanel: React.FC = () => {
  const { backtestContext } = useSharedContext();
  
  if (!backtestContext) return null;
  
  return (
    <div className="train-mode-content">
      <div className="context-panel">
        <div className="context-header">
          <div className="context-badge">
            📊 Viewing Backtest Results
          </div>
          <h2>Backtest Analysis Complete</h2>
          <div className="context-info">
            <span className="strategy-name">{backtestContext.strategy.name}</span>
            <span className="symbol-timeframe">
              {backtestContext.symbol} - {backtestContext.timeframe}
            </span>
            <span className="date-range">
              {backtestContext.dateRange.start} to {backtestContext.dateRange.end}
            </span>
          </div>
        </div>
        
        <div className="context-content">
          <div className="context-section">
            <h3>📈 Analysis Available</h3>
            <p>
              You've successfully analyzed this backtest in Research mode. 
              The analysis included:
            </p>
            <ul>
              <li><strong>Trade Execution Points:</strong> {backtestContext.trades.length} trades visualized on charts</li>
              <li><strong>Indicator Analysis:</strong> {backtestContext.indicators.length} indicators with fuzzy logic overlays</li>
              <li><strong>Strategy Performance:</strong> Detailed metrics and risk analysis</li>
              <li><strong>Decision Points:</strong> Entry and exit signals mapped to market conditions</li>
            </ul>
          </div>
          
          <div className="context-actions">
            <button 
              className="btn-primary"
              onClick={() => {
                // Switch back to Research mode
                window.dispatchEvent(new CustomEvent('switchMode', { detail: { mode: 'research' } }));
              }}
            >
              📊 Return to Research Analysis
            </button>
            
            <button 
              className="btn-secondary"
              onClick={() => {
                // Run a new backtest with the same strategy
                const strategy = backtestContext.strategy;
                // TODO: Trigger new backtest modal with pre-filled strategy
                logger.info('Starting backtest for strategy:', strategy.name);
              }}
            >
              🔄 Run New Backtest
            </button>
            
            <button 
              className="btn-tertiary"
              onClick={() => {
                // Clear context and return to strategy list
                window.dispatchEvent(new CustomEvent('clearBacktestContext'));
              }}
            >
              ← Back to Strategy List
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};