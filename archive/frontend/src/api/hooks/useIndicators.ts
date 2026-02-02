/**
 * Indicator API hooks for React components
 * Provides custom hooks for indicator-related API endpoints
 */

import { useState, useEffect, useCallback } from 'react';
import { indicatorsApi, RequestOptions, KTRDRApiError } from '../';
import { IndicatorInfo, IndicatorConfig, IndicatorData, DateRangeParams } from '../types';

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
 * Hook for retrieving available indicators
 * @param options Request options
 * @returns Hook result with indicators data
 */
export const useIndicators = (options?: RequestOptions): HookResult<IndicatorInfo[]> => {
  const [data, setData] = useState<IndicatorInfo[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<KTRDRApiError | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const indicators = await indicatorsApi.getIndicators(options);
      setData(indicators);
    } catch (err) {
      setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
        'UNKNOWN_ERROR',
        'An unknown error occurred when fetching indicators',
        { originalError: String(err) }
      ));
    } finally {
      setIsLoading(false);
    }
  }, [options]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};

/**
 * Hook for calculating indicator values
 * @param symbol Symbol
 * @param timeframe Timeframe
 * @param indicators Indicator configurations
 * @param dateRange Optional date range parameters
 * @param options Request options 
 * @returns Hook result with calculated indicator data
 */
export const useIndicatorData = (
  symbol: string | null,
  timeframe: string | null,
  indicators: IndicatorConfig[] | null,
  dateRange?: DateRangeParams,
  options?: RequestOptions
): HookResult<IndicatorData> => {
  const [data, setData] = useState<IndicatorData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<KTRDRApiError | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol || !timeframe || !indicators || !indicators.length) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const indicatorData = await indicatorsApi.calculateIndicators(
        symbol,
        timeframe,
        indicators,
        dateRange,
        options
      );
      setData(indicatorData);
    } catch (err) {
      setError(err instanceof KTRDRApiError ? err : new KTRDRApiError(
        'UNKNOWN_ERROR',
        'An unknown error occurred when calculating indicators',
        { originalError: String(err) }
      ));
    } finally {
      setIsLoading(false);
    }
  }, [symbol, timeframe, indicators, dateRange, options]);

  useEffect(() => {
    if (symbol && timeframe && indicators && indicators.length > 0) {
      fetchData();
    }
  }, [symbol, timeframe, indicators, dateRange, fetchData]);

  return { data, isLoading, error, refetch: fetchData };
};