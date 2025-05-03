import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import { useCallback } from 'react';
import type { RootState, AppDispatch } from './';
import { 
  fetchData, 
  fetchSymbols, 
  fetchTimeframes, 
  setCurrentSymbol, 
  setCurrentTimeframe, 
  clearData 
} from './slices/dataSlice';
import {
  fetchAvailableIndicators,
  calculateIndicatorData,
  addIndicator,
  removeIndicator,
  updateIndicator,
  clearIndicators
} from './slices/indicatorSlice';
import {
  setTheme,
  toggleSidebar,
  updateChartSettings
} from './slices/uiSlice';
import {
  selectDataReady,
  selectHasActiveSelection,
  selectCombinedLoadingState,
  selectCombinedErrorMessage,
  selectChartData,
  selectIndicatorByName,
  selectSymbols,
  selectTimeframes,
  selectCurrentSymbol,
  selectCurrentTimeframe,
  selectOhlcvData,
  selectAvailableIndicators,
  selectSelectedIndicators,
  selectTheme,
  selectChartSettings,
  selectSidebarOpen,
  selectSymbolsStatus,
  selectTimeframesStatus,
  selectDataStatus
} from './selectors';
import type { ThemeMode } from '../types/ui';
import type { IndicatorConfig } from '../types/indicators';

// Basic hooks
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

// Data management hooks
export const useDataSelection = () => {
  const dispatch = useAppDispatch();
  const symbols = useAppSelector(selectSymbols);
  const timeframes = useAppSelector(selectTimeframes);
  const currentSymbol = useAppSelector(selectCurrentSymbol);
  const currentTimeframe = useAppSelector(selectCurrentTimeframe);
  const hasActiveSelection = useAppSelector(selectHasActiveSelection);
  
  // Fetch available symbols and timeframes
  const loadMetadata = useCallback(() => {
    dispatch(fetchSymbols());
    dispatch(fetchTimeframes());
  }, [dispatch]);
  
  // Set selected symbol
  const selectSymbol = useCallback((symbol: string | null) => {
    dispatch(setCurrentSymbol(symbol));
  }, [dispatch]);
  
  // Set selected timeframe
  const selectTimeframe = useCallback((timeframe: string | null) => {
    dispatch(setCurrentTimeframe(timeframe));
  }, [dispatch]);
  
  return {
    symbols,
    timeframes,
    currentSymbol,
    currentTimeframe,
    hasActiveSelection,
    loadMetadata,
    selectSymbol,
    selectTimeframe
  };
};

export const useOhlcvData = () => {
  const dispatch = useAppDispatch();
  const ohlcvData = useAppSelector(selectOhlcvData);
  const symbolsStatus = useAppSelector(selectSymbolsStatus);
  const timeframesStatus = useAppSelector(selectTimeframesStatus);
  const dataStatus = useAppSelector(selectDataStatus);
  const errorMessage = useAppSelector(selectCombinedErrorMessage);
  const currentSymbol = useAppSelector(selectCurrentSymbol);
  const currentTimeframe = useAppSelector(selectCurrentTimeframe);
  
  // Load OHLCV data for the selected symbol and timeframe
  const loadData = useCallback((options?: { startDate?: string; endDate?: string }) => {
    if (!currentSymbol || !currentTimeframe) return;
    
    dispatch(fetchData({
      symbol: currentSymbol,
      timeframe: currentTimeframe,
      startDate: options?.startDate,
      endDate: options?.endDate
    }));
  }, [dispatch, currentSymbol, currentTimeframe]);
  
  // Clear loaded data
  const resetData = useCallback(() => {
    dispatch(clearData());
  }, [dispatch]);
  
  return {
    ohlcvData,
    symbolsStatus,
    timeframesStatus,
    dataStatus,
    loadingState: dataStatus, // For backward compatibility
    errorMessage,
    loadData,
    resetData
  };
};

