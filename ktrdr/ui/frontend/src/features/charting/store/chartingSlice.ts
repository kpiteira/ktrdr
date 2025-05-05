import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { loadData } from '../../../api/endpoints/data';

// Define type for OHLCV data
export interface OHLCVData {
  dates: string[];
  ohlcv: number[][];
  metadata?: {
    symbol?: string;
    timeframe?: string;
    start?: string;
    end?: string;
    points?: number;
  };
}

// Define types for the charting state
export interface ChartingState {
  ohlcvData: OHLCVData | null;
  dataStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// Initialize the state
const initialState: ChartingState = {
  ohlcvData: null,
  dataStatus: 'idle',
  error: null
};

// Create async thunk for fetching OHLCV data
export const fetchOHLCVData = createAsyncThunk(
  'charting/fetchOHLCVData',
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
      console.error('Error fetching OHLCV data:', error);
      throw error;
    }
  }
);

// Create the charting slice
const chartingSlice = createSlice({
  name: 'charting',
  initialState,
  reducers: {
    clearOHLCVData: (state) => {
      state.ohlcvData = null;
      state.dataStatus = 'idle';
      state.error = null;
    }
  },
  extraReducers: (builder) => {
    // Handle fetchOHLCVData
    builder
      .addCase(fetchOHLCVData.pending, (state) => {
        state.dataStatus = 'loading';
        state.error = null;
      })
      .addCase(fetchOHLCVData.fulfilled, (state, action) => {
        state.dataStatus = 'succeeded';
        state.ohlcvData = action.payload;
      })
      .addCase(fetchOHLCVData.rejected, (state, action) => {
        state.dataStatus = 'failed';
        state.error = action.error.message || 'Failed to load OHLCV data';
      });
  }
});

// Export actions and reducer
export const { clearOHLCVData } = chartingSlice.actions;
export default chartingSlice.reducer;