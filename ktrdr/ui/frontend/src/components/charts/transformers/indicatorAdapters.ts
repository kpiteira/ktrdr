// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/transformers/indicatorAdapters.ts
import { IndicatorData, IndicatorConfig, IndicatorType } from '../../../types/data';

/**
 * Format a date string or date object to the 'yyyy-mm-dd' format required by lightweight-charts
 * 
 * @param date Date as string, number, or Date object
 * @returns Date formatted as 'yyyy-mm-dd'
 */
export const formatDateForChart = (date: string | number | Date): string => {
  if (typeof date === 'string') {
    // If it's already in ISO format, extract just the date portion
    if (date.includes('T')) {
      return date.split('T')[0];
    }
    // If it's already in yyyy-mm-dd format, return as is
    if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return date;
    }
    // Otherwise, convert to Date then format
    return new Date(date).toISOString().split('T')[0];
  }
  // For Date objects or timestamps, convert to ISO and extract date
  return new Date(date).toISOString().split('T')[0];
};

/**
 * Transforms indicator data into format suitable for TradingView line series
 * 
 * @param data The indicator data to transform
 * @param seriesIndex Index of the series to use (for multi-line indicators)
 * @returns Array of line series data objects formatted for TradingView
 */
export const formatLineIndicatorData = (
  data: IndicatorData, 
  seriesIndex: number = 0
) => {
  if (!data || !data.dates || !data.values || data.values.length === 0) {
    return [];
  }

  // Ensure the requested series exists
  if (!data.values[seriesIndex]) {
    console.warn(`Series index ${seriesIndex} doesn't exist in indicator data`);
    return [];
  }

  return data.dates.map((date, index) => {
    const value = data.values[seriesIndex][index];
    
    // Skip null/undefined/NaN values
    if (value === null || value === undefined || isNaN(value)) {
      return null;
    }
    
    return {
      time: formatDateForChart(date),
      value: value
    };
  }).filter(point => point !== null);
};

/**
 * Transforms indicator data into format suitable for TradingView histogram series
 * 
 * @param data The indicator data to transform
 * @param seriesIndex Index of the series to use (for multi-line indicators)
 * @param baselineValue Optional baseline value (default: 0)
 * @param positiveColor Color for values above baseline
 * @param negativeColor Color for values below baseline
 * @returns Array of histogram data objects formatted for TradingView
 */
export const formatHistogramIndicatorData = (
  data: IndicatorData, 
  seriesIndex: number = 0,
  baselineValue: number = 0,
  positiveColor: string = 'rgba(76, 175, 80, 0.5)',
  negativeColor: string = 'rgba(239, 83, 80, 0.5)'
) => {
  if (!data || !data.dates || !data.values || data.values.length === 0) {
    return [];
  }

  // Ensure the requested series exists
  if (!data.values[seriesIndex]) {
    console.warn(`Series index ${seriesIndex} doesn't exist in indicator data`);
    return [];
  }

  return data.dates.map((date, index) => {
    const value = data.values[seriesIndex][index];
    
    // Skip null/undefined/NaN values
    if (value === null || value === undefined || isNaN(value)) {
      return null;
    }
    
    return {
      time: formatDateForChart(date),
      value: value,
      color: value >= baselineValue ? positiveColor : negativeColor
    };
  }).filter(point => point !== null);
};

/**
 * Transforms indicator data into format suitable for TradingView area series
 * 
 * @param data The indicator data to transform
 * @param seriesIndex Index of the series to use (for main line)
 * @returns Array of area series data objects formatted for TradingView
 */
export const formatAreaIndicatorData = (
  data: IndicatorData, 
  seriesIndex: number = 0
) => {
  return formatLineIndicatorData(data, seriesIndex);
};

/**
 * Transforms indicator data into format suitable for TradingView area series with two lines (cloud)
 * Creates data points for upper and lower bounds of a cloud/ribbon formation
 * 
 * @param data The indicator data to transform
 * @param upperSeriesIndex Index of the upper bound series
 * @param lowerSeriesIndex Index of the lower bound series
 * @returns Array of area series data objects with upperValue and lowerValue properties
 */
