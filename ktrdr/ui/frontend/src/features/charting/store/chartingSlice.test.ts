import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import chartingReducer, {
  fetchOHLCVData,
  clearOHLCVData
} from '@/features/charting/store/chartingSlice';
import { mockApiResponses } from '@/tests/test-utils';
import { loadData } from '@/api/endpoints/data';

// Mock the API endpoints
vi.mock('@/api/endpoints/data', () => ({
  loadData: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.ohlcvData)),
  getSymbols: vi.fn(),
  getTimeframes: vi.fn()
}));

describe('chartingSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Create a fresh store for each test
    store = configureStore({
      reducer: { charting: chartingReducer }
    });
    
    // Clear all mocks before each test
    vi.clearAllMocks();
  });

  describe('Synchronous actions', () => {
    it('should handle clearOHLCVData', () => {
      // Arrange - set up initial state with data
      store.dispatch({ 
        type: 'charting/fetchOHLCVData/fulfilled', 
        payload: mockApiResponses.ohlcvData 
      });
      
      // Verify data is loaded
      expect(store.getState().charting.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      
      // Act - clear the data
      store.dispatch(clearOHLCVData());
      
      // Assert - check that data was cleared
      expect(store.getState().charting.ohlcvData).toBeNull();
      expect(store.getState().charting.dataStatus).toBe('idle');
      expect(store.getState().charting.error).toBeNull();
    });
  });

  describe('Async thunks', () => {
    it('should handle fetchOHLCVData.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchOHLCVData({ 
        symbol: 'AAPL', 
        timeframe: '1d' 
      }));
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().charting.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      expect(store.getState().charting.dataStatus).toBe('succeeded');
      expect(store.getState().charting.error).toBeNull();
    });

    it('should handle fetchOHLCVData.rejected', async () => {
      // Arrange - make the API call fail
      const errorMessage = 'Network error';
      vi.mocked(loadData).mockRejectedValueOnce(new Error(errorMessage));
      
      // Act & Assert - dispatch the thunk and expect it to be rejected
      try {
        await store.dispatch(fetchOHLCVData({ 
          symbol: 'AAPL', 
          timeframe: '1d' 
        }));
      } catch (err) {
        // This is expected
      }
      
      // Assert - check that error state was set correctly
      expect(store.getState().charting.dataStatus).toBe('failed');
      expect(store.getState().charting.error).toContain(errorMessage);
    });
  });

  describe('Integration tests', () => {
    it('should manage a complete chart data loading workflow', async () => {
      // Act - dispatch a sequence of actions that mimics a typical workflow
      await store.dispatch(fetchOHLCVData({ 
        symbol: 'AAPL', 
        timeframe: '1d',
        startDate: '2023-01-01',
        endDate: '2023-01-31'
      }));
      
      // Assert - check the final state
      const state = store.getState().charting;
      expect(state.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      expect(state.dataStatus).toBe('succeeded');
      expect(state.error).toBeNull();
      
      // Act - clear the data
      store.dispatch(clearOHLCVData());
      
      // Assert - check that data was cleared
      expect(store.getState().charting.ohlcvData).toBeNull();
    });
  });
});