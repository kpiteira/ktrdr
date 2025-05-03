/**
 * Indicator API endpoints
 * Provides methods for accessing indicator-related endpoints
 */

import { apiClient, RequestOptions } from '../client';
import { 
  IndicatorInfo, 
  IndicatorConfig, 
  IndicatorData,
  DateRangeParams
} from '../types';

/**
 * Get available indicators
 * @param options Request options
 * @returns List of available indicators with metadata
 */
export const getIndicators = async (options?: RequestOptions): Promise<IndicatorInfo[]> => {
  return apiClient.get<IndicatorInfo[]>('/indicators', undefined, options);
};

/**
 * Calculate indicator values for a symbol and timeframe
 * @param symbol Symbol
 * @param timeframe Timeframe
 * @param indicators Indicator configurations
 * @param dateRange Optional date range parameters
 * @param options Request options
 * @returns Calculated indicator data
 */
export const calculateIndicators = async (
  symbol: string,
  timeframe: string,
  indicators: IndicatorConfig[],
  dateRange?: DateRangeParams,
  options?: RequestOptions
): Promise<IndicatorData> => {
  // Convert to snake_case for API
  const payload = {
    symbol,
    timeframe,
    indicators,
    start_date: dateRange?.startDate,
    end_date: dateRange?.endDate
  };
  
  return apiClient.post<IndicatorData>('/indicators/calculate', payload, options);
};