export const formatCloudIndicatorData = (
  data: IndicatorData, 
  upperSeriesIndex: number = 0,
  lowerSeriesIndex: number = 1
) => {
  if (!data || !data.dates || !data.values || data.values.length < 2) {
    return [];
  }

  // Ensure the requested series exist
  if (!data.values[upperSeriesIndex] || !data.values[lowerSeriesIndex]) {
    console.warn(`Series indices ${upperSeriesIndex} and ${lowerSeriesIndex} don't both exist in indicator data`);
    return [];
  }

  return data.dates.map((date, index) => {
    const upperValue = data.values[upperSeriesIndex][index];
    const lowerValue = data.values[lowerSeriesIndex][index];
    
    // Skip if either value is invalid
    if (upperValue === null || upperValue === undefined || isNaN(upperValue) ||
        lowerValue === null || lowerValue === undefined || isNaN(lowerValue)) {
      return null;
    }
    
    return {
      time: formatDateForChart(date),
      value: upperValue,  // Main value is the upper value
      upperValue: upperValue,
      lowerValue: lowerValue
    };
  }).filter(point => point !== null);
};

/**
 * Validates indicator data to prevent rendering errors
 * 
 * @param data The indicator data to validate
 * @returns Object with validation result and errors if any
 */
export const validateIndicatorData = (data: IndicatorData): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  if (!data) {
    errors.push('Data is undefined or null');
    return { valid: false, errors };
  }
  
  if (!data.dates || !data.values) {
    errors.push('Data is missing dates or values arrays');
    return { valid: false, errors };
  }
  
  if (data.dates.length === 0 || data.values.length === 0) {
    errors.push('Data arrays are empty');
    return { valid: false, errors };
  }
  
  // For multi-series indicators, ensure all arrays have the same length
  const firstSeriesLength = data.values[0].length;
  for (let i = 1; i < data.values.length; i++) {
    if (data.values[i].length !== firstSeriesLength) {
      errors.push(`Series at index ${i} has different length than first series`);
    }
  }
  
  // Check if dates array matches length of values array
  if (data.dates.length !== firstSeriesLength) {
    errors.push('Dates array length does not match values array length');
  }
  
  return {
    valid: errors.length === 0,
    errors
  };
};

/**
 * Gets the appropriate formatter function based on indicator type
 * 
 * @param type The indicator type
 * @returns Formatter function for that indicator type
 */
export const getIndicatorFormatter = (type: IndicatorType) => {
  switch (type) {
    case IndicatorType.LINE:
    case IndicatorType.MULTI_LINE:
      return formatLineIndicatorData;
    case IndicatorType.HISTOGRAM:
      return formatHistogramIndicatorData;
    case IndicatorType.AREA:
      return formatAreaIndicatorData;
    case IndicatorType.CLOUD:
      return formatCloudIndicatorData;
    default:
      return formatLineIndicatorData;
  }
};

/**
 * Helper to compute the min and max values for an indicator
 * Useful for setting y-axis scale
 * 
 * @param data The indicator data
 * @returns Object with min and max values
 */
