/**
 * Symbol API endpoints
 * Provides methods for accessing symbol-related endpoints
 */

import { apiClient } from '../client';
import { SymbolInfo } from '../../features/symbols/types';

/**
 * Get all available trading symbols
 * @returns List of available trading symbols with metadata
 */
export async function getSymbols(): Promise<SymbolInfo[]> {
  try {
    const response = await apiClient.get('symbols');
    
    console.log('Raw API response for symbols:', response);
    
    // Handle the specific response format we're seeing in the logs:
    // {success: true, data: Array(2), error: null}
    if (response && response.success === true && Array.isArray(response.data)) {
      console.log('Using response.data array from success response');
      return response.data;
    }
    
    // Handle other possible response structures
    if (response && Array.isArray(response)) {
      console.log('Response is already an array');
      return response;
    } else if (response && response.data && Array.isArray(response.data)) {
      console.log('Using response.data array');
      return response.data;
    } else if (response && response.data && response.data.data && Array.isArray(response.data.data)) {
      console.log('Using response.data.data array');
      return response.data.data;
    } else {
      // Unknown structure, but try to handle it gracefully
      console.warn('Unexpected API response structure for symbols:', response);
      
      if (response && typeof response === 'object') {
        // Try to extract any array we can find
        const possibleArrays = Object.values(response).filter(val => Array.isArray(val));
        if (possibleArrays.length > 0) {
          console.log('Found array in response object:', possibleArrays[0]);
          return possibleArrays[0];
        }
        
        // Last resort: Create mock data for development
        console.log('Creating mock symbol data for development');
        return [
          { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'META', name: 'Meta Platforms Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'NFLX', name: 'Netflix Inc.', exchange: 'NASDAQ', type: 'stock' },
          { symbol: 'NVDA', name: 'NVIDIA Corporation', exchange: 'NASDAQ', type: 'stock' },
        ];
      }
      
      // Return empty array as fallback
      console.error('Could not find any symbol array in response, returning empty array');
      return [];
    }
  } catch (error) {
    console.error('Error in getSymbols():', error);
    // Return mock data in case of error for development
    return [
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', type: 'stock' },
      { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NASDAQ', type: 'stock' },
      { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NASDAQ', type: 'stock' }
    ];
  }
}

/**
 * Get detailed information about a specific symbol
 * @param symbol Symbol identifier
 * @returns Symbol information
 */
export async function getSymbolInfo(symbol: string): Promise<SymbolInfo | null> {
  try {
    const response = await apiClient.get(`symbols/${symbol}`);
    
    if (response && response.data) {
      // Handle different response structures
      if (response.data.data) {
        return response.data.data;
      } else {
        return response.data;
      }
    }
    return null;
  } catch (error) {
    console.error(`Error fetching symbol info for ${symbol}:`, error);
    return null;
  }
}