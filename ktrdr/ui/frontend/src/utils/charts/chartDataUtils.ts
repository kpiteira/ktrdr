/**
 * Chart data transformation utilities
 * 
 * This module provides utilities for transforming OHLCV data into various chart formats,
 * handling time scales, preprocessing data, and providing validation.
 */
import {
  CandlestickData,
  LineData,
  HistogramData,
  BarData,
  Time,
  BusinessDay,
  UTCTimestamp
} from 'lightweight-charts';
import { OHLCVData, OHLCVPoint } from '../../types/data';

// Time format constants
export const TIME_FORMAT = {
  MONTH_DAY_YEAR: 'MM/DD/YYYY',
  DAY_MONTH_YEAR: 'DD/MM/YYYY',
  YEAR_MONTH_DAY: 'YYYY-MM-DD',
  HOUR_MINUTE: 'HH:mm',
  HOUR_MINUTE_SECOND: 'HH:mm:ss',
  MONTH_DAY_HOUR_MINUTE: 'MM/DD HH:mm',
  ISO: 'ISO', // ISO 8601 format
  UNIX: 'UNIX' // Unix timestamp
};

// Chart data formats
export enum DataFormat {
  CANDLESTICK = 'candlestick',
  LINE = 'line',
  AREA = 'area',
  BAR = 'bar',
  HISTOGRAM = 'histogram'
}

/**
 * Default colors for chart elements
 */
export const DEFAULT_COLORS = {
  CANDLE_UP: 'rgba(38, 166, 154, 1)',
  CANDLE_DOWN: 'rgba(239, 83, 80, 1)',
  VOLUME_UP: 'rgba(38, 166, 154, 0.5)',
  VOLUME_DOWN: 'rgba(239, 83, 80, 0.5)',
  LINE: 'rgba(41, 98, 255, 1)',
  HISTOGRAM: 'rgba(38, 166, 154, 0.5)',
};

/**
 * Detects the time scale format from a date string or number
 * @param time Date/time value in various formats
 * @returns Detected time format or null if unable to determine
 */
export const detectTimeFormat = (time: string | number): string | null => {
  if (typeof time === 'number') {
    // Check if it's a Unix timestamp (seconds)
    if (time > 1000000000 && time < 10000000000) {
      return TIME_FORMAT.UNIX;
    }
    // Or milliseconds
    if (time > 1000000000000 && time < 10000000000000) {
      return TIME_FORMAT.UNIX;
    }
  }
  
  if (typeof time === 'string') {
    // Check ISO format
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/.test(time)) {
      return TIME_FORMAT.ISO;
    }
    
    // Check YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(time)) {
      return TIME_FORMAT.YEAR_MONTH_DAY;
    }
    
    // Check MM/DD/YYYY
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(time)) {
      return TIME_FORMAT.MONTH_DAY_YEAR;
    }
    
    // Check DD/MM/YYYY
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(time)) {
      // Note: This is ambiguous with MM/DD/YYYY
      // May need additional logic to determine
      return TIME_FORMAT.DAY_MONTH_YEAR;
    }
  }
  
  return null;
};

/**
 * Converts a time value to Lightweight Charts time format
 * @param time Time in various formats (string or number)
 * @param format Optional explicit format
 * @returns Time in Lightweight Charts format (UTCTimestamp or BusinessDay)
 */
export const convertToChartTime = (time: string | number, format?: string): Time => {
  // Detect format if not provided
  const timeFormat = format || detectTimeFormat(time) || TIME_FORMAT.ISO;
  
  if (typeof time === 'number') {
    // For Unix timestamps, make sure it's in seconds for Lightweight Charts
    if (time > 1000000000000) {
      // If in milliseconds, convert to seconds
      return Math.floor(time / 1000) as UTCTimestamp;
    }
    return time as UTCTimestamp;
  }
  
  if (typeof time === 'string') {
    switch (timeFormat) {
      case TIME_FORMAT.ISO:
        // Convert ISO string to timestamp in seconds
        return Math.floor(new Date(time).getTime() / 1000) as UTCTimestamp;
      
      case TIME_FORMAT.YEAR_MONTH_DAY:
        // Convert YYYY-MM-DD to BusinessDay
        const [year, month, day] = time.split('-').map(Number);
        return { year, month, day } as BusinessDay;
      
      default:
        // Default to timestamp conversion
        return Math.floor(new Date(time).getTime() / 1000) as UTCTimestamp;
    }
  }
  
  // Fallback to current time if input is invalid
  console.warn('Invalid time format, using current time as fallback');
  return Math.floor(Date.now() / 1000) as UTCTimestamp;
};

