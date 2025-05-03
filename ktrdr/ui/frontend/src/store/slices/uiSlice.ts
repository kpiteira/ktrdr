import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ThemeMode } from '@/types/ui';

// Define the UI state interface
interface UIState {
  theme: ThemeMode;
  sidebarOpen: boolean;
  currentView: string;
  chartSettings: {
    height: number;
    showVolume: boolean;
    showGridlines: boolean;
  };
}

// Initialize the UI state
const initialState: UIState = {
  theme: 'light',
  sidebarOpen: true,
  currentView: 'dashboard',
  chartSettings: {
    height: 500,
    showVolume: true,
    showGridlines: true,
  },
};

// Create the UI slice
export const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setTheme: (state, action: PayloadAction<ThemeMode>) => {
      state.theme = action.payload;
    },
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setCurrentView: (state, action: PayloadAction<string>) => {
      state.currentView = action.payload;
    },
    updateChartSettings: (state, action: PayloadAction<Partial<UIState['chartSettings']>>) => {
      state.chartSettings = { ...state.chartSettings, ...action.payload };
    },
  },
});

// Export actions and reducer
export const { setTheme, toggleSidebar, setCurrentView, updateChartSettings } = uiSlice.actions;
export default uiSlice.reducer;