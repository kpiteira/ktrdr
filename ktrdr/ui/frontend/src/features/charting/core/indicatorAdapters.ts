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

  // ...existing code...
  
  return { seriesData, seriesOptions };
}