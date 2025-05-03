/**
 * Data API endpoints
 * Provides methods for accessing data-related endpoints
 */

import { apiClient, RequestOptions } from '../client';
import { 
  SymbolInfo, 
  TimeframeInfo, 
  OHLCVData, 
  DataRangeInfo, 
  DataLoadParams 
} from '../types';

/**
 * Get available symbols
 * @param options Request options
 * @returns List of available symbols
 */
export const getSymbols = async (options?: RequestOptions): Promise<SymbolInfo[]> => {
  return apiClient.get<SymbolInfo[]>('/symbols', undefined, options);
};

/**
 * Get available timeframes
 * @param options Request options
 * @returns List of available timeframes
 */
export const getTimeframes = async (options?: RequestOptions): Promise<TimeframeInfo[]> => {
  return apiClient.get<TimeframeInfo[]>('/timeframes', undefined, options);
};

/**
 * Load OHLCV data for a symbol and timeframe
 * @param params Request parameters
 * @param options Request options
 * @returns OHLCV data
 */
export const loadData = async (
  params: DataLoadParams,
  options?: RequestOptions
): Promise<OHLCVData> => {
  const { symbol, timeframe, startDate, endDate, page, pageSize } = params;
  
  // Convert to snake_case for API
  const payload = {
    symbol,
    timeframe,
    start_date: startDate,
    end_date: endDate,
    page,
    page_size: pageSize
  };
  
  return apiClient.post<OHLCVData>('/data/load', payload, options);
};

/**
 * Get data range information for a symbol and timeframe
 * @param symbol Symbol
 * @param timeframe Timeframe
 * @param options Request options
 * @returns Data range information
 */
export const getDataRange = async (
  symbol: string,
  timeframe: string,
  options?: RequestOptions
): Promise<DataRangeInfo> => {
  const payload = {
    symbol,
    timeframe
  };
  
  return apiClient.post<DataRangeInfo>('/data/range', payload, options);
};