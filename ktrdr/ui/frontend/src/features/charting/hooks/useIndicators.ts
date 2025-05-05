import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../../../app/store';
import { 
  fetchAvailableIndicators, 
  calculateIndicatorData,
  addIndicator,
  removeIndicator,
  updateIndicator,
  clearIndicators,
  IndicatorConfig
} from '../store/indicatorSlice';

/**
 * Hook for accessing and managing indicator data
 */
export const useIndicators = () => {
  const dispatch = useDispatch<AppDispatch>();
  const {
    availableIndicators,
    selectedIndicators,
    indicatorData,
    loadingStatus,
    error
  } = useSelector((state: RootState) => state.indicators);

  const loadAvailableIndicators = async () => {
    try {
      await dispatch(fetchAvailableIndicators()).unwrap();
      return true;
    } catch (error) {
      console.error('Error loading available indicators:', error);
      throw error;
    }
  };

  const calculateIndicators = async (symbol: string, timeframe: string) => {
    if (selectedIndicators.length === 0) {
      return {};
    }
    
    try {
      const result = await dispatch(calculateIndicatorData({
        symbol,
        timeframe,
        indicators: selectedIndicators
      })).unwrap();
      return result;
    } catch (error) {
      console.error('Error calculating indicators:', error);
      throw error;
    }
  };

  const addSelectedIndicator = (indicator: IndicatorConfig) => {
    dispatch(addIndicator(indicator));
  };

  const removeSelectedIndicator = (indicatorName: string) => {
    dispatch(removeIndicator(indicatorName));
  };

  const updateSelectedIndicator = (indicatorName: string, config: Partial<IndicatorConfig>) => {
    dispatch(updateIndicator({ name: indicatorName, config }));
  };

  const resetIndicators = () => {
    dispatch(clearIndicators());
  };

  return {
    availableIndicators,
    selectedIndicators,
    indicatorData,
    isLoading: loadingStatus === 'loading',
    error,
    loadAvailableIndicators,
    calculateIndicators,
    addIndicator: addSelectedIndicator,
    removeIndicator: removeSelectedIndicator,
    updateIndicator: updateSelectedIndicator,
    resetIndicators
  };
};