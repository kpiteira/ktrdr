import { describe, it, expect, beforeEach, vi } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import symbolsReducer, {
  setCurrentSymbol,
  setCurrentTimeframe,
  fetchSymbols,
  fetchTimeframes
} from '@/features/symbols/store/symbolsSlice';

// Create mock API responses
const mockApiResponses = {
  symbols: ['AAPL', 'MSFT', 'GOOG'],
  timeframes: ['1m', '5m', '15m', '1h', '4h', '1d'],
};

// Mock the API endpoints
vi.mock('@/api/endpoints/data', () => ({
  getSymbols: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.symbols)),
  getTimeframes: vi.fn().mockImplementation(() => Promise.resolve(mockApiResponses.timeframes))
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