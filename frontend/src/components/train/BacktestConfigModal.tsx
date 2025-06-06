/**
 * BacktestConfigModal - Modal for configuring backtest parameters.
 * 
 * This modal allows users to select symbol, timeframe, date range, and other
 * parameters before running a backtest.
 */

import React, { useState, useEffect } from 'react';
import { Strategy, BacktestRequest } from '../../types/trainMode';
import './BacktestConfigModal.css';

interface BacktestConfigModalProps {
  isOpen: boolean;
  strategy: Strategy | null;
  onClose: () => void;
  onSubmit: (config: BacktestRequest) => void;
}

export const BacktestConfigModal: React.FC<BacktestConfigModalProps> = ({
  isOpen,
  strategy,
  onClose,
  onSubmit
}) => {
  const [config, setConfig] = useState<BacktestRequest>({
    strategyName: '',
    symbol: '',
    timeframe: '',
    startDate: '',
    endDate: '',
    initialCapital: 100000,
    commission: 0.001,
    slippage: 0.0005,
    dataMode: 'local'
  });

  // Reset form when strategy changes
  useEffect(() => {
    if (strategy) {
      // Set sensible defaults based on current date
      const currentDate = new Date();
      const startDate = new Date(currentDate.getTime() - 90 * 24 * 60 * 60 * 1000); // 90 days ago
      const endDate = new Date();

      setConfig({
        strategyName: strategy.name,
        symbol: strategy.symbol || 'AAPL',
        timeframe: strategy.timeframe || '1h',
        startDate: startDate.toISOString().split('T')[0],
        endDate: endDate.toISOString().split('T')[0],
        initialCapital: 100000,
        commission: 0.001,
        slippage: 0.0005,
        dataMode: 'local'
      });
    }
  }, [strategy]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation
    if (!config.symbol.trim()) {
      alert('Please enter a symbol');
      return;
    }
    if (!config.timeframe.trim()) {
      alert('Please select a timeframe');
      return;
    }
    if (!config.startDate || !config.endDate) {
      alert('Please select start and end dates');
      return;
    }
    if (new Date(config.startDate) >= new Date(config.endDate)) {
      alert('Start date must be before end date');
      return;
    }

    onSubmit(config);
    onClose();
  };

  if (!isOpen || !strategy) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Configure Backtest</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit} className="backtest-config-form">
          <div className="form-section">
            <h3>Strategy</h3>
            <div className="form-group">
              <label>Strategy Name</label>
              <input
                type="text"
                value={config.strategyName}
                readOnly
                className="readonly"
              />
            </div>
          </div>

          <div className="form-section">
            <h3>Market Data</h3>
            <div className="form-row">
              <div className="form-group">
                <label>Symbol</label>
                <input
                  type="text"
                  value={config.symbol}
                  onChange={(e) => setConfig({ ...config, symbol: e.target.value.toUpperCase() })}
                  placeholder="e.g., AAPL, MSFT"
                  required
                />
              </div>
              <div className="form-group">
                <label>Timeframe</label>
                <select
                  value={config.timeframe}
                  onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}
                  required
                >
                  <option value="">Select timeframe</option>
                  <option value="1m">1 Minute</option>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="30m">30 Minutes</option>
                  <option value="1h">1 Hour</option>
                  <option value="4h">4 Hours</option>
                  <option value="1d">1 Day</option>
                </select>
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Date Range</h3>
            <div className="form-row">
              <div className="form-group">
                <label>Start Date</label>
                <input
                  type="date"
                  value={config.startDate}
                  onChange={(e) => setConfig({ ...config, startDate: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>End Date</label>
                <input
                  type="date"
                  value={config.endDate}
                  onChange={(e) => setConfig({ ...config, endDate: e.target.value })}
                  required
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Trading Parameters</h3>
            <div className="form-row">
              <div className="form-group">
                <label>Initial Capital ($)</label>
                <input
                  type="number"
                  value={config.initialCapital}
                  onChange={(e) => setConfig({ ...config, initialCapital: parseFloat(e.target.value) })}
                  min="1000"
                  step="1000"
                  required
                />
              </div>
              <div className="form-group">
                <label>Commission (%)</label>
                <input
                  type="number"
                  value={config.commission * 100}
                  onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) / 100 })}
                  min="0"
                  max="5"
                  step="0.001"
                  required
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Slippage (%)</label>
                <input
                  type="number"
                  value={config.slippage * 100}
                  onChange={(e) => setConfig({ ...config, slippage: parseFloat(e.target.value) / 100 })}
                  min="0"
                  max="1"
                  step="0.001"
                  required
                />
              </div>
              <div className="form-group">
                <label>Data Mode</label>
                <select
                  value={config.dataMode}
                  onChange={(e) => setConfig({ ...config, dataMode: e.target.value })}
                >
                  <option value="local">Local Data</option>
                  <option value="ib">Interactive Brokers</option>
                </select>
              </div>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" onClick={onClose} className="cancel-btn">
              Cancel
            </button>
            <button type="submit" className="submit-btn">
              🚀 Start Backtest
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};