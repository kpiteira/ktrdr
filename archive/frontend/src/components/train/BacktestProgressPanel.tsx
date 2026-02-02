/**
 * BacktestProgressPanel - Shows backtest execution progress.
 * 
 * This component displays real-time progress updates while a backtest is running,
 * including status, progress bar, and any error messages.
 */

import React from 'react';
import { useTrainModeStore, trainModeActions } from '../../store/trainModeStore';
import './BacktestProgressPanel.css';

export const BacktestProgressPanel: React.FC = () => {
  const state = useTrainModeStore();
  
  if (!state.activeBacktest) {
    return null;
  }
  
  const { activeBacktest } = state;
  const strategy = state.strategies.find(s => s.name === activeBacktest.strategyName);
  
  const getStatusMessage = () => {
    switch (activeBacktest.status) {
      case 'starting':
        return 'Initializing backtest environment...';
      case 'running':
        return 'Running backtest simulation...';
      case 'failed':
        return 'Backtest failed';
      default:
        return 'Processing...';
    }
  };
  
  const getProgressStage = () => {
    // Use enhanced progress info if available
    if (activeBacktest.progressInfo?.current_step) {
      return activeBacktest.progressInfo.current_step;
    }
    
    // Fallback to legacy progress stages
    if (activeBacktest.progress <= 20) return 'Loading strategy and model...';
    if (activeBacktest.progress <= 40) return 'Loading historical data...';
    if (activeBacktest.progress <= 90) return 'Executing trading simulation...';
    return 'Finalizing results...';
  };
  
  const getProgressDetails = () => {
    const progressInfo = activeBacktest.progressInfo;
    if (!progressInfo) return null;
    
    const { items_processed, items_total } = progressInfo;
    if (items_processed && items_total) {
      return `${items_processed.toLocaleString()} / ${items_total.toLocaleString()} bars processed`;
    } else if (items_processed) {
      return `${items_processed.toLocaleString()} bars processed`;
    }
    return null;
  };
  
  return (
    <div className="backtest-progress-panel">
      <div className="progress-header">
        <h2>Running Backtest</h2>
        <div className="strategy-info">
          <span className="strategy-name">{activeBacktest.strategyName}</span>
          {strategy && (
            <span className="symbol-timeframe">
              {strategy.symbol} - {strategy.timeframe}
            </span>
          )}
        </div>
      </div>
      
      <div className="progress-content">
        <div className="progress-visualization">
          <div className="progress-circle">
            <svg className="progress-ring" width="120" height="120">
              <circle
                className="progress-ring-background"
                stroke="#333"
                strokeWidth="8"
                fill="transparent"
                r="52"
                cx="60"
                cy="60"
              />
              <circle
                className="progress-ring-progress"
                stroke="#2196F3"
                strokeWidth="8"
                fill="transparent"
                r="52"
                cx="60"
                cy="60"
                strokeDasharray={`${2 * Math.PI * 52}`}
                strokeDashoffset={`${2 * Math.PI * 52 * (1 - activeBacktest.progress / 100)}`}
                strokeLinecap="round"
              />
            </svg>
            <div className="progress-text">
              <span className="progress-percentage">{activeBacktest.progress}%</span>
              <span className="progress-label">Complete</span>
            </div>
          </div>
          
          <div className="progress-details">
            <div className="status-message">
              <h3>{getStatusMessage()}</h3>
              <p className="stage-description">{getProgressStage()}</p>
              {getProgressDetails() && (
                <p className="progress-details">{getProgressDetails()}</p>
              )}
            </div>
            
            <div className="progress-bar-container">
              <div className="progress-bar">
                <div 
                  className="progress-bar-fill"
                  style={{ width: `${activeBacktest.progress}%` }}
                />
              </div>
              <span className="progress-percentage-text">{activeBacktest.progress}%</span>
            </div>
            
            <div className="progress-stats">
              <div className="stat-item">
                <span className="stat-label">Started:</span>
                <span className="stat-value">
                  {activeBacktest.startedAt ? 
                    new Date(activeBacktest.startedAt).toLocaleTimeString() : 
                    'N/A'
                  }
                </span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Status:</span>
                <span className={`stat-value status-${activeBacktest.status}`}>
                  {activeBacktest.status.charAt(0).toUpperCase() + activeBacktest.status.slice(1)}
                </span>
              </div>
            </div>
          </div>
        </div>
        
        {/* Display warnings and errors */}
        {(activeBacktest.warnings?.length || activeBacktest.errors?.length) && (
          <div className="messages-section">
            {activeBacktest.warnings?.length && (
              <div className="warnings">
                <h4>⚠️ Warnings</h4>
                {activeBacktest.warnings.map((warning, index) => (
                  <p key={index} className="warning-message">{warning}</p>
                ))}
              </div>
            )}
            {activeBacktest.errors?.length && (
              <div className="errors">
                <h4>❌ Errors</h4>
                {activeBacktest.errors.map((error, index) => (
                  <p key={index} className="error-message">{error}</p>
                ))}
              </div>
            )}
          </div>
        )}
        
        {activeBacktest.status === 'failed' && (
          <div className="error-section">
            <h4>❌ Backtest Failed</h4>
            <p className="error-message">
              {activeBacktest.error || 'The backtest encountered an error and could not complete.'}
            </p>
            <div className="error-actions">
              <button 
                className="retry-btn"
                onClick={() => window.location.reload()} // Simple retry for now
              >
                🔄 Retry Backtest
              </button>
              <button 
                className="back-btn"
                onClick={() => {
                  // Clear the active backtest to go back to strategy list
                  trainModeActions.clearActiveBacktest();
                }}
              >
                ← Back to Strategies
              </button>
            </div>
          </div>
        )}
        
        <div className="progress-tips">
          <h4>While you wait...</h4>
          <ul>
            <li>Backtests typically take 1-5 minutes depending on data size</li>
            <li>Neural network evaluation adds processing time for each trade signal</li>
            <li>You can view results in interactive charts once complete</li>
            <li>Multiple strategies can be compared side-by-side</li>
          </ul>
        </div>
      </div>
    </div>
  );
};