/**
 * Custom hook for fuzzy overlay data management
 * 
 * Provides fuzzy membership data fetching, caching, and local state management
 * following React hooks patterns without Redux complexity.
 */

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getFuzzyOverlay } from '../api/endpoints/fuzzy';
import { 
  FuzzyOverlayResponse, 
  FuzzySetMembership, 
  ChartFuzzyData 
} from '../api/types/fuzzy';
import { createFuzzyColorConfig } from '../utils/fuzzyColors';
import { createLogger } from '../utils/logger';

const logger = createLogger('useFuzzyOverlay');

/**
 * Cache entry for fuzzy data
 */
interface FuzzyCacheEntry {
  data: FuzzyOverlayResponse;
  timestamp: number;
  ttl: number;
}

/**
 * Simple cache for fuzzy overlay data
 * Prevents duplicate requests for the same parameters
 */
class FuzzyDataCache {
  private cache = new Map<string, FuzzyCacheEntry>();
  private readonly defaultTtl = 5 * 60 * 1000; // 5 minutes

  private createKey(indicatorId: string, symbol: string, timeframe: string, dateRange?: string): string {
    return dateRange 
      ? `${indicatorId}:${symbol}:${timeframe}:${dateRange}`
      : `${indicatorId}:${symbol}:${timeframe}`;
  }

  get(indicatorId: string, symbol: string, timeframe: string, dateRange?: string): FuzzyOverlayResponse | null {
    const key = this.createKey(indicatorId, symbol, timeframe, dateRange);
    const entry = this.cache.get(key);
    
    if (!entry) return null;
    
    // Check if cache entry has expired
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data;
  }

  set(
    indicatorId: string, 
    symbol: string, 
    timeframe: string, 
    data: FuzzyOverlayResponse, 
    ttl?: number,
    dateRange?: string
  ): void {
    const key = this.createKey(indicatorId, symbol, timeframe, dateRange);
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl || this.defaultTtl
    });
  }

  clear(): void {
    this.cache.clear();
  }
}

// Global cache instance
const fuzzyCache = new FuzzyDataCache();

/**
 * Hook state interface
 */
interface UseFuzzyOverlayState {
  fuzzyData: ChartFuzzyData[] | null;
  isLoading: boolean;
  error: string | null;
  isVisible: boolean;
  opacity: number;
  colorScheme: string;
}

/**
 * Hook return interface
 */
interface UseFuzzyOverlayReturn extends UseFuzzyOverlayState {
  toggleVisibility: () => void;
  setOpacity: (opacity: number) => void;
  setColorScheme: (scheme: string) => void;
  refetch: () => Promise<void>;
  clearCache: () => void;
}

/**
 * Scaling configuration for different indicator types
 */
interface ScalingConfig {
  minValue: number;
  maxValue: number;
  indicatorType: 'rsi' | 'macd' | 'other';
}

/**
 * Transform API response to chart-ready format with dynamic scaling
 */
const transformFuzzyDataForChart = (
  fuzzyData: FuzzySetMembership[],
  colorScheme: string,
  opacity: number,
  scalingConfig?: ScalingConfig
): ChartFuzzyData[] => {
  // Default to RSI scaling for backward compatibility
  const defaultScaling: ScalingConfig = {
    minValue: 0,
    maxValue: 100,
    indicatorType: 'rsi'
  };
  
  const scaling = scalingConfig || defaultScaling;
  const range = scaling.maxValue - scaling.minValue;
  
  return fuzzyData.map(setData => {
    const colorConfig = createFuzzyColorConfig(setData.set, colorScheme, opacity);
    
    // Convert membership points to chart format with dynamic scaling
    const chartData = setData.membership
      .filter(point => point.value !== null)
      .map(point => ({
        time: new Date(point.timestamp).getTime() / 1000, // Convert to Unix timestamp
        value: scaling.minValue + ((point.value as number) * range) // Scale 0-1 to indicator range
      }));

    return {
      setName: setData.set,
      data: chartData,
      color: colorConfig.fillColor,
      opacity
    };
  });
};

