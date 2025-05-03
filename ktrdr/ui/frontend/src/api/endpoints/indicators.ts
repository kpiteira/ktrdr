/**
 * Indicator API endpoints
 * Provides methods for accessing indicator-related endpoints
 */

import { apiClient } from '../client';
import type { IndicatorMetadata, IndicatorConfig } from '../../types/indicators';

/**
 * Get available indicators with their metadata
 */
export async function getIndicators(): Promise<IndicatorMetadata[]> {
  const response = await apiClient.get('/api/v1/indicators');
  return response.data.data;
}

/**
 * Calculate indicators for a given symbol and timeframe
 */
export async function calculateIndicators(
  symbol: string, 
  timeframe: string, 
  indicators: IndicatorConfig[]
): Promise<Record<string, number[]>> {
  const response = await apiClient.post('/api/v1/indicators/calculate', {
    symbol,
    timeframe,
    indicators
  });
  
  return response.data.data.indicators;
}