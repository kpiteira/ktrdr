/**
 * Data API hooks for React components
 * Provides custom hooks for data-related API endpoints
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { dataApi, RequestOptions, KTRDRApiError } from '../';
import { SymbolInfo, TimeframeInfo, OHLCVData, DataRangeInfo, DataLoadParams } from '../types';

/**
 * Hook result with loading and error states
 */
interface HookResult<T> {
  data: T | null;
  isLoading: boolean;
  error: KTRDRApiError | null;
  refetch: () => Promise<void>;
}

/**
 * Hook for retrieving available symbols
 * @param options Request options
 * @returns Hook result with symbols data
 */
export const useSymbols = (options?: RequestOptions): HookResult<SymbolInfo[]> => {
  const [data, setData] = useState<SymbolInfo[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<KTRDRApiError | null>(null);
  
  // Use ref to track if the component is mounted
  const isMounted = useRef(true);
  // Use ref to store the abort controller
  const controllerRef = useRef<AbortController | null>(null);
  
  const fetchData = useCallback(async () => {
    if (!isMounted.current) return;
    
    setIsLoading(true);
    setError(null);
    
    // Cancel any previous requests
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    
    // Create a new controller for this request
    const controller = new AbortController();
    controllerRef.current = controller;
    
    try {
      const enhancedOptions = { 
        ...options,
        signal: controller.signal
      };
      
      const symbols = await dataApi.getSymbols(enhancedOptions);
      
      if (isMounted.current) {
        setData(symbols);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && isMounted.current) {
        setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
          'UNKNOWN_ERROR',
          'An unknown error occurred when fetching symbols',
          { originalError: String(err) }
        ));
      }
    } finally {
      if (isMounted.current) {
        setIsLoading(false);
      }
    }
  }, [options]);

  useEffect(() => {
    fetchData();
    
    return () => {
      isMounted.current = false;
      // Abort any in-flight requests when unmounting
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};

/**
 * Hook for retrieving available timeframes
 * @param options Request options
 * @returns Hook result with timeframes data
 */
export const useTimeframes = (options?: RequestOptions): HookResult<TimeframeInfo[]> => {
  const [data, setData] = useState<TimeframeInfo[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<KTRDRApiError | null>(null);
  
  // Use ref to track if the component is mounted
  const isMounted = useRef(true);
  // Use ref to store the abort controller
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!isMounted.current) return;
    
    setIsLoading(true);
    setError(null);
    
    // Cancel any previous requests
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    
    // Create a new controller for this request
    const controller = new AbortController();
    controllerRef.current = controller;
    
    try {
      const enhancedOptions = { 
        ...options,
        signal: controller.signal
      };
      
      const timeframes = await dataApi.getTimeframes(enhancedOptions);
      
      if (isMounted.current) {
        setData(timeframes);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && isMounted.current) {
        setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
          'UNKNOWN_ERROR',
          'An unknown error occurred when fetching timeframes',
          { originalError: String(err) }
        ));
      }
    } finally {
      if (isMounted.current) {
        setIsLoading(false);
      }
    }
  }, [options]);

  useEffect(() => {
    fetchData();
    
    return () => {
      isMounted.current = false;
      // Abort any in-flight requests when unmounting
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};

/**
 * Hook for loading OHLCV data
 * @param params Data load parameters (symbol, timeframe, etc.)
 * @param options Request options
 * @returns Hook result with OHLCV data
 */
export const useOHLCVData = (
  params: DataLoadParams | null,
  options?: RequestOptions
): HookResult<OHLCVData> => {
  const [data, setData] = useState<OHLCVData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<KTRDRApiError | null>(null);
  
  // Use ref to track if the component is mounted
  const isMounted = useRef(true);
  // Use ref to store the abort controller
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!params || !isMounted.current) {
      return;
    }

    setIsLoading(true);
    setError(null);
    
    // Cancel any previous requests
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    
    // Create a new controller for this request
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const enhancedOptions = { 
        ...options,
        signal: controller.signal
      };
      
      const ohlcvData = await dataApi.loadData(params, enhancedOptions);
      
      if (isMounted.current) {
        setData(ohlcvData);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && isMounted.current) {
        setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
          'UNKNOWN_ERROR',
          'An unknown error occurred when loading OHLCV data',
          { originalError: String(err) }
        ));
      }
    } finally {
      if (isMounted.current) {
        setIsLoading(false);
      }
    }
  }, [params, options]);

  useEffect(() => {
    if (params) {
      fetchData();
    }
    
    return () => {
      isMounted.current = false;
      // Abort any in-flight requests when unmounting
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, [params, fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};

/**
 * Hook for getting data range information
 * @param symbol Symbol
 * @param timeframe Timeframe
 * @param options Request options
 * @returns Hook result with data range information
 */
export const useDataRange = (
  symbol: string | null,
  timeframe: string | null,
  options?: RequestOptions
): HookResult<DataRangeInfo> => {
  const [data, setData] = useState<DataRangeInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<KTRDRApiError | null>(null);
  
  // Use ref to track if the component is mounted
  const isMounted = useRef(true);
  // Use ref to store the abort controller
  const controllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol || !timeframe || !isMounted.current) {
      return;
    }

    setIsLoading(true);
    setError(null);
    
    // Cancel any previous requests
    if (controllerRef.current) {
      controllerRef.current.abort();
    }
    
    // Create a new controller for this request
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const enhancedOptions = { 
        ...options,
        signal: controller.signal
      };
      
      const rangeData = await dataApi.getDataRange(symbol, timeframe, enhancedOptions);
      
      if (isMounted.current) {
        setData(rangeData);
      }
    } catch (err) {
      if (err.name !== 'AbortError' && isMounted.current) {
        setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
          'UNKNOWN_ERROR',
          'An unknown error occurred when fetching data range',
          { originalError: String(err) }
        ));
      }
    } finally {
      if (isMounted.current) {
        setIsLoading(false);
      }
    }
  }, [symbol, timeframe, options]);

  useEffect(() => {
    if (symbol && timeframe) {
      fetchData();
    }
    
    return () => {
      isMounted.current = false;
      // Abort any in-flight requests when unmounting
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, [symbol, timeframe, fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};