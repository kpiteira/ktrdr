# State Management Patterns

This document outlines the state management patterns and best practices used in the KTRDR frontend application.

## Table of Contents

- [State Management Overview](#state-management-overview)
- [Redux Toolkit Implementation](#redux-toolkit-implementation)
- [State Organization](#state-organization)
- [Custom Hooks](#custom-hooks)
- [Async Operations](#async-operations)
- [Performance Optimization](#performance-optimization)
- [Testing Redux State](#testing-redux-state)
- [Debugging Tools](#debugging-tools)
- [Common Patterns](#common-patterns)

## State Management Overview

The KTRDR frontend uses Redux Toolkit as its primary state management solution. This provides:

- Centralized state management
- Predictable state updates
- Middleware support for side effects
- Developer tools integration
- TypeScript support

### State Management Architecture

The application's state management architecture follows these principles:

1. **Redux Store**: Central state store for application-wide data
2. **Context API**: For theme and localized UI state
3. **Component State**: For component-specific, ephemeral state
4. **Custom Hooks**: For encapsulating state logic and sharing across components

```
┌─────────────────────────┐
│      Redux Store        │
│                         │
│  ┌─────────┐ ┌────────┐ │
│  │ UI Slice│ │Data    │ │
│  │         │ │Slice   │ │
│  └─────────┘ └────────┘ │
│                         │
│  ┌─────────┐ ┌────────┐ │
│  │ Settings│ │User    │ │
│  │ Slice   │ │Slice   │ │
│  └─────────┘ └────────┘ │
└─────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│     UI Components       │
└─────────────────────────┘
```

## Redux Toolkit Implementation

### Store Configuration

The Redux store is configured using the Redux Toolkit's `configureStore` function:

```typescript
// src/store/index.ts
import { configureStore } from '@reduxjs/toolkit';
import { setupListeners } from '@reduxjs/toolkit/query';
import { dataApi } from '../api/dataApi';
import dataReducer from './slices/dataSlice';
import uiReducer from './slices/uiSlice';
import settingsReducer from './slices/settingsSlice';

export const store = configureStore({
  reducer: {
    data: dataReducer,
    ui: uiReducer,
    settings: settingsReducer,
    [dataApi.reducerPath]: dataApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(dataApi.middleware),
  devTools: process.env.NODE_ENV !== 'production',
});

// Enable refetchOnFocus and refetchOnReconnect behaviors
setupListeners(store.dispatch);

// Infer the `RootState` and `AppDispatch` types from the store
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
```

### Custom Hooks for Type Safety

Create custom hooks to provide type-safe access to the Redux store:

```typescript
// src/store/hooks.ts
import { TypedUseSelectorHook, useDispatch, useSelector } from 'react-redux';
import type { RootState, AppDispatch } from './index';

// Use throughout your app instead of plain `useDispatch` and `useSelector`
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
```

## State Organization

### Slice Structure

Each slice follows a consistent pattern:

```typescript
// src/store/slices/dataSlice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface DataState {
  currentSymbol: string | null;
  timeframe: string;
  dateRange: {
    start: string | null;
    end: string | null;
  };
  isLoading: boolean;
  error: string | null;
}

const initialState: DataState = {
  currentSymbol: null,
  timeframe: '1d',
  dateRange: {
    start: null,
    end: null,
  },
  isLoading: false,
  error: null,
};

export const dataSlice = createSlice({
  name: 'data',
  initialState,
  reducers: {
    setCurrentSymbol: (state, action: PayloadAction<string>) => {
      state.currentSymbol = action.payload;
    },
    setTimeframe: (state, action: PayloadAction<string>) => {
      state.timeframe = action.payload;
    },
    setDateRange: (state, action: PayloadAction<{ start: string | null; end: string | null }>) => {
      state.dateRange = action.payload;
    },
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.isLoading = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
});

export const { setCurrentSymbol, setTimeframe, setDateRange, setLoading, setError } = dataSlice.actions;

export default dataSlice.reducer;
```

### State Slice Categorization

State is organized into logical slices:

1. **Data Slice**: Manages data related to financial information
   - Current symbol
   - Selected timeframe
   - Date range
   - OHLCV data loading state

2. **UI Slice**: Manages UI-related state
   - Sidebar collapsed state
   - Modal visibility
   - Active panel or tab
   - Tooltip visibility

3. **Settings Slice**: Manages user preferences
   - Theme preference
   - Chart settings
   - Indicator parameters
   - Display options

4. **User Slice**: Manages user-related state
   - Authentication status
   - User profile
   - Permissions

## Custom Hooks

### Data Selection Hooks

Create custom hooks to encapsulate data selection logic:

```typescript
// src/hooks/useSymbolData.ts
import { useAppSelector, useAppDispatch } from '../store/hooks';
import { setCurrentSymbol, setTimeframe, setDateRange } from '../store/slices/dataSlice';
import { useGetOhlcvDataQuery } from '../api/dataApi';

export function useSymbolData() {
  const dispatch = useAppDispatch();
  const { currentSymbol, timeframe, dateRange } = useAppSelector((state) => state.data);
  
  const { data, isLoading, error } = useGetOhlcvDataQuery(
    { symbol: currentSymbol, timeframe, start: dateRange.start, end: dateRange.end },
    { skip: !currentSymbol }
  );
  
  const selectSymbol = (symbol: string) => {
    dispatch(setCurrentSymbol(symbol));
  };
  
  const selectTimeframe = (tf: string) => {
    dispatch(setTimeframe(tf));
  };
  
  const selectDateRange = (start: string | null, end: string | null) => {
    dispatch(setDateRange({ start, end }));
  };
  
  return {
    symbol: currentSymbol,
    timeframe,
    dateRange,
    data,
    isLoading,
    error,
    selectSymbol,
    selectTimeframe,
    selectDateRange,
  };
}
```

### UI State Hooks

Create custom hooks for UI state management:

```typescript
// src/hooks/useUIState.ts
import { useAppSelector, useAppDispatch } from '../store/hooks';
import { 
  setSidebarCollapsed, 
  setActiveModal, 
  setActiveTab 
} from '../store/slices/uiSlice';

export function useUIState() {
  const dispatch = useAppDispatch();
  const { sidebarCollapsed, activeModal, activeTab } = useAppSelector((state) => state.ui);
  
  const toggleSidebar = () => {
    dispatch(setSidebarCollapsed(!sidebarCollapsed));
  };
  
  const openModal = (modalId: string) => {
    dispatch(setActiveModal(modalId));
  };
  
  const closeModal = () => {
    dispatch(setActiveModal(null));
  };
  
  const setTab = (tab: string) => {
    dispatch(setActiveTab(tab));
  };
  
  return {
    sidebarCollapsed,
    activeModal,
    activeTab,
    toggleSidebar,
    openModal,
    closeModal,
    setTab,
  };
}
```

## Async Operations

### Redux Toolkit Query (RTK Query)

The application uses RTK Query for data fetching and caching:

```typescript
// src/api/dataApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { RootState } from '../store';

export interface OHLCVData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SymbolInfo {
  symbol: string;
  name: string;
  exchange: string;

export const dataApi = createApi({
  reducerPath: 'dataApi',
  baseQuery: fetchBaseQuery({ 
    baseUrl: '/api',
    prepareHeaders: (headers, { getState }) => {
      // Add authentication token from Redux state if available
      const token = (getState() as RootState).user?.token;
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  endpoints: (builder) => ({
    getSymbols: builder.query<string[], void>({
      query: () => '/symbols',
    }),
    getSymbolInfo: builder.query<SymbolInfo, string>({
      query: (symbol) => `/symbols/${symbol}`,
    }),
    getOhlcvData: builder.query<OHLCVData[], { 
      symbol: string | null; 
      timeframe: string; 
      start: string | null; 
      end: string | null; 
    }>({
      query: ({ symbol, timeframe, start, end }) => {
        let url = `/ohlcv/${symbol}?timeframe=${timeframe}`;
        if (start) url += `&start=${start}`;
        if (end) url += `&end=${end}`;
        return url;
      },
      // Don't run the query if symbol is null
      skip: (arg) => !arg.symbol,
    }),
  }),
});

export const { 
  useGetSymbolsQuery, 
  useGetSymbolInfoQuery, 
  useGetOhlcvDataQuery 
} = dataApi;
```

### Thunks for Complex Operations

For complex operations that involve multiple state updates, use Redux Thunks:

```typescript
// src/store/thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import { setCurrentSymbol, setTimeframe, setDateRange } from './slices/dataSlice';
import { RootState, AppDispatch } from './index';
import { saveUserPreferences } from '../api/userApi';

export const loadChartPreset = createAsyncThunk<
  void,
  string,
  { state: RootState; dispatch: AppDispatch }
>(
  'chart/loadPreset',
  async (presetId, { getState, dispatch }) => {
    try {
      // 1. Load preset data from API
      const response = await fetch(`/api/presets/${presetId}`);
      const preset = await response.json();
      
      // 2. Update Redux state with preset values
      dispatch(setCurrentSymbol(preset.symbol));
      dispatch(setTimeframe(preset.timeframe));
      dispatch(setDateRange(preset.dateRange));
      
      // 3. Load indicators (could be in another slice)
      // ...
      
      return preset;
    } catch (error) {
      throw new Error('Failed to load chart preset');
    }
  }
);

export const saveUserSettings = createAsyncThunk<
  void,
  void,
  { state: RootState }
>(
  'settings/save',
  async (_, { getState }) => {
    try {
      const state = getState();
      const settings = state.settings;
      
      // Save settings to server
      await saveUserPreferences(settings);
      
      return;
    } catch (error) {
      throw new Error('Failed to save user settings');
    }
  }
);
```

## Performance Optimization

### Memoized Selectors

Use memoized selectors to prevent unnecessary re-renders:

```typescript
// src/store/selectors.ts
import { createSelector } from '@reduxjs/toolkit';
import { RootState } from './index';

// Basic selector
export const selectCurrentSymbol = (state: RootState) => state.data.currentSymbol;
export const selectTimeframe = (state: RootState) => state.data.timeframe;
export const selectOhlcvData = (state: RootState) => state.data.ohlcvData;

// Memoized selector for derived data
export const selectCurrentDayData = createSelector(
  [selectOhlcvData],
  (ohlcvData) => {
    if (!ohlcvData || ohlcvData.length === 0) return null;
    return ohlcvData[ohlcvData.length - 1];
  }
);

// Complex memoized selector
export const selectPriceChange = createSelector(
  [selectOhlcvData],
  (ohlcvData) => {
    if (!ohlcvData || ohlcvData.length < 2) return { value: 0, percentage: 0 };
    
    const latest = ohlcvData[ohlcvData.length - 1];
    const previous = ohlcvData[ohlcvData.length - 2];
    
    const change = latest.close - previous.close;
    const percentage = (change / previous.close) * 100;
    
    return {
      value: change,
      percentage,
    };
  }
);
```

### Using Selectors in Components

```typescript
// Example component using memoized selectors
import React from 'react';
import { useAppSelector } from '../store/hooks';
import { selectCurrentSymbol, selectPriceChange } from '../store/selectors';

export const PriceChangeDisplay: React.FC = () => {
  const symbol = useAppSelector(selectCurrentSymbol);
  const { value, percentage } = useAppSelector(selectPriceChange);
  
  if (!symbol) return null;
  
  const isPositive = value >= 0;
  
  return (
    <div className={`price-change ${isPositive ? 'positive' : 'negative'}`}>
      <span className="symbol">{symbol}</span>
      <span className="change-value">{value.toFixed(2)}</span>
      <span className="change-percentage">({percentage.toFixed(2)}%)</span>
    </div>
  );
};
```

### List Rendering Optimization

Optimize list rendering to prevent unnecessary re-renders:

```typescript
// Using React.memo and useMemo
import React, { useMemo } from 'react';
import { useAppSelector } from '../store/hooks';
import { selectSymbols } from '../store/selectors';

// Memoized list item component
const SymbolItem = React.memo(({ symbol, onSelect }: { 
  symbol: string; 
  onSelect: (symbol: string) => void;
}) => {
  const handleClick = () => {
    onSelect(symbol);
  };
  
  return (
    <li className="symbol-item" onClick={handleClick}>
      {symbol}
    </li>
  );
});

// List component with optimization
export const SymbolList: React.FC<{ 
  onSelectSymbol: (symbol: string) => void; 
}> = ({ onSelectSymbol }) => {
  const symbols = useAppSelector(selectSymbols);
  
  // Memoize the list items
  const symbolItems = useMemo(() => {
    return symbols.map((symbol) => (
      <SymbolItem
        key={symbol}
        symbol={symbol}
        onSelect={onSelectSymbol}
      />
    ));
  }, [symbols, onSelectSymbol]);
  
  return (
    <ul className="symbol-list">
      {symbolItems}
    </ul>
  );
};
```

## Testing Redux State

### Testing Reducers

```typescript
// src/store/slices/dataSlice.test.ts
import reducer, { 
  setCurrentSymbol, 
  setTimeframe, 
  setDateRange,
  initialState 
} from './dataSlice';

describe('data reducer', () => {
  test('should return the initial state', () => {
    expect(reducer(undefined, { type: undefined })).toEqual(initialState);
  });
  
  test('should handle setCurrentSymbol', () => {
    const previousState = { ...initialState };
    expect(reducer(previousState, setCurrentSymbol('AAPL'))).toEqual({
      ...initialState,
      currentSymbol: 'AAPL',
    });
  });
  
  test('should handle setTimeframe', () => {
    const previousState = { ...initialState };
    expect(reducer(previousState, setTimeframe('1h'))).toEqual({
      ...initialState,
      timeframe: '1h',
    });
  });
  
  test('should handle setDateRange', () => {
    const previousState = { ...initialState };
    const dateRange = { start: '2023-01-01', end: '2023-01-31' };
    expect(reducer(previousState, setDateRange(dateRange))).toEqual({
      ...initialState,
      dateRange,
    });
  });
});
```

### Testing Selectors

```typescript
// src/store/selectors.test.ts
import { selectPriceChange } from './selectors';

describe('selectors', () => {
  test('selectPriceChange returns zero for empty data', () => {
    const state = {
      data: {
        ohlcvData: [],
      },
    } as any; // Type assertion for test
    
    expect(selectPriceChange(state)).toEqual({ value: 0, percentage: 0 });
  });
  
  test('selectPriceChange calculates correctly', () => {
    const state = {
      data: {
        ohlcvData: [
          { close: 100 },
          { close: 110 },
        ],
      },
    } as any; // Type assertion for test
    
    const result = selectPriceChange(state);
    expect(result.value).toBe(10);
    expect(result.percentage).toBe(10);
  });
});
```

### Testing Async Actions

```typescript
// src/store/thunks.test.ts
import { configureStore } from '@reduxjs/toolkit';
import dataReducer, { initialState } from './slices/dataSlice';
import { loadChartPreset } from './thunks';

// Mock fetch
global.fetch = vi.fn();

describe('async thunks', () => {
  let store;
  
  beforeEach(() => {
    store = configureStore({
      reducer: {
        data: dataReducer,
      },
    });
    
    // Reset mocks
    vi.resetAllMocks();
  });
  
  test('loadChartPreset updates state correctly', async () => {
    // Mock API response
    (global.fetch as any).mockResolvedValueOnce({
      json: async () => ({
        symbol: 'AAPL',
        timeframe: '1h',
        dateRange: { start: '2023-01-01', end: '2023-01-31' },
      }),
    });
    
    // Dispatch the thunk
    await store.dispatch(loadChartPreset('preset1'));
    
    // Verify state updates
    const state = store.getState();
    expect(state.data.currentSymbol).toBe('AAPL');
    expect(state.data.timeframe).toBe('1h');
    expect(state.data.dateRange).toEqual({ start: '2023-01-01', end: '2023-01-31' });
  });
  
  test('loadChartPreset handles error', async () => {
    // Mock API error
    (global.fetch as any).mockRejectedValueOnce(new Error('API Error'));
    
    // Verify thunk throws error
    await expect(store.dispatch(loadChartPreset('preset1'))).rejects.toThrow();
    
    // Verify state remains unchanged
    const state = store.getState();
    expect(state.data).toEqual(initialState);
  });
});
```

## Debugging Tools

### Redux DevTools

The application is configured to use Redux DevTools for debugging:

```typescript
// In store configuration
export const store = configureStore({
  // ...other configuration
  devTools: process.env.NODE_ENV !== 'production',
});
```

Tips for effective Redux debugging:

1. **State Inspection**: View the current state and how it changes over time
2. **Action Tracing**: Track which actions are dispatched and their payloads
3. **Time Travel**: Move back and forth between state changes
4. **Action Replay**: Replay a series of actions to reproduce issues
5. **Export/Import**: Save and load Redux state for issue reproduction

### Logging Middleware

To enhance debugging, add a logging middleware in development:

```typescript
// src/store/middleware/logger.ts
import { Middleware } from 'redux';

export const loggerMiddleware: Middleware = (store) => (next) => (action) => {
  if (process.env.NODE_ENV !== 'production') {
    console.group(`ACTION: ${action.type}`);
    console.log('Previous State:', store.getState());
    console.log('Action:', action);
    
    const result = next(action);
    
    console.log('Next State:', store.getState());
    console.groupEnd();
    
    return result;
  }
  
  return next(action);
};

// Add to store configuration
const store = configureStore({
  // ...other configuration
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .concat(dataApi.middleware)
      .concat(process.env.NODE_ENV !== 'production' ? loggerMiddleware : []),
});
```

## Common Patterns

### Handling Loading States

A common pattern for managing loading states:

```typescript
// In the slice
interface DataState {
  // ...other state properties
  status: 'idle' | 'loading' | 'succeeded' | 'failed';
  error: string | null;
}

// In a component
import React from 'react';
import { useAppSelector } from '../store/hooks';

export const DataLoadingHandler: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status, error } = useAppSelector((state) => state.data);
  
  if (status === 'loading') {
    return <LoadingSpinner />;
  }
  
  if (status === 'failed') {
    return <ErrorDisplay message={error || 'An error occurred'} />;
  }
  
  if (status === 'succeeded') {
    return <>{children}</>;
  }
  
  return null; // 'idle' state
};
```

### Handling Form State

For simple forms, use local state. For complex forms, consider using Redux:

```typescript
// Redux slice for form state
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface FormState {
  values: {
    [key: string]: any;
  };
  touched: {
    [key: string]: boolean;
  };
  errors: {
    [key: string]: string | null;
  };
  isSubmitting: boolean;
  isValid: boolean;
}

const initialState: FormState = {
  values: {},
  touched: {},
  errors: {},
  isSubmitting: false,
  isValid: false,
};

export const formSlice = createSlice({
  name: 'form',
  initialState,
  reducers: {
    setValue: (state, action: PayloadAction<{ field: string; value: any }>) => {
      const { field, value } = action.payload;
      state.values[field] = value;
      state.touched[field] = true;
    },
    setError: (state, action: PayloadAction<{ field: string; error: string | null }>) => {
      const { field, error } = action.payload;
      state.errors[field] = error;
      state.isValid = Object.values(state.errors).every((err) => err === null);
    },
    setSubmitting: (state, action: PayloadAction<boolean>) => {
      state.isSubmitting = action.payload;
    },
    resetForm: () => initialState,
  },
});
```

### State Updates with Immutability

Always use immutable updates with Redux Toolkit:

```typescript
// Bad - direct mutation (don't do this)
const badReducer = (state, action) => {
  state.items.push(action.payload); // Mutates state directly
  return state;
};

// Good - using Redux Toolkit's immer integration
const goodReducer = (state, action) => {
  state.items.push(action.payload); // Looks like mutation but is safe with Redux Toolkit
};

// Good - using spread operator for immutability
const goodReducer2 = (state, action) => {
  return {
    ...state,
    items: [...state.items, action.payload],
  };
};
```

### Derived State and Caching

Use memoized selectors for derived data:

```typescript
// Efficient selector pattern
import { createSelector } from '@reduxjs/toolkit';
import { RootState } from './index';

// Step 1: Create input selectors
const selectItems = (state: RootState) => state.data.items;
const selectFilter = (state: RootState) => state.ui.filter;

// Step 2: Create memoized selector for derived data
export const selectFilteredItems = createSelector(
  [selectItems, selectFilter],
  (items, filter) => {
    // This calculation only runs when inputs change
    if (!filter) return items;
    
    return items.filter(item => 
      item.name.toLowerCase().includes(filter.toLowerCase())
    );
  }
);
```

### Normalized State Shape

For complex data, normalize the state to improve performance and maintainability:

```typescript
// Before normalization
const unnormalizedState = {
  items: [
    { id: 1, name: 'Item 1', categoryId: 1 },
    { id: 2, name: 'Item 2', categoryId: 2 },
  ],
  categories: [
    { id: 1, name: 'Category 1' },
    { id: 2, name: 'Category 2' },
  ],
};

// After normalization
const normalizedState = {
  items: {
    byId: {
      1: { id: 1, name: 'Item 1', categoryId: 1 },
      2: { id: 2, name: 'Item 2', categoryId: 2 },
    },
    allIds: [1, 2],
  },
  categories: {
    byId: {
      1: { id: 1, name: 'Category 1' },
      2: { id: 2, name: 'Category 2' },
    },
    allIds: [1, 2],
  },
};
```

Redux Toolkit provides utilities for normalizing state:

```typescript
// Using createEntityAdapter
import { createEntityAdapter, createSlice } from '@reduxjs/toolkit';

// Create the adapter
const itemsAdapter = createEntityAdapter<Item>({
  // Assume item has an id field
  selectId: (item) => item.id,
  // Sort items by name
  sortComparer: (a, b) => a.name.localeCompare(b.name),
});

// Create the initial state
const initialState = itemsAdapter.getInitialState({
  // Additional state properties
  loading: false,
  error: null,
});

// Create the slice
const itemsSlice = createSlice({
  name: 'items',
  initialState,
  reducers: {
    // Add an item
    addItem: itemsAdapter.addOne,
    // Add multiple items
    addItems: itemsAdapter.addMany,
    // Update an item
    updateItem: itemsAdapter.updateOne,
    // Remove an item
    removeItem: itemsAdapter.removeOne,
  },
});
```