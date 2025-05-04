/**
 * Chart utilities index file
 * Exports all chart-related utility functions and types
 */

// Import and re-export specific functions from chartUtils.ts
import {
  createChartOptions,
  createCandlestickOptions,
  createLineOptions,
  createHistogramOptions,
  // formatCandlestickData, - removed to avoid conflict
  formatVolumeData,
  createPriceLine,
  handleChartResize,
  cleanupChart
} from './chartUtils';

// Import and re-export specific functions from chartDataUtils.ts
import {
  TIME_FORMAT,
  DataFormat,
  DEFAULT_COLORS,
  detectTimeFormat,
  convertToChartTime,
  formatTimeForDisplay,
  getTimeFormatForTimeframe,
  formatCandlestickData, // Use this version only
  formatLineData,
  formatHistogramData,
  formatBarData,
  preprocessData,
  validateData,
  createUpdateData,
  debugInspectData,
  createTestData
} from './chartDataUtils';

// Re-export from other modules
export * from './chartFactory';
export * from './performanceUtils';
export * from './updatesManager';
export * from './dataValidation';
export * from './debugUtils';

// Re-export all the named imports to maintain the public API
export {
  // From chartUtils.ts
  createChartOptions,
  createCandlestickOptions,
  createLineOptions,
  createHistogramOptions,
  formatVolumeData,
  createPriceLine,
  handleChartResize,
  cleanupChart,
  
  // From chartDataUtils.ts
  TIME_FORMAT,
  DataFormat,
  DEFAULT_COLORS,
  detectTimeFormat,
  convertToChartTime,
  formatTimeForDisplay,
  getTimeFormatForTimeframe,
  formatCandlestickData, // Only export the version from chartDataUtils
  formatLineData,
  formatHistogramData,
  formatBarData,
  preprocessData,
  validateData,
  createUpdateData,
  debugInspectData,
  createTestData
};