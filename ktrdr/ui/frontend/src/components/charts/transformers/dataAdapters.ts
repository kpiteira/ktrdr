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
 * Creates default empty data object when no data is provided
 * 
 * @returns Empty OHLCV data structure
 */
export const createEmptyChartData = (): OHLCVData => {
  return {
    dates: [],
    ohlcv: [],
    metadata: {
      symbol: 'SAMPLE',
      timeframe: '1D',
      start: '',
      end: '',
      points: 0
    }
  };
};

/**
 * Preprocesses data to handle missing values
 * 
 * @param data The OHLCV data to preprocess
 * @returns Preprocessed data with missing values handled
 */
export const preprocessChartData = (data: OHLCVData): OHLCVData => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return createEmptyChartData();
  }

  // Create a copy of the data to avoid mutating the original
  const processedData: OHLCVData = {
    dates: [...data.dates],
    ohlcv: [...data.ohlcv],
    metadata: { ...data.metadata }
  };

  // Check for missing values and handle them
  for (let i = 0; i < processedData.ohlcv.length; i++) {
    const [open, high, low, close, volume] = processedData.ohlcv[i];
    
    // If any price data is missing, use the previous value or a default
    if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
      if (i > 0) {
        // Use previous candle's close as a substitute
        const prevCandle = processedData.ohlcv[i - 1];
        const prevClose = prevCandle[3];
        
        processedData.ohlcv[i] = [
          isNaN(open) ? prevClose : open,
          isNaN(high) ? prevClose : high,
          isNaN(low) ? prevClose : low,
          isNaN(close) ? prevClose : close,
          isNaN(volume) ? 0 : volume
        ];
      } else {
        // For the first candle, use a default value
        processedData.ohlcv[i] = [
          isNaN(open) ? 0 : open,
          isNaN(high) ? 0 : high, 
          isNaN(low) ? 0 : low,
          isNaN(close) ? 0 : close,
          isNaN(volume) ? 0 : volume
        ];
      }
    }
  }

  return processedData;
};

/**
 * Formats time based on timeframe for chart display
 * 
 * @param date Date to format
 * @param timeframe Timeframe string (e.g., '1h', '1D')
 * @returns Formatted time string
 */
export const formatTimeByTimeframe = (date: string | number | Date, timeframe: string): string => {
  const dateObj = typeof date === 'string' ? new Date(date) : 
                  typeof date === 'number' ? new Date(date) : date;
  
  // Format based on timeframe
  if (timeframe.includes('m') || timeframe.includes('h')) {
    // For minute/hour timeframes, include time
    return dateObj.toISOString().replace('T', ' ').substring(0, 16);
  } else {
    // For day timeframes, just use date
    return dateObj.toISOString().split('T')[0];
  }
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
  
  if (!data.dates || !data.ohlcv) {
    errors.push('Data is missing dates or OHLCV arrays');
    return { valid: false, errors };
  }
  
  if (data.dates.length !== data.ohlcv.length) {
    errors.push('Dates and OHLCV arrays have different lengths');
    return { valid: false, errors };
  }
  
  if (data.dates.length === 0) {
    errors.push('Data arrays are empty');
    return { valid: false, errors };
  }
  
  // Check for invalid values
  for (let i = 0; i < data.ohlcv.length; i++) {
    const [open, high, low, close, volume] = data.ohlcv[i];
    
    if (isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
      errors.push(`Invalid price values at index ${i}`);
    }
    
    if (high < low) {
      errors.push(`High is less than low at index ${i}`);
    }
    
    if (isNaN(volume) || volume < 0) {
      errors.push(`Invalid volume at index ${i}`);
    }
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
};