/**
 * Custom hook for fuzzy overlay data and state management
 * 
 * @param indicatorId - Unique identifier for the indicator instance
 * @param symbol - Trading symbol (e.g., 'AAPL')
 * @param timeframe - Data timeframe (e.g., '1d', '1h')
 * @param dateRange - Optional date range to match chart data
 * @param isVisible - Whether the overlay should be visible
 * @param scalingConfig - Scaling configuration for the indicator type
 * @returns Fuzzy overlay state and control functions
 */
export const useFuzzyOverlay = (
  indicatorId: string,
  symbol: string,
  timeframe: string,
  dateRange?: { start: string; end: string },
  isVisible?: boolean,
  scalingConfig?: ScalingConfig
): UseFuzzyOverlayReturn => {
  // Local state management
  const [state, setState] = useState<UseFuzzyOverlayState>({
    fuzzyData: null,
    isLoading: false,
    error: null,
    isVisible: isVisible || false,
    opacity: 0.3,
    colorScheme: 'default'
  });

  // Refs for cleanup and abort controller
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  
  // Refs to avoid state dependencies in fetchFuzzyData
  const colorSchemeRef = useRef(state.colorScheme);
  const opacityRef = useRef(state.opacity);

  // Extract indicator name from indicatorId (e.g., 'rsi-123' -> 'rsi')
  const indicatorName = useMemo(() => {
    return indicatorId.split('-')[0];
  }, [indicatorId]);

  // Update internal visibility state when external isVisible prop changes
  useEffect(() => {
    // Only update if external prop is explicitly set (not undefined)
    if (isVisible !== undefined) {
      setState(prev => ({ ...prev, isVisible: isVisible }));
    }
  }, [isVisible, indicatorId]);

  // Update refs when state changes to avoid stale closures
  useEffect(() => {
    colorSchemeRef.current = state.colorScheme;
    opacityRef.current = state.opacity;
  }, [state.colorScheme, state.opacity]);

  /**
   * Fetch fuzzy data from API or cache
   */
  const fetchFuzzyData = useCallback(async (forceVisible?: boolean) => {
    // Use provided visibility or check current state via ref
    const isCurrentlyVisible = forceVisible ?? state.isVisible;
    
    // Don't fetch if not visible
    if (!isCurrentlyVisible) {
      return;
    }

    // Use provided date range or default to last 3 months to match chart data
    const endDate = dateRange?.end || new Date().toISOString().split('T')[0];
    const startDate = dateRange?.start || (() => {
      const date = new Date();
      date.setMonth(date.getMonth() - 3);
      return date.toISOString().split('T')[0];
    })();
    const dateRangeKey = `${startDate}:${endDate}`;

    // Check cache first
    const cachedData = fuzzyCache.get(indicatorId, symbol, timeframe, dateRangeKey);
    if (cachedData && cachedData.data[indicatorName]) {
      // Using cached fuzzy data
      const transformedData = transformFuzzyDataForChart(
        cachedData.data[indicatorName],
        colorSchemeRef.current,
        opacityRef.current,
        scalingConfig
      );
      
      if (isMountedRef.current) {
        setState(prev => ({
          ...prev,
          fuzzyData: transformedData,
          error: null
        }));
      }
      return;
    }

    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    if (isMountedRef.current) {
      setState(prev => ({ ...prev, isLoading: true, error: null }));
    }

    try {
      const response = await getFuzzyOverlay(
        {
          symbol,
          timeframe,
          indicators: [indicatorName],
          start_date: startDate,
          end_date: endDate
        },
        abortControllerRef.current.signal
      );

      // Cache the response with date range
      fuzzyCache.set(indicatorId, symbol, timeframe, response, undefined, dateRangeKey);

      // Check if we got data for our indicator
      const indicatorData = response.data[indicatorName];
      if (!indicatorData) {
        throw new Error(`No fuzzy data available for indicator: ${indicatorName}`);
      }

      // Transform data for charts
      const transformedData = transformFuzzyDataForChart(
        indicatorData,
        colorSchemeRef.current,
        opacityRef.current,
        scalingConfig
      );

      if (isMountedRef.current) {
        setState(prev => ({
          ...prev,
          fuzzyData: transformedData,
          isLoading: false,
          error: null
        }));
      }

      // Successfully loaded fuzzy data

    } catch (error: any) {
      if (error.name === 'AbortError' || error.message?.includes('canceled')) {
        // Request was cancelled, this is normal during component unmount or re-renders
        return;
      }

      logger.error(`Failed to fetch fuzzy data for ${indicatorId}:`, error);
      
      if (isMountedRef.current) {
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: error.message || 'Failed to load fuzzy data'
        }));
      }
    }
  }, [indicatorId, symbol, timeframe, indicatorName, dateRange]);

  /**
   * Toggle fuzzy overlay visibility
   */
  const toggleVisibility = useCallback(() => {
    setState(prev => {
      const newVisible = !prev.isVisible;
      // Toggling fuzzy visibility
      return { ...prev, isVisible: newVisible };
    });
  }, [indicatorId]);

  /**
   * Set fuzzy overlay opacity
   */
  const setOpacity = useCallback((newOpacity: number) => {
    const clampedOpacity = Math.max(0, Math.min(1, newOpacity));
    setState(prev => ({ ...prev, opacity: clampedOpacity }));
  }, []);

  /**
   * Set fuzzy color scheme
   */
  const setColorScheme = useCallback((newScheme: string) => {
    setState(prev => ({ ...prev, colorScheme: newScheme }));
  }, []);

  /**
   * Force refetch fuzzy data
   */
  const refetch = useCallback(async () => {
    fuzzyCache.clear();
    await fetchFuzzyData();
  }, [fetchFuzzyData]);

  /**
   * Clear cache for this hook
   */
  const clearCache = useCallback(() => {
    fuzzyCache.clear();
  }, []);

  // Initial fetch effect when key parameters change
  useEffect(() => {
    // Only fetch if currently visible and we don't have data
    if (state.isVisible && !state.fuzzyData && !state.isLoading) {
      fetchFuzzyData();
    }
  }, [indicatorId, symbol, timeframe]);

  // Effect to fetch data when visibility changes to true
  useEffect(() => {
    if (state.isVisible && !state.fuzzyData && !state.isLoading) {
      fetchFuzzyData(true); // Force visible since we already checked
    }
  }, [state.isVisible, indicatorId]);

  // Effect to retransform data when opacity or color scheme changes (with debouncing)
  useEffect(() => {
    if (!state.fuzzyData || state.isLoading) return;

    // Debounce rapid opacity changes to prevent chart jumping
    const timeoutId = setTimeout(() => {
      // Calculate current date range key
      const endDate = dateRange?.end || new Date().toISOString().split('T')[0];
      const startDate = dateRange?.start || (() => {
        const date = new Date();
        date.setMonth(date.getMonth() - 3);
        return date.toISOString().split('T')[0];
      })();
      const dateRangeKey = `${startDate}:${endDate}`;

      // Find the original data from cache to retransform
      const cachedData = fuzzyCache.get(indicatorId, symbol, timeframe, dateRangeKey);
      if (cachedData && cachedData.data[indicatorName]) {
        const transformedData = transformFuzzyDataForChart(
          cachedData.data[indicatorName],
          state.colorScheme,
          state.opacity,
          scalingConfig
        );
        
        // Only update if component is still mounted
        if (isMountedRef.current) {
          setState(prev => ({ ...prev, fuzzyData: transformedData }));
        }
      }
    }, 100); // 100ms debounce to prevent rapid updates

    return () => clearTimeout(timeoutId);
  }, [state.colorScheme, state.opacity, indicatorId, symbol, timeframe, indicatorName, dateRange, scalingConfig]);

  // Cleanup effect - only runs on actual unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [indicatorId]); // Reset when indicatorId changes

  const returnValue = {
    ...state,
    toggleVisibility,
    setOpacity,
    setColorScheme,
    refetch,
    clearCache
  };


  return returnValue;
};

// Export the scaling config interface for use in other components
export type { ScalingConfig };