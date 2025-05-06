import { OHLCVData } from '../../../types/data';
import { formatDateForChart } from './indicatorAdapters';

/**
 * Transforms OHLCV data into format suitable for TradingView candlestick chart
 * 
 * @param data The OHLCV data to transform
 * @returns Array of candlestick data objects formatted for TradingView
 */
export const formatCandlestickData = (data: OHLCVData) => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, high, low, close, _volume] = data.ohlcv[index];
    
    return {
      time: formatDateForChart(date),
      open,
      high,
      low,
      close,
    };
  });
};

/**
 * Transforms OHLCV data into format suitable for volume histogram
 * 
 * @param data The OHLCV data to transform
 * @returns Array of volume data objects with color based on price movement
 */
export const formatVolumeData = (data: OHLCVData) => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, _high, _low, close, volume] = data.ohlcv[index];
    
    return {
      time: formatDateForChart(date),
      value: volume,
      color: close >= open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    };
  });
};

/**
 * Validates chart data to prevent rendering errors
 * 
 * @param data The OHLCV data to validate
 * @returns Object with validation result and errors if any
 */
export const validateChartData = (data: OHLCVData): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  if (!data) {
    errors.push('Data is undefined or null');
    return { valid: false, errors };
  }
  
  if (!data.dates || data.dates.length === 0) {
    errors.push('Dates array is empty or undefined');
  }
  
  if (!data.ohlcv || data.ohlcv.length === 0) {
    errors.push('OHLCV array is empty or undefined');
  }
  
  if (data.dates && data.ohlcv && data.dates.length !== data.ohlcv.length) {
    errors.push('Dates and OHLCV arrays have different lengths');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
};