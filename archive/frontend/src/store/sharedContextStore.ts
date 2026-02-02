/**
 * Shared context store for communication between Train and Research modes.
 * This store holds context that needs to be preserved when transitioning between modes.
 */

import { createStore } from './createStore';
import { Strategy, Trade } from '../types/trainMode';
import { IndicatorConfig } from './indicatorRegistry';

// Types for backtest context
export interface BacktestContext {
  mode: 'backtest';
  strategy: Strategy;
  symbol: string;
  timeframe: string;
  dateRange: { start: string; end: string };
  indicators: IndicatorConfig[];
  fuzzyConfig: Record<string, any>;
  trades: Trade[];
  backtestId: string;
}

interface SharedContextState {
  backtestContext: BacktestContext | null;
}

// Create the shared context store instance
export const sharedContextStore = createStore<SharedContextState>({
  backtestContext: null
});

// Actions for the shared context store
export const sharedContextActions = {
  setBacktestContext: (context: BacktestContext | null) => {
    sharedContextStore.setState(state => ({
      ...state,
      backtestContext: context
    }));
  },
  
  clearBacktestContext: () => {
    sharedContextStore.setState(state => ({
      ...state,
      backtestContext: null
    }));
  }
};

// React hook for using shared context
import { useState, useEffect } from 'react';

export function useSharedContext() {
  const [state, setState] = useState(sharedContextStore.getState());
  
  useEffect(() => {
    return sharedContextStore.subscribe(setState);
  }, []);
  
  return state;
}