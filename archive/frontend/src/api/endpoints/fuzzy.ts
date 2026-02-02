/**
 * Fuzzy overlay API client
 * Provides typed methods for interacting with the fuzzy data endpoints
 */

import { apiClient } from '../client';
import { 
  FuzzyOverlayResponse, 
  FuzzyOverlayParams,
  FuzzyApiError 
} from '../types/fuzzy';

/**
 * Get fuzzy overlay data for indicators
 * 
 * @param params - Parameters for the fuzzy overlay request
 * @param signal - AbortSignal for request cancellation
 * @returns Promise resolving to fuzzy overlay response
 */
export const getFuzzyOverlay = async (
  params: FuzzyOverlayParams,
  signal?: AbortSignal
): Promise<FuzzyOverlayResponse> => {
  try {
    const queryParams: Record<string, any> = {
      symbol: params.symbol,
      timeframe: params.timeframe,
    };

    // Add optional parameters if provided
    if (params.indicators && params.indicators.length > 0) {
      queryParams.indicators = params.indicators;
    }
    if (params.start_date) {
      queryParams.start_date = params.start_date;
    }
    if (params.end_date) {
      queryParams.end_date = params.end_date;
    }

    const response = await apiClient.get<FuzzyOverlayResponse>(
      'fuzzy/data',
      queryParams,
      { signal }
    );

    return response;
  } catch (error: any) {
    // Handle specific fuzzy API errors
    if (error.response?.data?.error) {
      const fuzzyError: FuzzyApiError = error.response.data;
      throw new Error(`Fuzzy API Error: ${fuzzyError.error.message}`);
    }
    
    // Handle general network or other errors
    throw new Error(`Failed to fetch fuzzy overlay data: ${error.message}`);
  }
};

/**
 * Get available fuzzy indicators
 * 
 * @param signal - AbortSignal for request cancellation
 * @returns Promise resolving to list of available fuzzy indicators
 */
export const getFuzzyIndicators = async (
  signal?: AbortSignal
): Promise<Array<{
  id: string;
  name: string;
  fuzzy_sets: string[];
  output_columns: string[];
}>> => {
  try {
    const response = await apiClient.get<{
      success: boolean;
      data: Array<{
        id: string;
        name: string;
        fuzzy_sets: string[];
        output_columns: string[];
      }>;
    }>('fuzzy/indicators', {}, { signal });

    return response.data || [];
  } catch (error: any) {
    throw new Error(`Failed to fetch fuzzy indicators: ${error.message}`);
  }
};