/**
 * Data transformation utilities
 * Common utility functions for transforming OHLCV data
 */

import { OHLCVData } from '../../types/data';

/**
 * Normalize data to a range between 0 and 1
 * @param data Original OHLCV data
 * @returns Normalized OHLCV data
 */
export function normalizeData(data: OHLCVData): OHLCVData {
  if (!data?.ohlcv?.length) return data;

  // Find min and max values for each OHLCV component
  const mins = [Infinity, Infinity, Infinity, Infinity, Infinity];
  const maxs = [-Infinity, -Infinity, -Infinity, -Infinity, -Infinity];

  // First pass to find min/max
  for (const row of data.ohlcv) {
    for (let i = 0; i < 5; i++) {
      if (row[i] < mins[i]) mins[i] = row[i];
      if (row[i] > maxs[i]) maxs[i] = row[i];
    }
  }

  // Calculate ranges (avoid division by zero)
  const ranges = maxs.map((max, i) => {
    const range = max - mins[i];
    return range > 0 ? range : 1; // Use 1 if range is 0 to avoid division by zero
  });

  // Second pass to normalize
  const normalizedOhlcv = data.ohlcv.map(row => {
    return row.map((value, i) => {
      // Normalize to 0-1 range
      return (value - mins[i]) / ranges[i];
    });
  });

  // Return new data object with normalized values
  return {
    ...data,
    ohlcv: normalizedOhlcv,
    metadata: {
      ...data.metadata,
      transformation: 'normalized'
    }
  };
}

/**
 * Apply logarithmic transformation to data
 * @param data Original OHLCV data
 * @returns Log-transformed OHLCV data
 */
export function logTransformData(data: OHLCVData): OHLCVData {
  if (!data?.ohlcv?.length) return data;

  // Apply natural log transformation to all OHLCV values
  // (adding small epsilon to avoid log(0))
  const epsilon = 0.00001;
  const logOhlcv = data.ohlcv.map(row => {
    return row.map(value => Math.log(Math.max(value, epsilon)));
  });

  // Return new data object with log-transformed values
  return {
    ...data,
    ohlcv: logOhlcv,
    metadata: {
      ...data.metadata,
      transformation: 'log'
    }
  };
}

/**
 * Calculate percentage change from first data point
 * @param data Original OHLCV data
 * @returns Percentage change OHLCV data
 */
export function percentChangeData(data: OHLCVData): OHLCVData {
  if (!data?.ohlcv?.length) return data;

  // Get base values (first row)
  const baseValues = data.ohlcv[0];

  // Calculate percentage change for each value
  const percentChangeOhlcv = data.ohlcv.map(row => {
    return row.map((value, i) => {
      // Skip volume for percentage calculation
      if (i === 4) return value; 
      
      // Calculate percentage change
      const baseValue = baseValues[i];
      return baseValue !== 0 ? ((value - baseValue) / baseValue) * 100 : 0;
    });
  });

  // Return new data object with percentage changes
  return {
    ...data,
    ohlcv: percentChangeOhlcv,
    metadata: {
      ...data.metadata,
      transformation: 'percent-change'
    }
  };
}

/**
 * Get available transformation types
 * @returns List of available transformations
 */
export function getAvailableTransformations(): { id: string, name: string }[] {
  return [
    { id: 'normalized', name: 'Normalize (0-1)' },
    { id: 'log', name: 'Logarithmic' },
    { id: 'percent-change', name: 'Percent Change' }
  ];
}

/**
 * Apply a specified transformation to data
 * @param data Original OHLCV data
 * @param type Transformation type
 * @returns Transformed OHLCV data
 */
export function transformData(data: OHLCVData, type: string): OHLCVData {
  switch (type) {
    case 'normalized':
      return normalizeData(data);
    case 'log':
      return logTransformData(data);
    case 'percent-change':
      return percentChangeData(data);
    default:
      return data;
  }
}