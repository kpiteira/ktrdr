import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import { useCallback } from 'react';
import type { RootState, AppDispatch } from '../store';
import { 
  fetchData, 
  fetchSymbols, 
  fetchTimeframes, 
  setCurrentSymbol, 
  setCurrentTimeframe, 
  clearData 
} from '../store/slices/dataSlice';
import {
  fetchAvailableIndicators,
  calculateIndicatorData,
  addIndicator,
  removeIndicator,
  updateIndicator,
  clearIndicators
} from '../store/slices/indicatorSlice';
import {
  setTheme,
  toggleSidebar,
  updateChartSettings
} from '../store/slices/uiSlice';
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
} from '../store/selectors';
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

  const setSymbol = useCallback((symbol: string) => {
    dispatch(setCurrentSymbol(symbol));
  }, [dispatch]);

  const setTimeframe = useCallback((timeframe: string) => {
    dispatch(setCurrentTimeframe(timeframe));
  }, [dispatch]);

  return {
    symbols,
    timeframes,
    currentSymbol,
    currentTimeframe,
    setSymbol,
    setTimeframe,
  };
};

export const useOhlcvData = () => {
  const dispatch = useAppDispatch();
  const ohlcvData = useAppSelector(selectOhlcvData);

  const fetchOhlcvData = useCallback(() => {
    dispatch(fetchData());
  }, [dispatch]);

  return {
    ohlcvData,
    fetchOhlcvData,
  };
};

// Indicator hooks
export const useIndicators = () => {
  const dispatch = useAppDispatch();
  const availableIndicators = useAppSelector(selectAvailableIndicators);
  const selectedIndicators = useAppSelector(selectSelectedIndicators);

  const addNewIndicator = useCallback((indicator: IndicatorConfig) => {
    dispatch(addIndicator(indicator));
  }, [dispatch]);

  const removeExistingIndicator = useCallback((indicatorName: string) => {
    dispatch(removeIndicator(indicatorName));
  }, [dispatch]);

  const updateExistingIndicator = useCallback((indicator: IndicatorConfig) => {
    dispatch(updateIndicator(indicator));
  }, [dispatch]);

  return {
    availableIndicators,
    selectedIndicators,
    addNewIndicator,
    removeExistingIndicator,
    updateExistingIndicator,
  };
};

// Get a specific indicator by name
export const useIndicator = (name: string) => {
  return useAppSelector((state) => selectIndicatorByName(state, name));
};

// Chart data hook
export const useChartData = () => {
  const chartData = useAppSelector(selectChartData);
  return chartData;
};

// UI hooks
export const useThemeControl = () => {
  const dispatch = useAppDispatch();
  const theme = useAppSelector(selectTheme);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    dispatch(setTheme(mode));
  }, [dispatch]);

  return {
    theme,
    setThemeMode,
  };
};

export const useSidebarControl = () => {
  const dispatch = useAppDispatch();
  const sidebarOpen = useAppSelector(selectSidebarOpen);

  const toggleSidebarVisibility = useCallback(() => {
    dispatch(toggleSidebar());
  }, [dispatch]);

  return {
    sidebarOpen,
    toggleSidebarVisibility,
  };
};

export const useChartSettingsControl = () => {
  const dispatch = useAppDispatch();
  const chartSettings = useAppSelector(selectChartSettings);

  const updateSettings = useCallback((settings: any) => {
    dispatch(updateChartSettings(settings));
  }, [dispatch]);

  return {
    chartSettings,
    updateSettings,
  };
};