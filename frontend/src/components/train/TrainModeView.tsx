/**
 * TrainModeView - Main container for Train Mode UI.
 * 
 * This component orchestrates the entire Train mode interface, managing the layout
 * and coordinating between strategy list, backtest execution, and results display.
 */

import React, { useEffect } from 'react';
import { useTrainModeStore } from '../../store/trainModeStore';
import { StrategyListPanel } from './StrategyListPanel';
import { BacktestResultsPanel } from './BacktestResultsPanel';
import { BacktestProgressPanel } from './BacktestProgressPanel';
import './TrainModeView.css';

export const TrainModeView: React.FC = () => {
  const state = useTrainModeStore();
  
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