export const getIndicatorMinMax = (data: IndicatorData): { min: number; max: number } => {
  if (!data || !data.values || data.values.length === 0) {
    return { min: 0, max: 0 };
  }
  
  let min = Number.MAX_VALUE;
  let max = Number.MIN_VALUE;
  
  // Check all series in the data
  for (const series of data.values) {
    for (const value of series) {
      // Skip invalid values
      if (value === null || value === undefined || isNaN(value)) continue;
      
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
  }
  
  // If no valid values found, return defaults
  if (min === Number.MAX_VALUE || max === Number.MIN_VALUE) {
    return { min: 0, max: 0 };
  }
  
  // Add slight padding to min/max for better visualization
  const padding = (max - min) * 0.05;
  return {
    min: min - padding,
    max: max + padding
  };
};

/**
 * Format indicator data for the chart library
 * 
 * @param data Indicator data to format
 * @param config Indicator configuration
 * @param type Type of indicator
 * @returns Formatted series data and options
 */
export function formatIndicatorForChart(
  data: IndicatorData,
  config: IndicatorConfig,
  type: IndicatorType
): { 
  seriesData: any[][]; 
  seriesOptions: any[] 
} {
  if (!data || !config) {
    console.error('Missing data or config for formatIndicatorForChart');
    return { seriesData: [], seriesOptions: [] };
  }

  // Validate data
  const validation = validateIndicatorData(data);
  if (!validation.valid) {
    console.warn('Indicator data validation failed:', validation.errors);
    return { seriesData: [], seriesOptions: [] };
  }

  const seriesData: any[][] = [];
  const seriesOptions: any[] = [];
  
  // Get colors from config, or use defaults
  const colors = config.colors || ['#2196F3', '#9C27B0', '#4CAF50'];
  
  // Get names from metadata or use defaults
  const seriesNames = data.metadata?.names || [`${data.indicatorId || 'Indicator'}`];
  
  // Process data based on type
  switch (type) {
    case IndicatorType.LINE:
      // For single or multi-line indicators
      for (let i = 0; i < data.values.length; i++) {
        if (!data.values[i]) continue;
        
        const formattedData = formatLineIndicatorData(data, i);
        seriesData.push(formattedData);
        
        seriesOptions.push({
          color: colors[i % colors.length],
          lineWidth: 2,
          title: seriesNames[i] || `Series ${i+1}`,
          lastValueVisible: true,
          priceLineVisible: false,
        });
      }
      break;
      
    case IndicatorType.MULTI_LINE:
      // Similar to LINE but allows for different styling per line
      for (let i = 0; i < data.values.length; i++) {
        if (!data.values[i]) continue;
        
        const formattedData = formatLineIndicatorData(data, i);
        seriesData.push(formattedData);
        
        seriesOptions.push({
          color: colors[i % colors.length],
          lineWidth: i === 1 ? 2 : 1, // Make middle line thicker if it exists
          lineStyle: i !== 1 ? 1 : 0, // Make outer lines dashed if they exist
          title: seriesNames[i] || `Series ${i+1}`,
          lastValueVisible: true,
          priceLineVisible: false,
        });
      }
      break;
      
    case IndicatorType.HISTOGRAM:
      // For histogram indicators like MACD
      const formattedData = formatHistogramIndicatorData(data, 0, 0, 
        colors[0], // Positive color
        colors.length > 1 ? colors[1] : 'rgba(239, 83, 80, 0.5)' // Negative color
      );
      seriesData.push(formattedData);
      
      seriesOptions.push({
        title: seriesNames[0] || 'Histogram',
        lastValueVisible: true,
      });
      break;
      
    case IndicatorType.AREA:
      // For area indicators
      const areaData = formatAreaIndicatorData(data, 0);
      seriesData.push(areaData);
      
      seriesOptions.push({
        topColor: `${colors[0]}80`, // Add transparency
        bottomColor: `${colors[0]}10`,
        lineColor: colors[0],
        lineWidth: 2,
        title: seriesNames[0] || 'Area',
        lastValueVisible: true,
        priceLineVisible: false,
      });
      break;
      
    case IndicatorType.CLOUD:
      // For cloud indicators like Ichimoku
      if (data.values.length >= 2) {
        // First series is the main reference line (usually faster line)
        const lineData = formatLineIndicatorData(data, 0);
        seriesData.push(lineData);
        
        seriesOptions.push({
          color: colors[0],
          lineWidth: 2,
          title: seriesNames[0] || 'Line 1',
          lastValueVisible: true,
          priceLineVisible: false,
        });
        
        // Second series is the second reference line (usually slower line)
        const secondLineData = formatLineIndicatorData(data, 1);
        seriesData.push(secondLineData);
        
        seriesOptions.push({
          color: colors[1],
          lineWidth: 2,
          title: seriesNames[1] || 'Line 2',
          lastValueVisible: true,
          priceLineVisible: false,
        });
        
        // Third is the cloud (area between the two lines)
        const cloudData = formatCloudIndicatorData(data, 0, 1);
        seriesData.push(cloudData);
        
        const bullishColor = colors[2] || 'rgba(76, 175, 80, 0.2)';
        const bearishColor = colors.length > 3 ? colors[3] : 'rgba(239, 83, 80, 0.2)';
        
        seriesOptions.push({
          topColor: bullishColor,
          bottomColor: bullishColor,
          lineColor: 'transparent',
          title: 'Cloud',
          lastValueVisible: false,
          priceLineVisible: false,
        });
      }
      break;
      
    default:
      console.warn(`Unsupported indicator type: ${type}`);
  }
  
  return { seriesData, seriesOptions };
}