import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import symbolsReducer, {
  setCurrentSymbol,
  setCurrentTimeframe,
  fetchSymbols,
  fetchTimeframes
} from '@/features/symbols/store/symbolsSlice';
import { mockApiResponses } from '../../tests/test-utils';
import { getSymbols, getTimeframes } from '@/api/endpoints/data';

// Mock the API endpoints
vi.mock('@/api/endpoints/data', () => ({
  getSymbols: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.symbols)),
  getTimeframes: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.timeframes)),
  loadData: vi.fn()  // Mock loadData even though we don't use it directly
}));

describe('symbolsSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Create a fresh store for each test
    store = configureStore({
      reducer: { symbols: symbolsReducer }
    });
    
    // Clear all mocks before each test
    vi.clearAllMocks();
  });

  describe('Synchronous actions', () => {
    it('should handle setCurrentSymbol', () => {
      // Act - dispatch the action
      store.dispatch(setCurrentSymbol('AAPL'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().symbols.currentSymbol).toBe('AAPL');
    });

    it('should handle setCurrentTimeframe', () => {
      // Act - dispatch the action
      store.dispatch(setCurrentTimeframe('1d'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().symbols.currentTimeframe).toBe('1d');
    });
  });

  describe('Async thunks', () => {
    it('should handle fetchSymbols.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchSymbols());
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().symbols.symbols).toEqual(mockApiResponses.symbols);
      expect(store.getState().symbols.symbolsStatus).toBe('succeeded');
    });

    it('should handle fetchSymbols.rejected', async () => {
      // Arrange - make the API call fail
      const errorMessage = 'Network error';
      vi.mocked(getSymbols).mockRejectedValueOnce(new Error(errorMessage));
      
      // Act & Assert - dispatch the thunk and expect it to be rejected
      try {
        await store.dispatch(fetchSymbols());
      } catch (err) {
        // This is expected
      }
      
      // Assert - check that error state was set correctly
      expect(store.getState().symbols.symbolsStatus).toBe('failed');
      expect(store.getState().symbols.error).toContain(errorMessage);
    });

    it('should handle fetchTimeframes.fulfilled', async () => {
      // Act - dispatch the async thunk
      await store.dispatch(fetchTimeframes());
      
      // Assert - check the loading state sequence and final state
      expect(store.getState().symbols.timeframes).toEqual(mockApiResponses.timeframes);
      expect(store.getState().symbols.timeframesStatus).toBe('succeeded');
    });
  });

  describe('Integration tests', () => {
    it('should manage a complete symbol selection workflow', async () => {
      // Act - dispatch a sequence of actions that mimics a typical workflow
      await store.dispatch(fetchSymbols());
      await store.dispatch(fetchTimeframes());
      store.dispatch(setCurrentSymbol('AAPL'));
      store.dispatch(setCurrentTimeframe('1d'));
      
      // Assert - check the final state
      const state = store.getState().symbols;
      expect(state.symbols).toEqual(mockApiResponses.symbols);
      expect(state.timeframes).toEqual(mockApiResponses.timeframes);
      expect(state.currentSymbol).toBe('AAPL');
      expect(state.currentTimeframe).toBe('1d');
      expect(state.symbolsStatus).toBe('succeeded');
      expect(state.timeframesStatus).toBe('succeeded');
    });
  });
});