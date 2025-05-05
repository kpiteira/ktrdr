import { useDispatch, useSelector } from 'react-redux';
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

  const loadMetadata = async () => {
    try {
      await Promise.all([
        dispatch(fetchSymbols()).unwrap(),
        dispatch(fetchTimeframes()).unwrap()
      ]);
      return true;
    } catch (error) {
      console.error('Error loading metadata:', error);
      throw error;
    }
  };

  const selectSymbol = (symbol: string | null) => {
    dispatch(setCurrentSymbol(symbol));
  };

  const selectTimeframe = (timeframe: string | null) => {
    dispatch(setCurrentTimeframe(timeframe));
  };

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