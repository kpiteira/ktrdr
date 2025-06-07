/**
 * Train Mode Store - Single source of truth for all Train mode state.
 * 
 * This store follows strict state management principles:
 * - ALL state lives here, no local component state for business logic
 * - Components are pure renderers that read from this store
 * - Actions are the ONLY way to modify state
 * - No derived state is stored, always compute from source
 */

import { createStore } from './createStore';
import { 
  Strategy, 
  BacktestRequest, 
  BacktestStatus, 
  BacktestResults, 
  Trade,
  EquityCurve 
} from '../types/trainMode';
import { apiClient } from '../api/client';
import { sharedContextActions } from './sharedContextStore';
import { createLogger } from '../utils/logger';

const logger = createLogger('trainModeStore');

// Train mode state definition
export interface TrainModeState {
  // Strategy List State
  strategies: Strategy[];
  strategiesLoading: boolean;
  strategiesError: string | null;
  
  // Selected Strategy State
  selectedStrategyName: string | null;
  
  // Backtest Execution State
  activeBacktest: BacktestStatus | null;
  
  // Backtest Results State
  backtestResults: {
    [backtestId: string]: BacktestResults;
  };
  
  // Trade Details State
  backtestTrades: {
    [backtestId: string]: Trade[];
  };
  
  // Equity Curve State
  equityCurves: {
    [backtestId: string]: EquityCurve;
  };
  
  // UI View State
  viewMode: 'list' | 'results' | 'details';
  resultsPanel: {
    selectedTab: 'metrics' | 'trades' | 'chart';
    chartTimeRange: { start: string; end: string } | null;
  };
  
  // Research Mode Transition State
  pendingResearchTransition: {
    backtestId: string;
    strategy: Strategy;
  } | null;
}

// Create the single store instance
export const trainModeStore = createStore<TrainModeState>({
  strategies: [],
  strategiesLoading: false,
  strategiesError: null,
  selectedStrategyName: null,
  activeBacktest: null,
  backtestResults: {},
  backtestTrades: {},
  equityCurves: {},
  viewMode: 'list',
  resultsPanel: {
    selectedTab: 'trades',
    chartTimeRange: null
  },
  pendingResearchTransition: null
});

// Polling interval for backtest status
let statusPollingInterval: number | null = null;

/**
 * Actions are the ONLY way to modify the store state.
 * Each action is a pure function that describes what happened.
 */
