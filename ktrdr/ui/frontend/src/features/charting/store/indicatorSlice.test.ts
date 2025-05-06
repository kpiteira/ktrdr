import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import indicatorReducer, {
  addIndicator,
  removeIndicator,
  updateIndicator,
  clearIndicators,
  fetchAvailableIndicators,
  calculateIndicatorData,
  IndicatorConfig
} from '@/features/charting/store/indicatorSlice';
import { mockApiResponses } from '@/tests/test-utils';

// Mock API endpoints for indicators
vi.mock('@/api/endpoints/indicators', () => ({
  getIndicators: vi.fn().mockResolvedValue([
    { 
      name: 'SMA', 
      description: 'Simple Moving Average', 
      defaultParameters: { period: 14 },
      category: 'trend',
      availableSources: ['close']
    },
    { 
      name: 'RSI', 
      description: 'Relative Strength Index', 
      defaultParameters: { period: 14 },
      category: 'momentum',
      availableSources: ['close']
    }
  ]),
  calculateIndicators: vi.fn().mockResolvedValue({
    SMA: [1, 2, 3, 4, 5],
    RSI: [30, 40, 50, 60, 70]
  })
}));

describe('indicatorSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Create a fresh store for each test
    store = configureStore({
      reducer: { indicators: indicatorReducer }
    });
    
    // Clear all mocks before each test
    vi.clearAllMocks();
  });

  describe('Synchronous actions', () => {
    it('should handle addIndicator', () => {
      // Define a sample indicator
      const smaIndicator: IndicatorConfig = {
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close',
        panel: 'main',
        color: '#FF0000',
        visible: true
      };
      
      // Act - dispatch the action
      store.dispatch(addIndicator(smaIndicator));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().indicators.selectedIndicators).toHaveLength(1);
      expect(store.getState().indicators.selectedIndicators[0]).toEqual(smaIndicator);
      
      // Act - add another indicator
      const rsiIndicator: IndicatorConfig = {
        name: 'RSI',
        parameters: { period: 14 },
        source: 'close',
        panel: 'sub',
        color: '#0000FF',
        visible: true
      };
      store.dispatch(addIndicator(rsiIndicator));
      
      // Assert - check that both indicators are in state
      expect(store.getState().indicators.selectedIndicators).toHaveLength(2);
    });

    it('should handle replacing an existing indicator', () => {
      // Add an initial indicator
      const smaIndicator: IndicatorConfig = {
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close'
      };
      store.dispatch(addIndicator(smaIndicator));
      
      // Act - add a modified version of the same indicator
      const updatedSmaIndicator: IndicatorConfig = {
        name: 'SMA',
        parameters: { period: 21 },
        source: 'high',
        color: '#00FF00'
      };
      store.dispatch(addIndicator(updatedSmaIndicator));
      
      // Assert - check that the indicator was replaced, not added
      expect(store.getState().indicators.selectedIndicators).toHaveLength(1);
      expect(store.getState().indicators.selectedIndicators[0]).toEqual(updatedSmaIndicator);
    });

    it('should handle removeIndicator', () => {
      // Add a couple of indicators first
      store.dispatch(addIndicator({
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close'
      }));
      store.dispatch(addIndicator({
        name: 'RSI',
        parameters: { period: 14 },
        source: 'close'
      }));
      
      // Act - remove one indicator
      store.dispatch(removeIndicator('SMA'));
      
      // Assert - check that only the RSI indicator remains
      expect(store.getState().indicators.selectedIndicators).toHaveLength(1);
      expect(store.getState().indicators.selectedIndicators[0].name).toBe('RSI');
    });

    it('should handle updateIndicator', () => {
      // Add an indicator first
      store.dispatch(addIndicator({
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close',
        color: '#FF0000'
      }));
      
      // Act - update the indicator
      store.dispatch(updateIndicator({ 
        name: 'SMA', 
        config: { 
          parameters: { period: 21 },
          color: '#00FF00'
        } 
      }));
      
      // Assert - check that the indicator was updated correctly
      const updatedIndicator = store.getState().indicators.selectedIndicators[0];
      expect(updatedIndicator.parameters.period).toBe(21);
      expect(updatedIndicator.color).toBe('#00FF00');
      expect(updatedIndicator.source).toBe('close'); // Should retain this field
    });

    it('should handle clearIndicators', () => {
      // Add a couple of indicators first
      store.dispatch(addIndicator({
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close'
      }));
      store.dispatch(addIndicator({
        name: 'RSI',
        parameters: { period: 14 },
        source: 'close'
      }));
      
      // Also add some mock indicator data
      store.dispatch({
        type: 'indicators/calculateIndicatorData/fulfilled',
        payload: { SMA: [1, 2, 3], RSI: [50, 60, 70] }
      });
      
      // Act - clear everything
      store.dispatch(clearIndicators());
      
      // Assert - check that all indicators and data were cleared
      expect(store.getState().indicators.selectedIndicators).toHaveLength(0);
      expect(store.getState().indicators.indicatorData).toEqual({});
      expect(store.getState().indicators.loadingStatus).toBe('idle');
    });
  });

  describe('Async thunks', () => {
    it('should handle fetchAvailableIndicators', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchAvailableIndicators());
      
      // Assert - check state after thunk completes
      expect(store.getState().indicators.availableIndicators).toHaveLength(2);
      expect(store.getState().indicators.availableIndicators[0].name).toBe('SMA');
      expect(store.getState().indicators.availableIndicators[1].name).toBe('RSI');
      expect(store.getState().indicators.loadingStatus).toBe('succeeded');
    });

    it('should handle calculateIndicatorData', async () => {
      // Add some indicators first
      store.dispatch(addIndicator({
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close'
      }));
      store.dispatch(addIndicator({
        name: 'RSI',
        parameters: { period: 14 },
        source: 'close'
      }));
      
      // Act - dispatch the async thunk
      await store.dispatch(calculateIndicatorData({
        symbol: 'AAPL',
        timeframe: '1d',
        indicators: store.getState().indicators.selectedIndicators
      }));
      
      // Assert - check state after thunk completes
      expect(store.getState().indicators.indicatorData).toEqual({
        SMA: [1, 2, 3, 4, 5],
        RSI: [30, 40, 50, 60, 70]
      });
      expect(store.getState().indicators.loadingStatus).toBe('succeeded');
    });
  });

  describe('Integration tests', () => {
    it('should manage a complete indicator workflow', async () => {
      // Step 1: Fetch available indicators
      await store.dispatch(fetchAvailableIndicators());
      
      // Step 2: Add indicators
      store.dispatch(addIndicator({
        name: 'SMA',
        parameters: { period: 14 },
        source: 'close',
        panel: 'main',
        color: '#FF0000'
      }));
      
      store.dispatch(addIndicator({
        name: 'RSI',
        parameters: { period: 14 },
        source: 'close',
        panel: 'sub',
        color: '#0000FF'
      }));
      
      // Step 3: Calculate the indicators
      await store.dispatch(calculateIndicatorData({
        symbol: 'AAPL',
        timeframe: '1d',
        indicators: store.getState().indicators.selectedIndicators
      }));
      
      // Step 4: Update an indicator
      store.dispatch(updateIndicator({
        name: 'SMA',
        config: { parameters: { period: 21 } }
      }));
      
      // Step 5: Re-calculate with updated parameters
      await store.dispatch(calculateIndicatorData({
        symbol: 'AAPL',
        timeframe: '1d',
        indicators: store.getState().indicators.selectedIndicators
      }));
      
      // Final state checks
      const state = store.getState().indicators;
      expect(state.availableIndicators).toHaveLength(2);
      expect(state.selectedIndicators).toHaveLength(2);
      expect(state.selectedIndicators[0].parameters.period).toBe(21);
      expect(state.indicatorData).toHaveProperty('SMA');
      expect(state.indicatorData).toHaveProperty('RSI');
    });
  });
});