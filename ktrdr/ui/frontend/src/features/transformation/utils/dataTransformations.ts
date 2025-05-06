/**
 * Data transformation utilities
 * Provides functions for transforming API data into formats suitable for UI components
 */

import { OHLCVData, IndicatorData } from '../../../api/types';

/**
 * Candlestick data point for charts
 */
export interface CandlestickDataPoint {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
}

/**
 * Line data point for charts
 */
export interface LineDataPoint {
  time: string | number;
  value: number;
}

/**
 * Bar data point for charts (e.g. volume)
 */
export interface BarDataPoint {
  time: string | number;
  value: number;
  color?: string;
}

/**
 * Convert OHLCV data to candlestick format for charts
 * @param data OHLCV data from the API
 * @returns Array of candlestick data points
 */
export const formatOhlcvData = (data: OHLCVData): CandlestickDataPoint[] => {
  const { dates, ohlcv } = data;
  
  return dates.map((date, index) => {
    const [open, high, low, close] = ohlcv[index];
    
    return {
      time: date,
      open,
      high,
      low,
      close
    };
  });
};

/**
 * Extract volume data from OHLCV data
 * @param data OHLCV data from the API
 * @param greenOnPositive Show green bars for positive price changes (default: true)
 * @returns Array of volume bar data points
 */
export const extractVolumeData = (data: OHLCVData, greenOnPositive = true): BarDataPoint[] => {
  const { dates, ohlcv } = data;
  
  return dates.map((date, index) => {
    const volume = ohlcv[index][4]; // Volume is at index 4
    const open = ohlcv[index][0];
    const close = ohlcv[index][3];
    const isPositive = close >= open;
    const color = greenOnPositive ? 
      (isPositive ? 'rgba(0, 150, 136, 0.8)' : 'rgba(255, 82, 82, 0.8)') : 
      undefined;
    
    return {
      time: date,
      value: volume,
      color
    };
  });
};

/**
 * Convert indicator data to line series format
 * @param data Indicator data from the API
 * @param indicatorName Name of the indicator to extract
 * @returns Array of line data points
 */
export const formatIndicatorData = (data: IndicatorData, indicatorName: string): LineDataPoint[] => {
  const { dates, indicators } = data;
  
  if (!indicators[indicatorName]) {
    return [];
  }
  
  return dates.map((date, index) => ({
    time: date,
    value: indicators[indicatorName][index]
  }));
};

/**
 * Find minimum and maximum values in a data series
 * @param data Array of data points with a value property
 * @returns Object with min and max values
 */
export const findDataExtremes = (data: Array<{ value: number }>): { min: number; max: number } => {
  if (!data.length) {
    return { min: 0, max: 0 };
  }
  
  return data.reduce(
    (extremes, point) => ({
      min: Math.min(extremes.min, point.value),
      max: Math.max(extremes.max, point.value)
    }),
    { min: Infinity, max: -Infinity }
  );
};

/**
 * Check if OHLCV data contains gaps
 * @param data OHLCV data from the API
 * @param timeframeSecs Timeframe in seconds
 * @returns Array of gap ranges { start, end }
 */
export const findDataGaps = (
  data: OHLCVData, 
  timeframeSecs: number
): Array<{ start: string; end: string }> => {
  const { dates } = data;
  const gaps = [];
  
  if (dates.length < 2) {
    return [];
  }
  
  let previousDate = new Date(dates[0]);
  
  for (let i = 1; i < dates.length; i++) {
    const currentDate = new Date(dates[i]);
    const diffSecs = (currentDate.getTime() - previousDate.getTime()) / 1000;
    
    // If the gap is more than 2x the expected time difference
    if (diffSecs > timeframeSecs * 2) {
      gaps.push({
        start: new Date(previousDate.getTime() + timeframeSecs * 1000).toISOString(),
        end: new Date(currentDate.getTime() - timeframeSecs * 1000).toISOString()
      });
    }
    
    previousDate = currentDate;
  }
  
  return gaps;
};

/**
 * Merge multiple indicator datasets
 * @param dataSets Array of indicator data objects
 * @returns Combined indicator data
 */
export const mergeIndicatorData = (dataSets: IndicatorData[]): IndicatorData => {
  if (!dataSets.length) {
    throw new Error('No datasets provided for merging');
  }
  
  const firstDataSet = dataSets[0];
  const mergedIndicators: Record<string, number[]> = {};
  
  // Initialize with first dataset indicators
  Object.keys(firstDataSet.indicators).forEach(key => {
    mergedIndicators[key] = [...firstDataSet.indicators[key]];
  });
  
  // Merge in other datasets
  for (let i = 1; i < dataSets.length; i++) {
    const dataset = dataSets[i];
    
    Object.keys(dataset.indicators).forEach(key => {
      if (!mergedIndicators[key]) {
        mergedIndicators[key] = [...dataset.indicators[key]];
      } else {
        // Handle duplicates - this is simplistic and assumes same date order
        console.warn(`Duplicate indicator key found when merging: ${key}`);
      }
    });
  }
  
  return {
    dates: firstDataSet.dates,
    indicators: mergedIndicators,
    metadata: firstDataSet.metadata
  };
};