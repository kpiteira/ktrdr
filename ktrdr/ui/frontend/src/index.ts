// Re-export the app's store and related types
export { store, type RootState, type AppDispatch } from './app/store';

// Re-export app-level components
export { ThemeProvider, useTheme } from './app';

// Re-export feature-level components
export { DataSelectionContainer, useSymbolSelection } from './features/symbols';
export { useChartData, useIndicators } from './features/charting';

// Export central hooks that abstract away implementation details
export {
  useAppDispatch,
  useAppSelector,
  // Legacy hooks (compatibility aliases)
  useDataSelection,
  useOhlcvData,
  useThemeControl
} from './hooks';