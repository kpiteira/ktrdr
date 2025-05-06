import { useDispatch, useSelector } from 'react-redux';
import { useCallback } from 'react';
import { RootState } from '../../../app/store';
import { 
  fetchSymbols, 
  fetchTimeframes,
  setCurrentSymbol, 
  setCurrentTimeframe 
} from '../store/symbolsSlice';
import { AppDispatch } from '../../../app/store';

/**
 * Hook for accessing and managing symbol selection state
 */
export const useSymbolSelection = () => {
  const dispatch = useDispatch<AppDispatch>();
  const {
    symbols,
    timeframes,
    currentSymbol,
    currentTimeframe,
    symbolsStatus,
    timeframesStatus,
    error
  } = useSelector((state: RootState) => state.symbols);

  // Memoize the loadMetadata function to prevent infinite loops
  const loadMetadata = useCallback(async () => {
    try {
      // Only fetch new data if we're not already loading
      if (symbolsStatus !== 'loading' && timeframesStatus !== 'loading') {
        await Promise.all([
          dispatch(fetchSymbols()).unwrap(),
          dispatch(fetchTimeframes()).unwrap()
        ]);
      }
      return true;
    } catch (error) {
      console.error('Error loading metadata:', error);
      throw error;
    }
  }, [dispatch, symbolsStatus, timeframesStatus]);

  const selectSymbol = useCallback((symbol: string | null) => {
    dispatch(setCurrentSymbol(symbol));
  }, [dispatch]);

  const selectTimeframe = useCallback((timeframe: string | null) => {
    dispatch(setCurrentTimeframe(timeframe));
  }, [dispatch]);

  const hasActiveSelection = Boolean(currentSymbol && currentTimeframe);

  return {
    symbols,
    timeframes,
    currentSymbol,
    currentTimeframe,
    symbolsStatus,
    timeframesStatus,
    error,
    loadMetadata,
    selectSymbol,
    selectTimeframe,
    hasActiveSelection,
    isLoading: symbolsStatus === 'loading' || timeframesStatus === 'loading'
  };
};