import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { loadData, getSymbols, getTimeframes } from '../../api/endpoints/data';
import type { OHLCVData } from '../../types/data';

// Define types for the state
interface DataState {
  symbols: string[];
  timeframes: string[];
  currentSymbol: string | null;
  currentTimeframe: string | null;
  ohlcvData: OHLCVData | null;
  symbolsStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  timeframesStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  dataStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// Initialize the state
const initialState: DataState = {
  symbols: [],
  timeframes: [],
  currentSymbol: null,
  currentTimeframe: null,
  ohlcvData: null,
  symbolsStatus: 'idle',
  timeframesStatus: 'idle',
  dataStatus: 'idle',
  error: null
};

// Create async thunks for data operations
export const fetchData = createAsyncThunk(
  'data/fetchData',
  async ({ symbol, timeframe, startDate, endDate }: { 
    symbol: string; 
    timeframe: string; 
    startDate?: string; 
    endDate?: string;
  }) => {
    try {
      const response = await loadData({ symbol, timeframe, startDate, endDate });
      return response;
    } catch (error) {
      console.error('Error fetching data:', error);
      throw error;
    }
  }
);

export const fetchSymbols = createAsyncThunk(
  'data/fetchSymbols',
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
  'data/fetchTimeframes',
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

// Create the data slice
const dataSlice = createSlice({
  name: 'data',
  initialState,
  reducers: {
    setCurrentSymbol: (state, action: PayloadAction<string | null>) => {
      state.currentSymbol = action.payload;
    },
    setCurrentTimeframe: (state, action: PayloadAction<string | null>) => {
      state.currentTimeframe = action.payload;
    },
    clearData: (state) => {
      state.ohlcvData = null;
      state.dataStatus = 'idle';
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    // Handle fetchData
    builder
      .addCase(fetchData.pending, (state) => {
        state.dataStatus = 'loading';
        state.error = null;
      })
      .addCase(fetchData.fulfilled, (state, action) => {
        state.dataStatus = 'succeeded';
        state.ohlcvData = action.payload;
      })
      .addCase(fetchData.rejected, (state, action) => {
        state.dataStatus = 'failed';
        state.error = action.error.message || 'Failed to load data';
      });
    
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
export const { setCurrentSymbol, setCurrentTimeframe, clearData } = dataSlice.actions;
export default dataSlice.reducer;