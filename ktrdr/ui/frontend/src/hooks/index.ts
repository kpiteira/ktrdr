/**
 * React hooks index
 * Centralizes exports of all hooks
 */

// Re-export Redux hooks
import { useDispatch, useSelector } from 'react-redux';
import type { TypedUseSelectorHook } from 'react-redux';
import type { RootState, AppDispatch } from '../store';

// Import feature-specific hooks
import { useSymbolSelection } from '../features/symbols/hooks/useSymbolSelection';
import { useChartData } from '../features/charting/hooks/useChartData';
import { useIndicators } from '../features/charting/hooks/useIndicators';
import { useUI } from '../app/hooks/useUI';

// Use these typed versions throughout the app instead of plain useDispatch and useSelector
export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

// Re-export all feature-specific hooks
export {
  useSymbolSelection,
  useChartData,
  useIndicators,
  useUI
};

// Renamed for backward compatibility
export const useDataSelection = useSymbolSelection;
export const useOhlcvData = useChartData;
export const useThemeControl = useUI;