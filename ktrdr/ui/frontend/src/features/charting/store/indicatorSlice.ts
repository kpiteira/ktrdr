import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { getIndicators, calculateIndicators } from '../../../api/endpoints/indicators';

// Define types for indicator metadata and configuration
export interface IndicatorMetadata {
  name: string;
  description: string;
  defaultParameters: Record<string, any>;
  category: string;
  availableSources: string[];
}

export interface IndicatorConfig {
  name: string;
  parameters: Record<string, any>;
  source?: string;
  panel?: string;
  color?: string;
  visible?: boolean;
}

// Define types for the indicator state
export interface IndicatorState {
  availableIndicators: IndicatorMetadata[];
  selectedIndicators: IndicatorConfig[];
  indicatorData: Record<string, number[]>;
  loadingStatus: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// Create async thunk for fetching available indicators
export const fetchAvailableIndicators = createAsyncThunk(
  'indicators/fetchAvailableIndicators',
  async (_, { rejectWithValue }) => {
    try {
      const indicatorsInfo = await getIndicators();
      // Transform API response to match our state structure, adapting to actual API response format
      const indicators: IndicatorMetadata[] = indicatorsInfo.map(info => ({
        name: info.name,
        description: info.description,
        // Handle API format differences with fallbacks
        defaultParameters: info.default_parameters || info.defaultParameters || {},
        category: info.category || 'general',
        availableSources: info.available_sources || info.availableSources || ['close'],
      }));
      return indicators;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Unknown error occurred');
    }
  }
);

// Create async thunk for calculating indicators
export const calculateIndicatorData = createAsyncThunk(
  'indicators/calculateIndicatorData',
  async ({ 
    symbol, 
    timeframe, 
    indicators 
  }: { 
    symbol: string; 
    timeframe: string; 
    indicators: IndicatorConfig[] 
  }, { rejectWithValue }) => {
    try {
      const response = await calculateIndicators(symbol, timeframe, indicators);
      // Handle different API response formats
      return response.indicators || response;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Unknown error occurred');
    }
  }
);

// Initialize the indicator state
const initialState: IndicatorState = {
  availableIndicators: [],
  selectedIndicators: [],
  indicatorData: {},
  loadingStatus: 'idle',
  error: null,
};

// Create the indicator slice
export const indicatorSlice = createSlice({
  name: 'indicators',
  initialState,
  reducers: {
    addIndicator: (state, action: PayloadAction<IndicatorConfig>) => {
      // Check if indicator already exists
      const existingIndex = state.selectedIndicators.findIndex(
        (indicator: IndicatorConfig) => indicator.name === action.payload.name
      );
      
      if (existingIndex >= 0) {
        // Replace existing indicator with the same name
        state.selectedIndicators[existingIndex] = action.payload;
      } else {
        // Add new indicator
        state.selectedIndicators.push(action.payload);
      }
    },
    removeIndicator: (state, action: PayloadAction<string>) => {
      state.selectedIndicators = state.selectedIndicators.filter(
        (indicator: IndicatorConfig) => indicator.name !== action.payload
      );
      // Also remove indicator data if it exists
      if (state.indicatorData[action.payload]) {
        const { [action.payload]: _, ...rest } = state.indicatorData;
        state.indicatorData = rest;
      }
    },
    updateIndicator: (state, action: PayloadAction<{ name: string; config: Partial<IndicatorConfig> }>) => {
      const { name, config } = action.payload;
      const indicatorIndex = state.selectedIndicators.findIndex(
        (ind: IndicatorConfig) => ind.name === name
      );
      
      if (indicatorIndex >= 0) {
        state.selectedIndicators[indicatorIndex] = {
          ...state.selectedIndicators[indicatorIndex],
          ...config
        };
      }
    },
    clearIndicators: (state) => {
      state.selectedIndicators = [];
      state.indicatorData = {};
      state.loadingStatus = 'idle';
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Handle fetchAvailableIndicators states
      .addCase(fetchAvailableIndicators.pending, (state) => {
        state.loadingStatus = 'loading';
        state.error = null;
      })
      .addCase(fetchAvailableIndicators.fulfilled, (state, action) => {
        state.loadingStatus = 'succeeded';
        state.availableIndicators = action.payload;
      })
      .addCase(fetchAvailableIndicators.rejected, (state, action) => {
        state.loadingStatus = 'failed';
        state.error = action.payload as string || 'Unknown error';
      })
      // Handle calculateIndicatorData states
      .addCase(calculateIndicatorData.pending, (state) => {
        state.loadingStatus = 'loading';
        state.error = null;
      })
      .addCase(calculateIndicatorData.fulfilled, (state, action) => {
        state.loadingStatus = 'succeeded';
        state.indicatorData = action.payload;
      })
      .addCase(calculateIndicatorData.rejected, (state, action) => {
        state.loadingStatus = 'failed';
        state.error = action.payload as string || 'Unknown error';
      });
  },
});

// Export actions and reducer
export const { 
  addIndicator, 
  removeIndicator, 
  updateIndicator,
  clearIndicators 
} = indicatorSlice.actions;

export default indicatorSlice.reducer;