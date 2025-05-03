import { createSelector } from '@reduxjs/toolkit';
import { RootState } from './index';
import type { OHLCVData } from '../types/data';
import type { IndicatorConfig } from '../types/indicators';

// Data selectors
export const selectSymbols = (state: RootState) => state.data.symbols;
export const selectTimeframes = (state: RootState) => state.data.timeframes;
export const selectCurrentSymbol = (state: RootState) => state.data.currentSymbol;
export const selectCurrentTimeframe = (state: RootState) => state.data.currentTimeframe;
export const selectOhlcvData = (state: RootState) => state.data.ohlcvData;
export const selectSymbolsStatus = (state: RootState) => state.data.symbolsStatus;
export const selectTimeframesStatus = (state: RootState) => state.data.timeframesStatus;
export const selectDataStatus = (state: RootState) => state.data.dataStatus;
export const selectDataError = (state: RootState) => state.data.error;

// Indicator selectors
export const selectAvailableIndicators = (state: RootState) => state.indicators.availableIndicators;
export const selectSelectedIndicators = (state: RootState) => state.indicators.selectedIndicators;
export const selectIndicatorData = (state: RootState) => state.indicators.indicatorData;
export const selectIndicatorsLoadingStatus = (state: RootState) => state.indicators.loadingStatus;
export const selectIndicatorsError = (state: RootState) => state.indicators.error;

// UI selectors
export const selectTheme = (state: RootState) => state.ui.theme;
export const selectSidebarOpen = (state: RootState) => state.ui.sidebarOpen;
export const selectCurrentView = (state: RootState) => state.ui.currentView;
export const selectChartSettings = (state: RootState) => state.ui.chartSettings;

// Memoized selectors

// Select a specific indicator's configuration by name
export const selectIndicatorByName = createSelector(
  [selectSelectedIndicators, (_, name: string) => name],
  (indicators, name) => indicators.find((indicator: IndicatorConfig) => indicator.name === name)
);

// Select data for specific indicators
export const selectIndicatorDataByNames = createSelector(
  [selectIndicatorData, (_, names: string[]) => names],
  (indicatorData, names) => {
    const result: Record<string, number[]> = {};
    names.forEach((name: string) => {
      if (indicatorData[name]) {
        result[name] = indicatorData[name];
      }
    });
    return result;
  }
);

// Get formatted data for chart display (combines OHLCV and indicators)
export const selectChartData = createSelector(
  [selectOhlcvData, selectIndicatorData],
  (ohlcvData, indicatorData): { ohlcv: OHLCVData | null, indicators: Record<string, number[]> } => {
    return {
      ohlcv: ohlcvData,
      indicators: indicatorData,
    };
  }
);

// Check if all required data is loaded and ready
export const selectDataReady = createSelector(
  [selectOhlcvData, selectDataStatus, selectSelectedIndicators, selectIndicatorData, selectIndicatorsLoadingStatus],
  (ohlcvData, dataStatus, selectedIndicators, indicatorData, indicatorsLoadingStatus) => {
    // Data is ready if OHLCV data is loaded and any selected indicators have data
    const ohlcvReady = Boolean(ohlcvData) && dataStatus === 'succeeded';
    
    // If no indicators selected, only check OHLCV
    if (selectedIndicators.length === 0) {
      return ohlcvReady;
    }
    
    // Check if all selected indicators have data
    const indicatorsReady = selectedIndicators.every(
      (indicator: IndicatorConfig) => Boolean(indicatorData[indicator.name])
    ) && indicatorsLoadingStatus === 'succeeded';
    
    return ohlcvReady && indicatorsReady;
  }
);

// Check if there is an active data selection
export const selectHasActiveSelection = createSelector(
  [selectCurrentSymbol, selectCurrentTimeframe],
  (symbol, timeframe) => Boolean(symbol && timeframe)
);

// Get loading state for UI display - for backwards compatibility
export const selectCombinedLoadingState = createSelector(
  [selectSymbolsStatus, selectTimeframesStatus, selectDataStatus, selectIndicatorsLoadingStatus],
  (symbolsStatus, timeframesStatus, dataStatus, indicatorsStatus) => {
    if (symbolsStatus === 'loading' || timeframesStatus === 'loading' || 
        dataStatus === 'loading' || indicatorsStatus === 'loading') {
      return 'loading';
    }
    if (symbolsStatus === 'failed' || timeframesStatus === 'failed' || 
        dataStatus === 'failed' || indicatorsStatus === 'failed') {
      return 'failed';
    }
    if ((symbolsStatus === 'succeeded' || symbolsStatus === 'idle') && 
        (timeframesStatus === 'succeeded' || timeframesStatus === 'idle') && 
        (dataStatus === 'succeeded' || dataStatus === 'idle') && 
        (indicatorsStatus === 'succeeded' || indicatorsStatus === 'idle')) {
      return 'succeeded';
    }
    return 'idle';
  }
);

// Get combined error message
export const selectCombinedErrorMessage = createSelector(
  [selectDataError, selectIndicatorsError],
  (dataError, indicatorsError) => {
    if (dataError && indicatorsError) {
      return `Data: ${dataError}, Indicators: ${indicatorsError}`;
    }
    return dataError || indicatorsError || null;
  }
);