/**
 * Formats time for display based on timeframe and format preferences
 * @param time Time in Lightweight Charts format
 * @param timeframe Chart timeframe (e.g., '1m', '1h', '1d')
 * @param format Desired output format
 * @returns Formatted time string
 */
export const formatTimeForDisplay = (
  time: Time,
  timeframe: string,
  format: string = TIME_FORMAT.MONTH_DAY_YEAR
): string => {
  // Convert Time to JavaScript Date
  let date: Date;
  
  if (typeof time === 'number') {
    // UTCTimestamp in seconds
    date = new Date(time * 1000);
  } else if (typeof time === 'object' && 'year' in time) {
    // BusinessDay format
    date = new Date(time.year, time.month - 1, time.day);
  } else {
    throw new Error('Unsupported time format');
  }
  
  // Format based on timeframe and desired format
  switch (format) {
    case TIME_FORMAT.MONTH_DAY_YEAR:
      return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
    
    case TIME_FORMAT.DAY_MONTH_YEAR:
      return `${date.getDate()}/${date.getMonth() + 1}/${date.getFullYear()}`;
    
    case TIME_FORMAT.YEAR_MONTH_DAY:
      return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    
    case TIME_FORMAT.HOUR_MINUTE:
      return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    
    case TIME_FORMAT.HOUR_MINUTE_SECOND:
      return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
    
    case TIME_FORMAT.MONTH_DAY_HOUR_MINUTE:
      return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
    
    case TIME_FORMAT.ISO:
      return date.toISOString();
    
    default:
      return date.toLocaleString();
  }
};

/**
 * Calculates appropriate time formatter based on timeframe
 * @param timeframe Chart timeframe (e.g., '1m', '1h', '1d')
 * @returns Appropriate time format for the timeframe
 */
export const getTimeFormatForTimeframe = (timeframe: string): string => {
  // Extract the time unit (m, h, d, w, M, y)
  const unit = timeframe.slice(-1).toLowerCase();
  
  switch (unit) {
    case 'm': // minute
      return TIME_FORMAT.HOUR_MINUTE;
    
    case 'h': // hour
      return TIME_FORMAT.MONTH_DAY_HOUR_MINUTE;
    
    case 'd': // day
      return TIME_FORMAT.MONTH_DAY_YEAR;
    
    case 'w': // week
    case 'M': // month (note: using 'M' for month, 'm' for minute)
    case 'y': // year
      return TIME_FORMAT.MONTH_DAY_YEAR;
    
    default:
      return TIME_FORMAT.MONTH_DAY_YEAR;
  }
};

/**
 * Converts OHLCV data to candlestick format
 * @param data OHLCV data
 * @returns Formatted candlestick data
 */
export const formatCandlestickData = (data: OHLCVData): CandlestickData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, high, low, close, _volume] = data.ohlcv[index];
    
    return {
      time: convertToChartTime(date),
      open,
      high,
      low,
      close,
    };
  });
};

/**
 * Converts OHLCV data to line format (using close prices)
 * @param data OHLCV data
 * @param valueField Which value from OHLCV to use ('open', 'high', 'low', 'close', 'volume')
 * @returns Formatted line data
 */
export const formatLineData = (
  data: OHLCVData, 
  valueField: keyof OHLCVPoint = 'close'
): LineData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  const fieldIndices: Record<keyof OHLCVPoint, number> = {
    open: 0,
    high: 1,
    low: 2,
    close: 3,
    volume: 4
  };

  const fieldIndex = fieldIndices[valueField];

  return data.dates.map((date, index) => {
    return {
      time: convertToChartTime(date),
      value: data.ohlcv[index][fieldIndex]
    };
  });
};

/**
 * Converts OHLCV data to histogram format
 * @param data OHLCV data
 * @param valueField Which value from OHLCV to use (default is 'volume')
 * @param positiveColor Color for positive bars (close > open)
 * @param negativeColor Color for negative bars (close < open)
 * @returns Formatted histogram data
 */
