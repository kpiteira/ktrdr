/**
 * Data API endpoints
 * Provides methods for accessing data-related endpoints
 */

import { apiClient } from '../client';
import type { OHLCVData } from '../../types/data';

/**
 * Load OHLCV data for a given symbol and timeframe
 */
export async function loadData({ 
  symbol, 
  timeframe, 
  startDate, 
  endDate 
}: { 
  symbol: string; 
  timeframe: string; 
  startDate?: string; 
  endDate?: string;
}): Promise<OHLCVData> {
  const response = await apiClient.post('data/load', {
    symbol,
    timeframe,
    start_date: startDate,
    end_date: endDate
  });
  
  // Handle different possible response structures
  if (response.data && response.data.data) {
    return response.data.data;
  } else if (Array.isArray(response.data)) {
    return response.data;
  } else {
    return response.data;
  }
}

/**
 * Get available trading symbols
 */
export async function getSymbols(): Promise<any[]> {
  const response = await apiClient.get('symbols');
  
  // Handle different possible response structures
  if (response && Array.isArray(response)) {
    return response;
  } else if (response && response.data && Array.isArray(response.data)) {
    return response.data;
  } else if (response && response.data && response.data.data && Array.isArray(response.data.data)) {
    return response.data.data;
  } else {
    // Unknown structure, but try to handle it gracefully
    console.warn('Unexpected API response structure for symbols');
    if (response && typeof response === 'object') {
      // Try to extract any array we can find
      const possibleArrays = Object.values(response).filter(val => Array.isArray(val));
      if (possibleArrays.length > 0) {
        return possibleArrays[0];
      }
    }
    // Return empty array as fallback
    return [];
  }
}

/**
 * Get available timeframes
 */
export async function getTimeframes(): Promise<string[]> {
  const response = await apiClient.get('timeframes');
  
  // Handle different possible response structures
  if (response.data && response.data.data) {
    return response.data.data;
  } else if (Array.isArray(response.data)) {
    return response.data;
  } else {
    // If response.data is the actual array
    return response.data;
  }
}