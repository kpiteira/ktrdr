import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../../app/store';
import { fetchOHLCVData, clearOHLCVData } from '../store/chartingSlice';

/**
 * Hook for accessing and managing OHLCV data in charts
 */
export const useChartData = () => {
  const dispatch = useDispatch<AppDispatch>();
  const {
    ohlcvData,
    dataStatus,
    error
  } = useSelector((state: RootState) => state.charting);

  const loadData = async ({ 
    symbol, 
    timeframe, 
    startDate, 
    endDate 
  }: { 
    symbol: string; 
    timeframe: string; 
    startDate?: string; 
    endDate?: string;
  }) => {
    try {
      const result = await dispatch(fetchOHLCVData({ symbol, timeframe, startDate, endDate })).unwrap();
      return result;
    } catch (error) {
      console.error('Error loading OHLCV data:', error);
      throw error;
    }
  };

  const resetData = () => {
    dispatch(clearOHLCVData());
  };

  return {
    ohlcvData,
    dataStatus,
    errorMessage: error,
    isLoading: dataStatus === 'loading',
    loadData,
    resetData
  };
};