export const formatHistogramData = (
  data: OHLCVData,
  valueField: keyof OHLCVPoint = 'volume',
  positiveColor: string = DEFAULT_COLORS.VOLUME_UP,
  negativeColor: string = DEFAULT_COLORS.VOLUME_DOWN
): HistogramData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  const fieldIndices: Record<keyof OHLCVPoint, number> = {
    open: 0,
    high: 1,
    low: 2,
    close: 3,
    volume: 4
  };

  const valueIndex = fieldIndices[valueField];

  return data.dates.map((date, index) => {
    const [open, _high, _low, close, _volume] = data.ohlcv[index];
    const value = data.ohlcv[index][valueIndex];
    
    return {
      time: convertToChartTime(date),
      value,
      color: close >= open ? positiveColor : negativeColor,
    };
  });
};

/**
 * Converts OHLCV data to bar format
 * @param data OHLCV data
 * @returns Formatted bar data
 */
export const formatBarData = (data: OHLCVData): BarData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, high, low, close, _volume] = data.ohlcv[index];
    
    return {
      time: convertToChartTime(date),
      open,
      high,
      low,
      close,
    };
  });
};

/**
 * Preprocesses data to handle missing values
 * @param data OHLCV data
 * @param fillMethod Method to fill missing values ('previous', 'linear', 'zero', 'none')
 * @returns Processed data with missing values handled
 */
export const preprocessData = (
  data: OHLCVData,
  fillMethod: 'previous' | 'linear' | 'zero' | 'none' = 'previous'
): OHLCVData => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return data;
  }

  // Create a copy of the data to avoid mutating the original
  const processedData: OHLCVData = {
    dates: [...data.dates],
    ohlcv: [...data.ohlcv.map(arr => [...arr])],
    metadata: { ...data.metadata }
  };

  if (fillMethod === 'none') {
    return processedData;
  }

  for (let i = 0; i < processedData.ohlcv.length; i++) {
    const [open, high, low, close, volume] = processedData.ohlcv[i];
    
    // Check if any OHLC value is missing (null, undefined, NaN)
    const missingOHLC = [open, high, low, close].some(val => 
      val === null || val === undefined || Number.isNaN(val));
    
    // Check if volume is missing
    const missingVolume = volume === null || volume === undefined || Number.isNaN(volume);
    
    if (missingOHLC || missingVolume) {
      switch (fillMethod) {
        case 'zero':
          // Fill with zeros
          if (missingOHLC) {
            processedData.ohlcv[i][0] = open || 0; // open
            processedData.ohlcv[i][1] = high || 0; // high
            processedData.ohlcv[i][2] = low || 0;  // low
            processedData.ohlcv[i][3] = close || 0; // close
          }
          if (missingVolume) {
            processedData.ohlcv[i][4] = 0; // volume
          }
          break;
          
        case 'previous':
          // Fill with previous values if available
          if (i > 0) {
            const prevValues = processedData.ohlcv[i-1];
            
            if (missingOHLC) {
              processedData.ohlcv[i][0] = open || prevValues[0]; // open
              processedData.ohlcv[i][1] = high || prevValues[1]; // high
              processedData.ohlcv[i][2] = low || prevValues[2];  // low
              processedData.ohlcv[i][3] = close || prevValues[3]; // close
            }
            if (missingVolume) {
              processedData.ohlcv[i][4] = prevValues[4]; // volume
            }
          } else {
            // No previous value available, use zero
            if (missingOHLC) {
              processedData.ohlcv[i][0] = open || 0; // open
              processedData.ohlcv[i][1] = high || 0; // high
              processedData.ohlcv[i][2] = low || 0;  // low
              processedData.ohlcv[i][3] = close || 0; // close
            }
            if (missingVolume) {
              processedData.ohlcv[i][4] = 0; // volume
            }
          }
          break;
          
        case 'linear':
          // Linear interpolation requires values before and after
          // We'll only do this if we have both prev and next values
          if (i > 0 && i < processedData.ohlcv.length - 1) {
            const prevValues = processedData.ohlcv[i-1];
            const nextValues = processedData.ohlcv[i+1];
            
            if (missingOHLC) {
              for (let j = 0; j < 4; j++) {
                if (processedData.ohlcv[i][j] === null || 
                    processedData.ohlcv[i][j] === undefined || 
                    Number.isNaN(processedData.ohlcv[i][j])) {
                  // Linear interpolation: prevValue + (nextValue - prevValue) * 0.5
                  processedData.ohlcv[i][j] = prevValues[j] + (nextValues[j] - prevValues[j]) * 0.5;
                }
              }
            }
            if (missingVolume) {
              processedData.ohlcv[i][4] = prevValues[4] + (nextValues[4] - prevValues[4]) * 0.5;
            }
          } else {
            // Fallback to previous method if we can't do linear interpolation
            if (i > 0) {
              const prevValues = processedData.ohlcv[i-1];
              
              if (missingOHLC) {
                processedData.ohlcv[i][0] = open || prevValues[0]; // open
                processedData.ohlcv[i][1] = high || prevValues[1]; // high
                processedData.ohlcv[i][2] = low || prevValues[2];  // low
                processedData.ohlcv[i][3] = close || prevValues[3]; // close
              }
              if (missingVolume) {
                processedData.ohlcv[i][4] = prevValues[4]; // volume
              }
            } else {
              // No previous value available, use next value if available
              if (i < processedData.ohlcv.length - 1) {
                const nextValues = processedData.ohlcv[i+1];
                
                if (missingOHLC) {
                  processedData.ohlcv[i][0] = open || nextValues[0]; // open
                  processedData.ohlcv[i][1] = high || nextValues[1]; // high
                  processedData.ohlcv[i][2] = low || nextValues[2];  // low
                  processedData.ohlcv[i][3] = close || nextValues[3]; // close
                }
                if (missingVolume) {
                  processedData.ohlcv[i][4] = nextValues[4]; // volume
                }
              } else {
                // Neither previous nor next available, use zero
                if (missingOHLC) {
                  processedData.ohlcv[i][0] = open || 0; // open
                  processedData.ohlcv[i][1] = high || 0; // high
                  processedData.ohlcv[i][2] = low || 0;  // low
                  processedData.ohlcv[i][3] = close || 0; // close
                }
                if (missingVolume) {
                  processedData.ohlcv[i][4] = 0; // volume
                }
              }
            }
          }
          break;
      }
    }
  }

  return processedData;
};

