import { useState, useEffect } from 'react';
import { useOHLCVData } from '../../../api/hooks/useData';
import type { OHLCVData } from '../../../api/types';

/**
 * Custom hook for fetching OHLCV data specifically for chart views
 * Wraps the base useOHLCVData hook with chart-specific functionality
 * 
 * @param symbol - Trading symbol (e.g., 'AAPL', 'MSFT')
 * @param timeframe - Time interval (e.g., '1d', '1h', '5m')
 * @param additionalOptions - Optional parameters like date range
 */
export const useChartData = (
  symbol: string | null,
  timeframe: string,
  additionalOptions?: {
    startDate?: string;
    endDate?: string;
  }
) => {
  // Use the core OHLCV data hook
  const ohlcvResult = useOHLCVData(
    symbol ? {
      symbol,
      timeframe,
      startDate: additionalOptions?.startDate,
      endDate: additionalOptions?.endDate
    } : null
  );

  // Track if this is the initial data load
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  // Set initialLoadComplete to true after first successful data load
  useEffect(() => {
    if (ohlcvResult.data && !initialLoadComplete) {
      setInitialLoadComplete(true);
    }
  }, [ohlcvResult.data, initialLoadComplete]);

  // Return the results from the OHLCV hook plus our additional state
  return {
    ...ohlcvResult,
    initialLoadComplete
  };
};

export default useChartData;