export const trainModeActions = {
  // Strategy List Actions
  loadStrategies: async () => {
    trainModeStore.setState(state => ({
      ...state,
      strategiesLoading: true,
      strategiesError: null
    }));
    
    try {
      const response = await apiClient.get('/api/v1/strategies/');
      
      if (response.success && response.strategies) {
        trainModeStore.setState(state => ({
          ...state,
          strategies: response.strategies.map((s: any) => ({
            name: s.name,
            description: s.description,
            symbol: s.symbol,
            timeframe: s.timeframe,
            indicators: s.indicators,
            fuzzyConfig: s.fuzzy_config,
            trainingStatus: s.training_status,
            availableVersions: s.available_versions,
            latestVersion: s.latest_version,
            latestTrainingDate: s.latest_training_date,
            latestMetrics: s.latest_metrics
          })),
          strategiesLoading: false
        }));
      }
    } catch (error) {
      trainModeStore.setState(state => ({
        ...state,
        strategiesError: error instanceof Error ? error.message : 'Failed to load strategies',
        strategiesLoading: false
      }));
    }
  },
  
  selectStrategy: (strategyName: string | null) => {
    trainModeStore.setState(state => ({
      ...state,
      selectedStrategyName: strategyName
    }));
  },
  
  // Backtest Execution Actions
  startBacktest: async (request: BacktestRequest) => {
    // Clear any existing polling
    if (statusPollingInterval) {
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
    
    // Set starting state
    trainModeStore.setState(state => ({
      ...state,
      activeBacktest: {
        id: '',  // Will be set when API responds
        strategyName: request.strategyName,
        status: 'starting',
        progress: 0,
        startedAt: new Date().toISOString()
      }
    }));
    
    try {
      const response = await apiClient.post('/api/v1/backtests/', {
        strategy_name: request.strategyName,
        symbol: request.symbol,
        timeframe: request.timeframe,
        start_date: request.startDate,
        end_date: request.endDate,
        initial_capital: request.initialCapital || 100000,
        commission: request.commission || 0.001,
        slippage: request.slippage || 0.0005,
        data_mode: request.dataMode || 'local'
      });
      
      if (response.success && response.backtest_id) {
        // Update with backtest ID
        trainModeStore.setState(state => ({
          ...state,
          activeBacktest: state.activeBacktest ? {
            ...state.activeBacktest,
            id: response.backtest_id,
            status: 'running'
          } : null
        }));
        
        // Start polling for status
        pollBacktestStatus(response.backtest_id);
      } else {
        // API returned success=false or no backtest_id
        trainModeStore.setState(state => ({
          ...state,
          activeBacktest: state.activeBacktest ? {
            ...state.activeBacktest,
            status: 'failed',
            error: response.message || 'Failed to start backtest'
          } : null
        }));
      }
    } catch (error) {
      logger.error('Failed to start backtest:', error);
      
      // Determine error message based on error type
      let errorMessage = 'Failed to start backtest';
      if (error instanceof Error) {
        if (error.message.includes('404')) {
          errorMessage = 'Strategy or endpoint not found - check strategy configuration';
        } else if (error.message.includes('400')) {
          errorMessage = 'Invalid backtest parameters';
        } else if (error.message.includes('500')) {
          errorMessage = 'Server error - please try again later';
        } else {
          errorMessage = error.message;
        }
      }
      
      trainModeStore.setState(state => ({
        ...state,
        activeBacktest: state.activeBacktest ? {
          ...state.activeBacktest,
          status: 'failed',
          error: errorMessage
        } : null
      }));
    }
  },
  
  clearActiveBacktest: () => {
    // Clear any existing polling
    if (statusPollingInterval) {
      clearInterval(statusPollingInterval);
      statusPollingInterval = null;
    }
    
    trainModeStore.setState(state => ({
      ...state,
      activeBacktest: null,
      viewMode: 'list'
    }));
  },
  
  updateBacktestProgress: (backtestId: string, progress: number, status: BacktestStatus['status']) => {
    trainModeStore.setState(state => {
      if (state.activeBacktest?.id !== backtestId) return state;
      
      return {
        ...state,
        activeBacktest: {
          ...state.activeBacktest,
          progress,
          status
        }
      };
    });
  },
  
  setBacktestResults: (backtestId: string, results: BacktestResults) => {
    trainModeStore.setState(state => ({
      ...state,
      backtestResults: {
        ...state.backtestResults,
        [backtestId]: results
      },
      viewMode: 'results'
    }));
  },
  
  setBacktestTrades: (backtestId: string, trades: Trade[]) => {
    trainModeStore.setState(state => ({
      ...state,
      backtestTrades: {
        ...state.backtestTrades,
        [backtestId]: trades
      }
    }));
  },
  
  setEquityCurve: (backtestId: string, curve: EquityCurve) => {
    trainModeStore.setState(state => ({
      ...state,
      equityCurves: {
        ...state.equityCurves,
        [backtestId]: curve
      }
    }));
  },
  
  // UI State Actions
  setViewMode: (mode: TrainModeState['viewMode']) => {
    trainModeStore.setState(state => ({
      ...state,
      viewMode: mode
    }));
  },
  
  setResultsTab: (tab: TrainModeState['resultsPanel']['selectedTab']) => {
    trainModeStore.setState(state => ({
      ...state,
      resultsPanel: {
        ...state.resultsPanel,
        selectedTab: tab
      }
    }));
  },
  
  // Research Mode Transition
  prepareResearchTransition: (backtestId: string, strategy: Strategy) => {
    const state = trainModeStore.getState();
    const results = state.backtestResults[backtestId];
    const trades = state.backtestTrades[backtestId] || [];
    
    if (!results) return;
    
    // Enhanced strategy indicators for Research mode visualization
    const enhancedIndicators = strategy.indicators && strategy.indicators.length > 0 
      ? strategy.indicators 
      : [
          // Default indicators if strategy doesn't specify them
          {
            name: 'Simple Moving Average',
            type: 'sma',
            parameters: { period: 20, source: 'close' },
            fuzzySupport: {
              enabled: true,
              sets: ['below', 'near', 'above'],
              scalingType: 'relative'
            }
          },
          {
            name: 'Relative Strength Index',
            type: 'rsi',
            parameters: { period: 14, source: 'close' },
            fuzzySupport: {
              enabled: true,
              sets: ['oversold', 'neutral', 'overbought'],
              scalingType: 'fixed',
              range: { min: 0, max: 100 }
            }
          },
          {
            name: 'Exponential Moving Average',
            type: 'ema',
            parameters: { period: 12, source: 'close' },
            fuzzySupport: {
              enabled: true,
              sets: ['below', 'near', 'above'],
              scalingType: 'relative'
            }
          }
        ];
    
    // Enhanced fuzzy configuration
    const enhancedFuzzyConfig = strategy.fuzzyConfig && Object.keys(strategy.fuzzyConfig).length > 0
      ? strategy.fuzzyConfig
      : {
          colorScheme: 'trading',
          opacity: 0.3,
          membershipThreshold: 0.5,
          rules: {
            bullish: {
              conditions: ['sma_above', 'rsi_oversold_recovery'],
              confidence: 0.8
            },
            bearish: {
              conditions: ['sma_below', 'rsi_overbought_decline'],
              confidence: 0.8
            },
            neutral: {
              conditions: ['rsi_neutral', 'price_near_sma'],
              confidence: 0.6
            }
          }
        };
    
    // Set up shared context for Research mode
    const context = {
      mode: 'backtest' as const,
      strategy: {
        ...strategy,
        indicators: enhancedIndicators,
        fuzzyConfig: enhancedFuzzyConfig
      },
      symbol: results.symbol,
      timeframe: results.timeframe,
      dateRange: {
        start: results.startDate,
        end: results.endDate
      },
      indicators: enhancedIndicators,
      fuzzyConfig: enhancedFuzzyConfig,
      trades,
      backtestId
    };
    
    sharedContextActions.setBacktestContext(context);
    
    trainModeStore.setState(state => ({
      ...state,
      pendingResearchTransition: {
        backtestId,
        strategy
      }
    }));
  },
  
  clearPendingTransition: () => {
    trainModeStore.setState(state => ({
      ...state,
      pendingResearchTransition: null
    }));
  }
};

// Helper function to poll backtest status
async function pollBacktestStatus(backtestId: string) {
  // Don't start polling if no valid ID
  if (!backtestId) {
    logger.error('Cannot poll backtest status: no valid backtest ID');
    return;
  }
  
  let consecutiveErrors = 0;
  const maxErrors = 5; // Stop polling after 5 consecutive errors
  
  statusPollingInterval = window.setInterval(async () => {
    try {
      const response = await apiClient.get(`/api/v1/backtests/${backtestId}`);
      
      if (response.success) {
        // Reset error counter on successful response
        consecutiveErrors = 0;
        
        trainModeActions.updateBacktestProgress(
          backtestId,
          response.progress,
          response.status
        );
        
        if (response.status === 'completed') {
          // Stop polling
          if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
          }
          
          // Fetch full results
          await fetchBacktestResults(backtestId);
        } else if (response.status === 'failed') {
          // Stop polling on failure
          if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
          }
        }
      } else {
        // API returned success=false
        consecutiveErrors++;
        logger.error(`Backtest status poll failed: ${response.message || 'Unknown error'}`);
        
        if (consecutiveErrors >= maxErrors) {
          logger.error(`Stopping polling after ${maxErrors} consecutive errors`);
          if (statusPollingInterval) {
            clearInterval(statusPollingInterval);
            statusPollingInterval = null;
          }
          
          // Mark backtest as failed
          trainModeStore.setState(state => ({
            ...state,
            activeBacktest: state.activeBacktest ? {
              ...state.activeBacktest,
              status: 'failed',
              error: 'Lost connection to backtest - please try again'
            } : null
          }));
        }
      }
    } catch (error) {
      consecutiveErrors++;
      logger.error('Failed to poll backtest status:', error);
      
      // If we hit too many errors, stop polling and mark as failed
      if (consecutiveErrors >= maxErrors) {
        logger.error(`Stopping polling after ${maxErrors} consecutive errors`);
        if (statusPollingInterval) {
          clearInterval(statusPollingInterval);
          statusPollingInterval = null;
        }
        
        // Mark backtest as failed
        trainModeStore.setState(state => ({
          ...state,
          activeBacktest: state.activeBacktest ? {
            ...state.activeBacktest,
            status: 'failed',
            error: 'Lost connection to backtest - please try again'
          } : null
        }));
      }
    }
  }, 1000); // Poll every second
}