/**
 * Validates OHLCV data and returns issues found
 * @param data OHLCV data to validate
 * @returns Validation result with array of issues
 */
export const validateData = (data: OHLCVData): { valid: boolean; issues: string[] } => {
  const issues: string[] = [];
  
  // Check if data is defined
  if (!data) {
    issues.push('Data is undefined or null');
    return { valid: false, issues };
  }
  
  // Check for required properties
  if (!data.dates) {
    issues.push('Data missing "dates" property');
  }
  
  if (!data.ohlcv) {
    issues.push('Data missing "ohlcv" property');
  }
  
  if (!data.metadata) {
    issues.push('Data missing "metadata" property');
  }
  
  // If any required property is missing, no need to validate further
  if (issues.length > 0) {
    return { valid: false, issues };
  }
  
  // Check array lengths match
  if (data.dates.length !== data.ohlcv.length) {
    issues.push(`Array length mismatch: dates (${data.dates.length}) vs ohlcv (${data.ohlcv.length})`);
  }
  
  // Check data property types
  if (!Array.isArray(data.dates)) {
    issues.push('Property "dates" is not an array');
  }
  
  if (!Array.isArray(data.ohlcv)) {
    issues.push('Property "ohlcv" is not an array');
  }
  
  // Validate date values
  for (let i = 0; i < data.dates.length; i++) {
    const date = data.dates[i];
    if (typeof date !== 'string' && typeof date !== 'number') {
      issues.push(`Invalid date at index ${i}: ${String(date)}`);
    }
    if (typeof date === 'string') {
      const timestamp = new Date(date).getTime();
      if (isNaN(timestamp)) {
        issues.push(`Invalid date string at index ${i}: "${date}"`);
      }
    }
  }
  
  // Validate OHLCV data structure
  for (let i = 0; i < data.ohlcv.length; i++) {
    const ohlcv = data.ohlcv[i];
    
    if (!Array.isArray(ohlcv)) {
      issues.push(`OHLCV data at index ${i} is not an array`);
      continue;
    }
    
    if (ohlcv.length !== 5) {
      issues.push(`OHLCV data at index ${i} has incorrect length: ${ohlcv.length} (expected 5)`);
    }
    
    // Check for non-numeric values
    for (let j = 0; j < ohlcv.length; j++) {
      if (typeof ohlcv[j] !== 'number' || isNaN(ohlcv[j])) {
        const field = ['open', 'high', 'low', 'close', 'volume'][j];
        issues.push(`Non-numeric ${field} value at index ${i}: ${ohlcv[j]}`);
      }
    }
    
    // Check OHLC relationships
    if (ohlcv[1] < ohlcv[0] || ohlcv[1] < ohlcv[2] || ohlcv[1] < ohlcv[3]) {
      issues.push(`Invalid OHLC at index ${i}: high (${ohlcv[1]}) is not the highest value`);
    }
    
    if (ohlcv[2] > ohlcv[0] || ohlcv[2] > ohlcv[1] || ohlcv[2] > ohlcv[3]) {
      issues.push(`Invalid OHLC at index ${i}: low (${ohlcv[2]}) is not the lowest value`);
    }
    
    // Check for negative volume
    if (ohlcv[4] < 0) {
      issues.push(`Negative volume at index ${i}: ${ohlcv[4]}`);
    }
  }
  
  // Validate metadata
  if (data.metadata) {
    if (!data.metadata.symbol) {
      issues.push('Metadata missing "symbol" property');
    }
    
    if (!data.metadata.timeframe) {
      issues.push('Metadata missing "timeframe" property');
    }
    
    if (data.metadata.points !== data.dates.length) {
      issues.push(`Metadata "points" (${data.metadata.points}) doesn't match actual data length (${data.dates.length})`);
    }
  }
  
  return {
    valid: issues.length === 0,
    issues
  };
};

