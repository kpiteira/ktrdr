/**
 * BacktestOverlay - Research mode integration for backtest results.
 * 
 * This component adds trade markers and backtest context to the existing Research mode
 * when viewing backtest results. It integrates with TradingView charts to show trade
 * entry/exit points and provides backtest-specific UI elements.
 */

import React, { useEffect, useState, useRef } from 'react';
import { createSeriesMarkers, type SeriesMarker, type Time } from 'lightweight-charts';
import { useSharedContext, sharedContextActions } from '../../../store/sharedContextStore';
import { Trade } from '../../../types/trainMode';
import { createLogger } from '../../../utils/logger';
import './BacktestOverlay.css';

const logger = createLogger('BacktestOverlay');

interface BacktestOverlayProps {
  chartApi?: any; // TradingView chart API
}

export const BacktestOverlay: React.FC<BacktestOverlayProps> = ({ chartApi }) => {
  const { backtestContext } = useSharedContext();
  const [tradeMarkers, setTradeMarkers] = useState<any[]>([]);
  const [hoveredTrade, setHoveredTrade] = useState<Trade | null>(null);
  const chartApiRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const seriesMarkersApiRef = useRef<any>(null);
  
  // Store chart API reference from props and get candlestick series
  useEffect(() => {
    if (chartApi) {
      chartApiRef.current = chartApi;
      
      // Listen for the chartReady event to get the candlestick series
      const handleChartReady = (event: CustomEvent) => {
        if (event.detail && event.detail.candlestickSeries) {
          candlestickSeriesRef.current = event.detail.candlestickSeries;
        }
      };
      
      window.addEventListener('chartReady', handleChartReady as EventListener);
      
      // Clean up the event listener
      return () => {
        window.removeEventListener('chartReady', handleChartReady as EventListener);
      };
    }
  }, [chartApi]);

  // Add trade markers to chart when context is available
  useEffect(() => {
    if (!backtestContext || !chartApiRef.current || !candlestickSeriesRef.current) {
      return;
    }
    
    try {
      // Create trade markers for executed trades using correct v5 API
      const markers: SeriesMarker<Time>[] = backtestContext.trades.flatMap(trade => [
        // Entry marker
        {
          time: Math.floor(new Date(trade.entryTime).getTime() / 1000) as Time,
          position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
          color: trade.side === 'BUY' ? '#26a69a' : '#ef5350',
          shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
          text: `${trade.side} $${trade.entryPrice.toFixed(4)}`,
          size: 2,
          id: trade.tradeId || `${trade.entryTime}-${trade.side}`
        },
        // Exit marker
        {
          time: Math.floor(new Date(trade.exitTime).getTime() / 1000) as Time,
          position: trade.side === 'BUY' ? 'aboveBar' : 'belowBar',
          color: trade.pnl >= 0 ? '#4CAF50' : '#ef5350',
          shape: 'circle',
          text: `Exit $${trade.exitPrice.toFixed(4)} (${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)})`,
          size: 1,
          id: `exit-${trade.tradeId || `${trade.exitTime}-exit`}`
        }
      ]);
      
      logger.info(`Creating ${markers.length} trade markers for backtest ${backtestContext.backtestId}`);
      
      // Create series markers using TradingView v5 API
      const seriesMarkersApi = createSeriesMarkers(candlestickSeriesRef.current, markers);
      
      // Store reference for cleanup
      seriesMarkersApiRef.current = seriesMarkersApi;
      setTradeMarkers(markers);
      
      logger.info('Successfully added trade markers to chart');
      
      // Cleanup function
      return () => {
        if (seriesMarkersApiRef.current) {
          try {
            seriesMarkersApiRef.current.setMarkers([]);
            logger.debug('Cleared trade markers from chart');
          } catch (error) {
            logger.warn('Error clearing chart markers:', error);
          }
        }
      };
    } catch (error) {
      logger.error('Failed to add trade markers to chart:', error);
    }
  }, [backtestContext, chartApi]);
  
  // Don't render if no backtest context
  if (!backtestContext) return null;
  
  return (
    <>
      <BacktestMetricsOverlay />
      {hoveredTrade && <TradeDetailsPopup trade={hoveredTrade} />}
    </>
  );
};

// Backtest mode indicator at top of Research view
const BacktestModeIndicator: React.FC = () => {
  const { backtestContext } = useSharedContext();
  
  if (!backtestContext) return null;
  
  const handleExitBacktestView = () => {
    // Clear the backtest context
    sharedContextActions.clearBacktestContext();
    
    // Switch back to Train mode using custom event
    window.dispatchEvent(new CustomEvent('switchMode', { detail: { mode: 'train' } }));
  };
  
  const handleBackToResults = () => {
    // Switch back to Train mode but keep context
    window.dispatchEvent(new CustomEvent('switchMode', { detail: { mode: 'train' } }));
  };
  
  return (
    <div className="backtest-mode-indicator">
      <div className="indicator-content">
        <div className="indicator-info">
          <span className="indicator-badge">
            📊 Viewing Backtest Results
          </span>
          <div className="strategy-details">
            <span className="strategy-name">{backtestContext.strategy.name}</span>
            <span className="symbol-timeframe">
              {backtestContext.symbol} - {backtestContext.timeframe}
            </span>
            <span className="date-range">
              {backtestContext.dateRange.start} to {backtestContext.dateRange.end}
            </span>
          </div>
        </div>
        
        <div className="indicator-actions">
          <button 
            onClick={handleBackToResults}
            className="back-to-results-btn"
            title="Return to backtest results"
          >
            ← Back to Results
          </button>
          <button 
            onClick={handleExitBacktestView}
            className="exit-backtest-btn"
            title="Exit backtest view"
          >
            ✕ Exit Backtest View
          </button>
        </div>
      </div>
      
      <div className="trade-summary">
        <span className="trade-count">
          {backtestContext.trades.length} trades
        </span>
        <span className="pnl-summary">
          Total P&L: ${backtestContext.trades.reduce((sum, trade) => sum + trade.pnl, 0).toFixed(2)}
        </span>
      </div>
    </div>
  );
};