// Helper function to fetch complete backtest results
async function fetchBacktestResults(backtestId: string) {
  try {
    // Fetch results
    const resultsResponse = await apiClient.get(`/api/v1/backtests/${backtestId}/results`);
    if (resultsResponse.success) {
      trainModeActions.setBacktestResults(backtestId, {
        backtestId: resultsResponse.backtest_id,
        strategyName: resultsResponse.strategy_name,
        symbol: resultsResponse.symbol,
        timeframe: resultsResponse.timeframe,
        startDate: resultsResponse.start_date,
        endDate: resultsResponse.end_date,
        metrics: {
          totalReturn: resultsResponse.metrics.total_return,
          annualizedReturn: resultsResponse.metrics.annualized_return,
          sharpeRatio: resultsResponse.metrics.sharpe_ratio,
          maxDrawdown: resultsResponse.metrics.max_drawdown,
          winRate: resultsResponse.metrics.win_rate,
          profitFactor: resultsResponse.metrics.profit_factor,
          totalTrades: resultsResponse.metrics.total_trades
        },
        summary: {
          initialCapital: resultsResponse.summary.initial_capital,
          finalValue: resultsResponse.summary.final_value,
          totalPnl: resultsResponse.summary.total_pnl,
          winningTrades: resultsResponse.summary.winning_trades,
          losingTrades: resultsResponse.summary.losing_trades
        }
      });
    }
    
    // Fetch trades
    const tradesResponse = await apiClient.get(`/api/v1/backtests/${backtestId}/trades`);
    if (tradesResponse.success && tradesResponse.trades) {
      const formattedTrades = tradesResponse.trades.map((t: any) => ({
        tradeId: t.trade_id,
        entryTime: t.entry_time,
        exitTime: t.exit_time,
        side: t.side,
        entryPrice: t.entry_price,
        exitPrice: t.exit_price,
        quantity: t.quantity,
        pnl: t.pnl,
        pnlPercent: t.pnl_percent,
        entryReason: t.entry_reason,
        exitReason: t.exit_reason
      }));
      trainModeActions.setBacktestTrades(backtestId, formattedTrades);
    }
    
    // Fetch equity curve
    const equityResponse = await apiClient.get(`/api/v1/backtests/${backtestId}/equity_curve`);
    if (equityResponse.success) {
      trainModeActions.setEquityCurve(backtestId, {
        timestamps: equityResponse.timestamps,
        values: equityResponse.values,
        drawdowns: equityResponse.drawdowns
      });
    }
  } catch (error) {
    logger.error('Failed to fetch backtest results:', error);
  }
}

// React hook for using the train mode store
import { useState, useEffect } from 'react';

export function useTrainModeStore() {
  const [state, setState] = useState(trainModeStore.getState());
  
  useEffect(() => {
    return trainModeStore.subscribe(setState);
  }, []);
  
  return state;
}