/**
 * Creates an optimized subset of data for real-time updates
 * @param existingData Existing chart data
 * @param newData New data to merge
 * @param maxPoints Maximum number of points to include (0 for no limit)
 * @returns Optimized data for efficient updates
 */
export const createUpdateData = (
  existingData: OHLCVData,
  newData: OHLCVData,
  maxPoints: number = 0
): OHLCVData => {
  if (!existingData || !newData) {
    return newData || existingData || { dates: [], ohlcv: [], metadata: {} as any };
  }
  
  // Create a new data object for the update
  const updateData: OHLCVData = {
    dates: [...existingData.dates],
    ohlcv: [...existingData.ohlcv],
    metadata: { ...newData.metadata } // Use updated metadata
  };
  
  // Find new data points that aren't in existing data
  const lastExistingDate = existingData.dates[existingData.dates.length - 1];
  let lastExistingTimestamp: number;
  
  if (typeof lastExistingDate === 'number') {
    lastExistingTimestamp = lastExistingDate;
  } else {
    lastExistingTimestamp = new Date(lastExistingDate).getTime();
  }
  
  // Add new data points and update last point if it matches
  for (let i = 0; i < newData.dates.length; i++) {
    const currentDate = newData.dates[i];
    let currentTimestamp: number;
    
    if (typeof currentDate === 'number') {
      currentTimestamp = currentDate;
    } else {
      currentTimestamp = new Date(currentDate).getTime();
    }
    
    if (currentTimestamp > lastExistingTimestamp) {
      // This is a new data point, add it
      updateData.dates.push(newData.dates[i]);
      updateData.ohlcv.push(newData.ohlcv[i]);
    } else if (currentTimestamp === lastExistingTimestamp) {
      // This is an update to the last existing point
      const lastIndex = updateData.dates.length - 1;
      updateData.ohlcv[lastIndex] = newData.ohlcv[i];
    }
  }
  
  // Limit to maxPoints if specified
  if (maxPoints > 0 && updateData.dates.length > maxPoints) {
    const startIndex = updateData.dates.length - maxPoints;
    updateData.dates = updateData.dates.slice(startIndex);
    updateData.ohlcv = updateData.ohlcv.slice(startIndex);
    updateData.metadata.points = maxPoints;
  } else {
    updateData.metadata.points = updateData.dates.length;
  }
  
  return updateData;
};

/**
 * Debug utility that logs information about chart data
 * @param data OHLCV data to inspect
 * @param label Optional label for the debug output
 * @returns Object with summary information about the data
 */