// Trade details popup (for future enhancement)
interface TradeDetailsPopupProps {
  trade: Trade;
}

const TradeDetailsPopup: React.FC<TradeDetailsPopupProps> = ({ trade }) => {
  return (
    <div className="trade-details-popup">
      <div className="popup-header">
        <h4>Trade Details</h4>
      </div>
      <div className="popup-content">
        <div className="detail-row">
          <span>Side:</span>
          <span className={`side ${trade.side.toLowerCase()}`}>{trade.side}</span>
        </div>
        <div className="detail-row">
          <span>Entry:</span>
          <span>${trade.entryPrice.toFixed(4)} at {new Date(trade.entryTime).toLocaleString()}</span>
        </div>
        <div className="detail-row">
          <span>Exit:</span>
          <span>${trade.exitPrice.toFixed(4)} at {new Date(trade.exitTime).toLocaleString()}</span>
        </div>
        <div className="detail-row">
          <span>Quantity:</span>
          <span>{trade.quantity}</span>
        </div>
        <div className="detail-row">
          <span>P&L:</span>
          <span className={trade.pnl >= 0 ? 'positive' : 'negative'}>
            ${trade.pnl.toFixed(2)} ({trade.pnlPercent.toFixed(2)}%)
          </span>
        </div>
        {trade.entryReason && (
          <div className="detail-row">
            <span>Entry Reason:</span>
            <span>{trade.entryReason}</span>
          </div>
        )}
        {trade.exitReason && (
          <div className="detail-row">
            <span>Exit Reason:</span>
            <span>{trade.exitReason}</span>
          </div>
        )}
      </div>
    </div>
  );
};

// Performance metrics overlay in Research mode
const BacktestMetricsOverlay: React.FC = () => {
  const { backtestContext } = useSharedContext();
  
  if (!backtestContext) return null;
  
  
  // Calculate key metrics from trades
  const totalTrades = backtestContext.trades.length;
  const winningTrades = backtestContext.trades.filter(t => t.pnl > 0).length;
  const losingTrades = backtestContext.trades.filter(t => t.pnl < 0).length;
  const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
  const totalPnL = backtestContext.trades.reduce((sum, trade) => sum + trade.pnl, 0);
  
  const avgWin = winningTrades > 0 ? 
    backtestContext.trades.filter(t => t.pnl > 0).reduce((sum, t) => sum + t.pnl, 0) / winningTrades : 0;
  const avgLoss = losingTrades > 0 ? 
    backtestContext.trades.filter(t => t.pnl < 0).reduce((sum, t) => sum + t.pnl, 0) / losingTrades : 0;
  const profitFactor = avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;
  
  return (
    <div className="backtest-metrics-overlay">
      <div className="metrics-header">
        <h4>📊 Backtest Performance</h4>
        <div className="strategy-info">
          {backtestContext.strategy.name} • {backtestContext.symbol} {backtestContext.timeframe}
        </div>
      </div>
      
      <div className="metrics-grid">
        <div className="metric-item">
          <span className="metric-label">Total Trades</span>
          <span className="metric-value">{totalTrades}</span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Win Rate</span>
          <span className={`metric-value ${winRate >= 50 ? 'positive' : 'negative'}`}>
            {winRate.toFixed(1)}%
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Total P&L</span>
          <span className={`metric-value ${totalPnL >= 0 ? 'positive' : 'negative'}`}>
            ${totalPnL.toFixed(2)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Profit Factor</span>
          <span className={`metric-value ${profitFactor >= 1 ? 'positive' : 'negative'}`}>
            {profitFactor.toFixed(2)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Avg Win</span>
          <span className="metric-value positive">
            ${avgWin.toFixed(2)}
          </span>
        </div>
        
        <div className="metric-item">
          <span className="metric-label">Avg Loss</span>
          <span className="metric-value negative">
            ${avgLoss.toFixed(2)}
          </span>
        </div>
      </div>
      
      <div className="fuzzy-indicators-info">
        <div className="info-section">
          <h5>🧠 Strategy Indicators</h5>
          <div className="indicators-list">
            {Array.isArray(backtestContext.indicators) && backtestContext.indicators.length > 0 ? (
              backtestContext.indicators.map((indicator, index) => (
                <div key={index} className="indicator-item">
                  <span className="indicator-name">{indicator.name || 'Unknown Indicator'}</span>
                  <span className="indicator-params">
                    {indicator.parameters && typeof indicator.parameters === 'object' 
                      ? Object.entries(indicator.parameters).map(([key, value]) => 
                          `${key}: ${value}`
                        ).join(', ')
                      : 'No parameters'
                    }
                  </span>
                </div>
              ))
            ) : (
              <div className="indicator-item">
                <span className="indicator-name">No indicators configured</span>
                <span className="indicator-params">Strategy uses default settings</span>
              </div>
            )}
          </div>
        </div>
        
        <div className="info-section">
          <h5>🎯 Decision Points</h5>
          <div className="decision-points-summary">
            <div className="point-stat">
              <span>Entry Signals: {backtestContext.trades.length}</span>
            </div>
            <div className="point-stat">
              <span>Exit Signals: {backtestContext.trades.length}</span>
            </div>
            <div className="point-stat">
              <span>Successful: {winningTrades} ({winRate.toFixed(1)}%)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};