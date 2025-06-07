import { useState, useCallback, useRef } from 'react';
import { CandlestickData } from 'lightweight-charts';
import { createLogger } from '../utils/logger';
import { convertToUTCTimestamp } from '../api/utils/dataTransformations';

const logger = createLogger('useSharedPriceData');

/**
 * Shared price data hook to eliminate duplication between chart containers
 * 
 * This hook provides a single source of truth for price data that can be
 * shared between BasicChartContainer and RSIChartContainer, preventing
 * duplicate API calls and improving performance.
 */

interface UseSharedPriceDataResult {
  priceData: CandlestickData[];
  isLoading: boolean;
  error: string | null;
  loadPriceData: (symbol: string, timeframe: string) => Promise<void>;
  getCurrentSymbol: () => string;
  getCurrentTimeframe: () => string;
}

interface PriceDataCache {
  [key: string]: {
    data: CandlestickData[];
    timestamp: number;
  };
}

const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export const useSharedPriceData = (): UseSharedPriceDataResult => {
  const [priceData, setPriceData] = useState<CandlestickData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Track current symbol/timeframe
  const currentSymbolRef = useRef<string>('');
  const currentTimeframeRef = useRef<string>('');
  
  // Simple in-memory cache
  const cacheRef = useRef<PriceDataCache>({});

  const loadPriceData = useCallback(async (symbol: string, timeframe: string) => {
    const cacheKey = `${symbol}-${timeframe}`;
    const now = Date.now();
    
    
    // Check cache first
    const cached = cacheRef.current[cacheKey];
    if (cached && (now - cached.timestamp) < CACHE_DURATION) {
      setPriceData(cached.data);
      currentSymbolRef.current = symbol;
      currentTimeframeRef.current = timeframe;
      return;
    }
    setIsLoading(true);
    setError(null);

    try {
      // Calculate date range to get approximately 500 trading points
      const targetPoints = 500;
      const currentDate = new Date();
      let weeksNeeded;
      
      // For hourly data: ~6.5 hours/day * 5 days/week = ~32.5 points/week  
      // For daily data: ~5 trading days/week
      if (timeframe === '1h') {
        weeksNeeded = Math.ceil(targetPoints / 32.5); // ~15 weeks for 500 points
      } else if (timeframe === '1d') {
        weeksNeeded = Math.ceil(targetPoints / 5); // ~100 weeks for 500 points  
      } else {
        weeksNeeded = 20; // Default fallback
      }
      
      const startDate = new Date(currentDate);
      startDate.setDate(startDate.getDate() - (weeksNeeded * 7));
      
      // Build query parameters for date filtering
      const params = new URLSearchParams({
        start_date: startDate.toISOString().split('T')[0],
        end_date: currentDate.toISOString().split('T')[0]
      });
      
      const response = await fetch(`/api/v1/data/${symbol}/${timeframe}?${params.toString()}`);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const result = await response.json();
      if (!result.success || !result.data || !result.data.dates || !result.data.ohlcv) {
        throw new Error('Invalid response format from data API');
      }

      // Transform the data to TradingView format (matching the actual API response)
      const data = result.data;
      const transformedData: CandlestickData[] = data.dates.map((dateStr: string, index: number) => {
        const ohlcv = data.ohlcv[index];
        if (!ohlcv || ohlcv.length < 4) {
          throw new Error(`Invalid OHLCV data at index ${index}`);
        }
        
        const timestamp = convertToUTCTimestamp(dateStr);
        return {
          time: timestamp,
          open: ohlcv[0],
          high: ohlcv[1],
          low: ohlcv[2],
          close: ohlcv[3]
        };
      })
      .filter(item => !isNaN(item.time as number)); // Filter out invalid timestamps

      // Sort by time to ensure correct order
      transformedData.sort((a, b) => (a.time as number) - (b.time as number));

      // Cache the data
      cacheRef.current[cacheKey] = {
        data: transformedData,
        timestamp: now
      };
      
      setPriceData(transformedData);
      currentSymbolRef.current = symbol;
      currentTimeframeRef.current = timeframe;
      setIsLoading(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error loading price data';
      logger.error('[useSharedPriceData] Error loading price data:', errorMessage);
      setError(errorMessage);
      setIsLoading(false);
    }
  }, []);

  const getCurrentSymbol = useCallback(() => currentSymbolRef.current, []);
  const getCurrentTimeframe = useCallback(() => currentTimeframeRef.current, []);

  return {
    priceData,
    isLoading,
    error,
    loadPriceData,
    getCurrentSymbol,
    getCurrentTimeframe
  };
};