import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { getSymbols, getTimeframes } from '../../../api/endpoints/data';

// Define types for the symbols state
export interface SymbolsState {
  symbols: string[];
  timeframes: string[];
  currentSymbol: string | null;
  currentTimeframe: string | null;
  symbolsStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  timeframesStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// Initialize the state
const initialState: SymbolsState = {
  symbols: [],
  timeframes: [],
  currentSymbol: null,
  currentTimeframe: null,
  symbolsStatus: 'idle',
  timeframesStatus: 'idle',
  error: null
};

// Create async thunks for symbol data operations
export const fetchSymbols = createAsyncThunk(
  'symbols/fetchSymbols',
  async () => {
    try {
      const symbols = await getSymbols();
      return symbols;
    } catch (error) {
      console.error('Error fetching symbols:', error);
      throw error;
    }
  }
);

export const fetchTimeframes = createAsyncThunk(
  'symbols/fetchTimeframes',
  async () => {
    try {
      const timeframes = await getTimeframes();
      return timeframes;
    } catch (error) {
      console.error('Error fetching timeframes:', error);
      throw error;
    }
  }
);

// Create the symbols slice
const symbolsSlice = createSlice({
  name: 'symbols',
  initialState,
  reducers: {
    setCurrentSymbol: (state, action: PayloadAction<string | null>) => {
      state.currentSymbol = action.payload;
    },
    setCurrentTimeframe: (state, action: PayloadAction<string | null>) => {
      state.currentTimeframe = action.payload;
    }
  },
  extraReducers: (builder) => {
    // Handle fetchSymbols
    builder
      .addCase(fetchSymbols.pending, (state) => {
        state.symbolsStatus = 'loading';
        state.error = null;
      })
      .addCase(fetchSymbols.fulfilled, (state, action) => {
        state.symbolsStatus = 'succeeded';
        // Handle the case where action.payload might be undefined
        if (action.payload) {
          state.symbols = action.payload;
        } else {
          console.warn('Received undefined payload for symbols');
        }
      })
      .addCase(fetchSymbols.rejected, (state, action) => {
        state.symbolsStatus = 'failed';
        state.error = action.error.message || 'Failed to load symbols';
      });
    
    // Handle fetchTimeframes
    builder
      .addCase(fetchTimeframes.pending, (state) => {
        state.timeframesStatus = 'loading';
        state.error = null;
      })
      .addCase(fetchTimeframes.fulfilled, (state, action) => {
        state.timeframesStatus = 'succeeded';
        // Handle the case where action.payload might be undefined
        if (action.payload) {
          state.timeframes = action.payload;
        } else {
          console.warn('Received undefined payload for timeframes');
        }
      })
      .addCase(fetchTimeframes.rejected, (state, action) => {
        state.timeframesStatus = 'failed';
        state.error = action.error.message || 'Failed to load timeframes';
      });
  }
});

// Export actions and reducer
export const { setCurrentSymbol, setCurrentTimeframe } = symbolsSlice.actions;
export default symbolsSlice.reducer;