// Indicator hooks
export const useIndicators = () => {
  const dispatch = useAppDispatch();
  const availableIndicators = useAppSelector(selectAvailableIndicators);
  const selectedIndicators = useAppSelector(selectSelectedIndicators);
  const loadingState = useAppSelector(selectCombinedLoadingState);
  const errorMessage = useAppSelector(selectCombinedErrorMessage);
  const currentSymbol = useAppSelector(selectCurrentSymbol);
  const currentTimeframe = useAppSelector(selectCurrentTimeframe);
  
  // Load available indicators
  const loadAvailableIndicators = useCallback(() => {
    dispatch(fetchAvailableIndicators());
  }, [dispatch]);
  
  // Add an indicator to the selected list
  const addSelectedIndicator = useCallback((indicator: IndicatorConfig) => {
    dispatch(addIndicator(indicator));
  }, [dispatch]);
  
  // Remove an indicator from the selected list
  const removeSelectedIndicator = useCallback((name: string) => {
    dispatch(removeIndicator(name));
  }, [dispatch]);
  
  // Update an indicator's configuration
  const updateSelectedIndicator = useCallback((name: string, config: Partial<IndicatorConfig>) => {
    dispatch(updateIndicator({ name, config }));
  }, [dispatch]);
  
  // Clear all selected indicators
  const clearSelectedIndicators = useCallback(() => {
    dispatch(clearIndicators());
  }, [dispatch]);
  
  // Calculate indicators for the selected symbol and timeframe
  const calculateIndicators = useCallback(() => {
    if (!currentSymbol || !currentTimeframe || selectedIndicators.length === 0) return;
    
    dispatch(calculateIndicatorData({
      symbol: currentSymbol,
      timeframe: currentTimeframe,
      indicators: selectedIndicators
    }));
  }, [dispatch, currentSymbol, currentTimeframe, selectedIndicators]);
  
  return {
    availableIndicators,
    selectedIndicators,
    loadingState,
    errorMessage,
    loadAvailableIndicators,
    addSelectedIndicator,
    removeSelectedIndicator,
    updateSelectedIndicator,
    clearSelectedIndicators,
    calculateIndicators
  };
};

// Get a specific indicator by name
export const useIndicator = (name: string) => {
  return useAppSelector((state) => selectIndicatorByName(state, name));
};

// Chart data hook
export const useChartData = () => {
  const chartData = useAppSelector(selectChartData);
  const dataReady = useAppSelector(selectDataReady);
  const loadingState = useAppSelector(selectCombinedLoadingState);
  const errorMessage = useAppSelector(selectCombinedErrorMessage);
  
  return {
    data: chartData,
    ready: dataReady,
    loading: loadingState === 'loading',
    error: errorMessage
  };
};

// UI hooks
export const useThemeControl = () => {
  const dispatch = useAppDispatch();
  const theme = useAppSelector(selectTheme);
  
  const toggleTheme = useCallback(() => {
    dispatch(setTheme(theme === 'light' ? 'dark' : 'light'));
  }, [dispatch, theme]);
  
  const setThemeMode = useCallback((mode: ThemeMode) => {
    dispatch(setTheme(mode));
  }, [dispatch]);
  
  return {
    theme,
    toggleTheme,
    setThemeMode
  };
};

export const useSidebarControl = () => {
  const dispatch = useAppDispatch();
  const isOpen = useAppSelector(selectSidebarOpen);
  
  const toggle = useCallback(() => {
    dispatch(toggleSidebar());
  }, [dispatch]);
  
  return {
    isOpen,
    toggle
  };
};

export const useChartSettingsControl = () => {
  const dispatch = useAppDispatch();
  const chartSettings = useAppSelector(selectChartSettings);
  
  const updateSettings = useCallback((settings: Partial<typeof chartSettings>) => {
    dispatch(updateChartSettings(settings));
  }, [dispatch]);
  
  return {
    settings: chartSettings,
    updateSettings
  };
};