export const debugInspectData = (data: OHLCVData, label: string = 'Chart Data'): any => {
  if (!data || !data.dates || !data.ohlcv) {
    console.debug(`${label}: Invalid or empty data`);
    return null;
  }
  
  // Collect statistics
  const stats = {
    points: data.dates.length,
    timeRange: {
      start: data.dates[0],
      end: data.dates[data.dates.length - 1]
    },
    priceRange: {
      min: Number.MAX_VALUE,
      max: Number.MIN_VALUE
    },
    volume: {
      min: Number.MAX_VALUE,
      max: Number.MIN_VALUE,
      total: 0
    },
    validation: validateData(data)
  };
  
  // Calculate price and volume stats
  for (const ohlcv of data.ohlcv) {
    const [open, high, low, close, volume] = ohlcv;
    
    stats.priceRange.min = Math.min(stats.priceRange.min, low);
    stats.priceRange.max = Math.max(stats.priceRange.max, high);
    
    stats.volume.min = Math.min(stats.volume.min, volume);
    stats.volume.max = Math.max(stats.volume.max, volume);
    stats.volume.total += volume;
  }
  
  // Add sample data points
  const sampleSize = Math.min(5, data.dates.length);
  const samples = {
    start: data.ohlcv.slice(0, sampleSize),
    end: data.ohlcv.slice(-sampleSize)
  };
  
  const summary = {
    label,
    dataPoints: stats.points,
    timeframe: data.metadata?.timeframe,
    symbol: data.metadata?.symbol,
    timeRange: stats.timeRange,
    priceRange: stats.priceRange,
    volumeStats: stats.volume,
    isValid: stats.validation.valid,
    issues: stats.validation.issues,
    samples
  };
  
  // Log the summary
  console.debug(`${label}: Chart Data Summary`, summary);
  
  return summary;
};

/**
 * Creates test data for chart examples and testing
 * @param points Number of data points to generate
 * @param symbol Symbol for the test data
 * @param timeframe Timeframe for the test data
 * @param startDate Start date (default: 30 days ago)
 * @param volatility Price volatility factor
 * @returns Generated test data
 */
export const createTestData = (
  points: number = 50,
  symbol: string = 'TEST',
  timeframe: string = '1d',
  startDate: Date = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
  volatility: number = 0.02
): OHLCVData => {
  const dates: string[] = [];
  const ohlcv: number[][] = [];
  
  // Determine time increment based on timeframe
  let timeIncrement: number;
  switch (timeframe.slice(-1).toLowerCase()) {
    case 'm': // minute
      timeIncrement = 60 * 1000;
      break;
    case 'h': // hour
      timeIncrement = 60 * 60 * 1000;
      break;
    case 'd': // day
      timeIncrement = 24 * 60 * 60 * 1000;
      break;
    case 'w': // week
      timeIncrement = 7 * 24 * 60 * 60 * 1000;
      break;
    default:
      timeIncrement = 24 * 60 * 60 * 1000; // default to daily
  }
  
  // Extract the timeframe multiplier
  const multiplier = parseInt(timeframe.slice(0, -1)) || 1;
  timeIncrement *= multiplier;
  
  // Generate data points
  let currentDate = new Date(startDate);
  let currentPrice = 100; // Starting price
  
  for (let i = 0; i < points; i++) {
    // Generate random price movement
    const changePercent = (Math.random() - 0.5) * volatility;
    const change = currentPrice * changePercent;
    
    // Calculate OHLC values with some randomness
    const open = currentPrice;
    const close = currentPrice + change;
    const high = Math.max(open, close) + Math.random() * Math.abs(change);
    const low = Math.min(open, close) - Math.random() * Math.abs(change);
    
    // Generate random volume
    const volume = Math.floor(100000 + Math.random() * 900000);
    
    // Add data point
    dates.push(currentDate.toISOString());
    ohlcv.push([open, high, low, close, volume]);
    
    // Advance to next time period
    currentDate = new Date(currentDate.getTime() + timeIncrement);
    currentPrice = close; // Use close as next open
  }
  
  return {
    dates,
    ohlcv,
    metadata: {
      symbol,
      timeframe,
      start: dates[0],
      end: dates[dates.length - 1],
      points
    }
  };
};