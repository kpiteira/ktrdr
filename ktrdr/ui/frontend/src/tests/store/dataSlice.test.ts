import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import dataReducer, {
  setCurrentSymbol,
  setCurrentTimeframe,
  clearData,
  fetchData,
  fetchSymbols,
  fetchTimeframes
} from '@/store/slices/dataSlice';
import { mockApiResponses } from '../test-utils';
import { loadData, getSymbols, getTimeframes } from '@/api/endpoints/data';

// Mock the API endpoints
vi.mock('@/api/endpoints/data', () => ({
  loadData: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.ohlcvData)),
  getSymbols: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.symbols)),
  getTimeframes: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.timeframes))
}));

describe('dataSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Create a fresh store for each test
    store = configureStore({
      reducer: { data: dataReducer }
    });
    
    // Clear all mocks before each test
    vi.clearAllMocks();
  });

  describe('Synchronous actions', () => {
    it('should handle setCurrentSymbol', () => {
      // Act - dispatch the action
      store.dispatch(setCurrentSymbol('AAPL'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().data.currentSymbol).toBe('AAPL');
    });

    it('should handle setCurrentTimeframe', () => {
      // Act - dispatch the action
      store.dispatch(setCurrentTimeframe('1d'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().data.currentTimeframe).toBe('1d');
    });

    it('should handle clearData', () => {
      // Arrange - set up initial state with data
      store.dispatch({ 
        type: 'data/fetchData/fulfilled', 
        payload: mockApiResponses.ohlcvData 
      });
      
      // Verify data is loaded
      expect(store.getState().data.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      
      // Act - clear the data
      store.dispatch(clearData());
      
      // Assert - check that data was cleared
      expect(store.getState().data.ohlcvData).toBeNull();
      expect(store.getState().data.dataStatus).toBe('idle');
      expect(store.getState().data.error).toBeNull();
    });
  });

  describe('Async thunks', () => {
    it('should handle fetchData.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchData({ 
        symbol: 'AAPL', 
        timeframe: '1d' 
      }));
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().data.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      expect(store.getState().data.dataStatus).toBe('succeeded');
      expect(store.getState().data.error).toBeNull();
    });

    it('should handle fetchData.rejected', async () => {
      // Arrange - make the API call fail
      const errorMessage = 'Network error';
      vi.mocked(loadData).mockRejectedValueOnce(new Error(errorMessage));
      
      // Act & Assert - dispatch the thunk and expect it to be rejected
      try {
        await store.dispatch(fetchData({ 
          symbol: 'AAPL', 
          timeframe: '1d' 
        }));
      } catch (err) {
        // This is expected
      }
      
      // Assert - check that error state was set correctly
      expect(store.getState().data.dataStatus).toBe('failed');
      expect(store.getState().data.error).toContain(errorMessage);
    });

    it('should handle fetchSymbols.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchSymbols());
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().data.symbols).toEqual(mockApiResponses.symbols);
      expect(store.getState().data.symbolsStatus).toBe('succeeded');
    });

    it('should handle fetchTimeframes.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchTimeframes());
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().data.timeframes).toEqual(mockApiResponses.timeframes);
      expect(store.getState().data.timeframesStatus).toBe('succeeded');
    });
  });

  describe('Integration tests', () => {
    it('should manage a complete data loading workflow', async () => {
      // Act - dispatch a sequence of actions that mimics a typical workflow
      await store.dispatch(fetchSymbols());
      await store.dispatch(fetchTimeframes());
      store.dispatch(setCurrentSymbol('AAPL'));
      store.dispatch(setCurrentTimeframe('1d'));
      await store.dispatch(fetchData({ 
        symbol: 'AAPL', 
        timeframe: '1d' 
      }));
      
      // Assert - check the final state
      const state = store.getState().data;
      expect(state.symbols).toEqual(mockApiResponses.symbols);
      expect(state.timeframes).toEqual(mockApiResponses.timeframes);
      expect(state.currentSymbol).toBe('AAPL');
      expect(state.currentTimeframe).toBe('1d');
      expect(state.ohlcvData).toEqual(mockApiResponses.ohlcvData);
      expect(state.symbolsStatus).toBe('succeeded');
      expect(state.timeframesStatus).toBe('succeeded');
      expect(state.dataStatus).toBe('succeeded');
    });
  });
});