/**
 * StrategyListPanel - Pure presentation component for displaying strategies.
 * 
 * This component is "dumb" - it only reads from the store and dispatches actions.
 * No local state for business logic, only UI state if needed.
 */

import React, { useEffect, useState } from 'react';
import { useTrainModeStore, trainModeActions } from '../../store/trainModeStore';
import LoadingSpinner from '../common/LoadingSpinner';
import { Strategy, BacktestRequest } from '../../types/trainMode';
import { BacktestConfigModal } from './BacktestConfigModal';
import './StrategyListPanel.css';

export const StrategyListPanel: React.FC = () => {
  const state = useTrainModeStore();
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);
  
  // Load strategies on mount
  useEffect(() => {
    trainModeActions.loadStrategies();
  }, []);

  const handleConfigureBacktest = (strategy: Strategy) => {
    setSelectedStrategy(strategy);
    setConfigModalOpen(true);
  };

  const handleStartBacktest = (config: BacktestRequest) => {
    trainModeActions.startBacktest(config);
  };
  
  // Pure render based on state
  if (state.strategiesLoading) {
    return (
      <div className="strategy-list-panel">
        <div className="panel-header">
          <h2>Trading Strategies</h2>
        </div>
        <div className="panel-content loading">
          <LoadingSpinner />
        </div>
      </div>
    );
  }
  
  if (state.strategiesError) {
    return (
      <div className="strategy-list-panel">
        <div className="panel-header">
          <h2>Trading Strategies</h2>
        </div>
        <div className="panel-content error">
          <p className="error-message">Failed to load strategies: {state.strategiesError}</p>
          <button onClick={() => trainModeActions.loadStrategies()}>Retry</button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="strategy-list-panel">
      <div className="panel-header">
        <h2>Trading Strategies</h2>
        <button 
          className="refresh-btn"
          onClick={() => trainModeActions.loadStrategies()}
          title="Refresh strategies"
        >
          🔄
        </button>
      </div>
      <div className="panel-content">
        {state.strategies.length === 0 ? (
          <div className="empty-state">
            <p>No strategies found</p>
            <p className="hint">Create a strategy YAML file in the strategies/ directory</p>
          </div>
        ) : (
          <div className="strategy-list">
            {state.strategies.map(strategy => (
              <StrategyCard
                key={strategy.name}
                strategy={strategy}
                isSelected={strategy.name === state.selectedStrategyName}
                isRunning={state.activeBacktest?.strategyName === strategy.name && ['starting', 'running'].includes(state.activeBacktest.status)}
                onSelect={() => trainModeActions.selectStrategy(strategy.name)}
                onRunBacktest={() => handleConfigureBacktest(strategy)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Backtest Configuration Modal */}
      <BacktestConfigModal
        isOpen={configModalOpen}
        strategy={selectedStrategy}
        onClose={() => {
          setConfigModalOpen(false);
          setSelectedStrategy(null);
        }}
        onSubmit={handleStartBacktest}
      />
    </div>
  );
};

// Pure presentational component for strategy cards
interface StrategyCardProps {
  strategy: Strategy;
  isSelected: boolean;
  isRunning: boolean;
  onSelect: () => void;
  onRunBacktest: () => void;
}

const StrategyCard: React.FC<StrategyCardProps> = ({ 
  strategy, 
  isSelected, 
  isRunning, 
  onSelect, 
  onRunBacktest 
}) => {
  const isTrained = strategy.trainingStatus === 'trained';
  const canRunBacktest = isTrained && !isRunning;
  
  const getDisabledReason = () => {
    if (isRunning) return 'Backtest already running';
    if (!isTrained) return 'Strategy not trained yet';
    return '';
  };
  
  return (
    <div 
      className={`strategy-card ${isSelected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="strategy-header">
        <h3>{strategy.name}</h3>
        <span className={`status-badge ${strategy.trainingStatus}`}>
          {strategy.trainingStatus}
        </span>
      </div>
      
      <p className="strategy-description">{strategy.description}</p>
      
      <div className="strategy-details">
        <div className="detail-row">
          <span className="label">Symbol:</span>
          <span className="value">{strategy.symbol}</span>
        </div>
        <div className="detail-row">
          <span className="label">Timeframe:</span>
          <span className="value">{strategy.timeframe}</span>
        </div>
        <div className="detail-row">
          <span className="label">Indicators:</span>
          <span className="value">{strategy.indicators.length}</span>
        </div>
        {strategy.latestVersion && (
          <div className="detail-row">
            <span className="label">Version:</span>
            <span className="value">v{strategy.latestVersion}</span>
          </div>
        )}
      </div>
      
      {strategy.latestMetrics && (
        <div className="strategy-metrics">
          <h4>Training Metrics</h4>
          <div className="metrics-grid">
            {strategy.latestMetrics.accuracy && (
              <div className="metric">
                <span className="metric-label">Accuracy</span>
                <span className="metric-value">{(strategy.latestMetrics.accuracy * 100).toFixed(1)}%</span>
              </div>
            )}
            {strategy.latestMetrics.f1_score && (
              <div className="metric">
                <span className="metric-label">F1 Score</span>
                <span className="metric-value">{strategy.latestMetrics.f1_score.toFixed(3)}</span>
              </div>
            )}
          </div>
        </div>
      )}
      
      <div className="strategy-actions">
        <button 
          className={`run-backtest-btn ${!canRunBacktest ? 'disabled' : ''}`}
          onClick={(e) => {
            e.stopPropagation();
            if (canRunBacktest) {
              onRunBacktest();
            }
          }}
          disabled={!canRunBacktest}
          title={canRunBacktest ? 'Run backtest for this strategy' : getDisabledReason()}
        >
          {isRunning ? (
            <>
              <span className="spinner">⏳</span>
              Running...
            </>
          ) : (
            <>
              📊 Run Backtest
            </>
          )}
        </button>
      </div>
      
      {strategy.trainingStatus === 'untrained' && (
        <div className="training-hint">
          Train this strategy using: <code>uv run ktrdr train {strategy.name}</code>
        </div>
      )}
    </div>
  );
};