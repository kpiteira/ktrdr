/**
 * Chart components index - Exports reusable chart components and utilities
 */

// Export core components
import CandlestickTradingView from './core/CandlestickTradingView';
import CandlestickChart from './core/CandlestickChart';
export { CandlestickTradingView, CandlestickChart };

// Export chart controls and UI components
import { ChartToolbar, TimeNavigation, ChartOptions } from './core/ChartControls';
import { CrosshairContainer, PriceLabel } from './core/CrosshairInfo';
import { LegendContainer, LegendItem } from './core/ChartLegend';
export { 
  ChartToolbar, 
  TimeNavigation, 
  ChartOptions,
  CrosshairContainer,
  PriceLabel,
  LegendContainer,
  LegendItem
};

// Export types
export type { ChartCustomizableOptions } from './core/ChartControls/ChartOptions';
export type { CrosshairData } from './core/CrosshairInfo/CrosshairContainer';
export type { LegendItemData } from './core/ChartLegend/LegendContainer';

// Export transformers (data utilities)
import * as dataAdapters from './transformers/dataAdapters';
import * as timeFormatters from './transformers/timeFormatters';
export { dataAdapters, timeFormatters };

// Default export for backward compatibility
export default {
  CandlestickTradingView,
  CandlestickChart,
  dataAdapters,
  timeFormatters
};