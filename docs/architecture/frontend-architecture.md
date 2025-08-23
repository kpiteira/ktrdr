# KTRDR Frontend Architecture Document

## Template and Framework Selection

### Existing Codebase Foundation

This is a **custom-built production React application** specifically designed for quantitative trading research and visualization. The frontend architecture was developed from scratch using modern React patterns and is **not based on any starter template**.

**Key Architectural Foundations:**
- React 19.0.0 with TypeScript for type-safe development
- Vite build system for fast development and optimized production builds
- Container/Presentation pattern for clean component separation
- Redux Toolkit for professional-grade state management
- TradingView Lightweight Charts for industry-standard financial visualizations
- Docker-based development environment for consistency

**Design Philosophy:**
- **Research-first**: Optimized for exploring market data and testing trading strategies
- **Performance-critical**: Real-time data visualization with thousands of data points
- **Professional-grade**: Production-ready patterns suitable for financial applications
- **AI-friendly**: Architecture designed for AI agent development and maintenance

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|---------|
| 2025-01-22 | 1.0 | Initial frontend architecture documentation | Winston (Architect) |

## Frontend Tech Stack

The frontend technology stack is carefully selected for financial data visualization and trading research applications. All choices align with the main architecture document and prioritize performance, maintainability, and developer experience.

### Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| **Framework** | React | 19.0.0 | Core UI framework | Latest stable with excellent performance, mature ecosystem, team expertise |
| **Language** | TypeScript | 5.x | Type-safe development | Prevents runtime errors, excellent IDE support, essential for financial applications |
| **Build Tool** | Vite | Latest | Development server and bundling | Fast HMR, optimized builds, modern ESM support, better than webpack |
| **State Management** | Redux Toolkit | 2.7.0 | Application state management | Professional-grade state management, excellent DevTools, predictable updates |
| **Routing** | React Router | 6.16.0 | Client-side routing | Industry standard, excellent v6 API, supports nested routes |
| **Styling** | CSS + CSS Modules | Native | Component styling | Simple, performant, no runtime overhead, easy to debug |
| **Charts** | TradingView Lightweight Charts | 5.0.7 | Financial data visualization | Industry standard for trading applications, high performance, professional features |
| **HTTP Client** | Axios | 1.9.0 | API communication | Robust HTTP client, excellent error handling, request/response interceptors |
| **Testing** | Vitest + React Testing Library | Latest | Unit and integration testing | Fast test runner, React-optimized testing utilities, excellent TypeScript support |
| **Dev Tools** | ESLint + Prettier | Latest | Code quality and formatting | Consistent code style, catch errors early, team collaboration |
| **Development** | Docker | Latest | Containerized development | Consistent environments, easy setup, production parity |

## Project Structure

The project follows a **vertical slice architecture** with clear separation between containers (smart components) and presentation (dumb components). This structure is optimized for AI agent development and maintenance.

```
frontend/
├── public/                           # Static assets
│   ├── index.html                    # HTML template
│   └── favicon.ico                   # Application icon
├── src/
│   ├── components/                   # All React components
│   │   ├── containers/               # Smart components (state + logic)
│   │   │   ├── AppContainer.tsx      # Main app container
│   │   │   ├── BasicChartContainer.tsx
│   │   │   ├── RSIChartContainer.tsx
│   │   │   └── IndicatorSidebarContainer.tsx
│   │   ├── presentation/             # Dumb components (UI only)
│   │   │   ├── charts/               # Chart components
│   │   │   │   ├── BasicChart.tsx
│   │   │   │   ├── RSIChart.tsx
│   │   │   │   └── fuzzy/            # Fuzzy visualization components
│   │   │   │       ├── FuzzyOverlay.tsx
│   │   │   │       └── FuzzyLegend.tsx
│   │   │   ├── sidebar/              # Sidebar components
│   │   │   │   ├── IndicatorSidebar.tsx
│   │   │   │   ├── InstrumentSelector.tsx
│   │   │   │   ├── ActiveIndicatorsList.tsx
│   │   │   │   ├── IndicatorItem.tsx
│   │   │   │   ├── AddIndicatorButton.tsx
│   │   │   │   └── ParameterControls.tsx
│   │   │   └── layout/               # Layout components
│   │   │       ├── Header.tsx
│   │   │       ├── Layout.tsx
│   │   │       ├── LeftSidebar.tsx
│   │   │       └── CollapsibleSidebar.tsx
│   │   └── common/                   # Shared components
│   │       ├── LoadingSpinner.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── Modal.tsx
│   ├── hooks/                        # Custom React hooks
│   │   ├── useIndicatorManager.ts    # Core indicator CRUD operations
│   │   ├── useChartSynchronizer.ts   # Chart sync logic
│   │   ├── useApiClient.ts          # API client with error handling
│   │   ├── useLocalState.ts         # Local UI state management
│   │   ├── useInstrumentData.ts     # Symbol/timeframe data
│   │   ├── useFuzzyData.ts         # Fuzzy set data management
│   │   └── useSidebarCollapse.ts    # Sidebar state management
│   ├── store/                        # Redux store configuration
│   │   ├── index.ts                 # Store configuration
│   │   ├── rootReducer.ts           # Root reducer combining slices
│   │   ├── slices/                  # Redux Toolkit slices
│   │   │   ├── dataSlice.ts         # Market data state
│   │   │   ├── indicatorSlice.ts    # Technical indicators state
│   │   │   ├── uiSlice.ts          # UI state (sidebar, modals)
│   │   │   └── chartSlice.ts       # Chart configuration state
│   │   └── types.ts                # Redux state type definitions
│   ├── services/                     # API services
│   │   ├── api/                     # API client configuration
│   │   │   ├── client.ts            # Axios client setup
│   │   │   ├── types.ts            # API request/response types
│   │   │   └── endpoints.ts        # API endpoint definitions
│   │   ├── dataService.ts          # Market data API calls
│   │   ├── indicatorService.ts     # Technical indicators API
│   │   ├── fuzzyService.ts        # Fuzzy logic API calls
│   │   └── strategyService.ts     # Strategy management API
│   ├── utils/                       # Utility functions
│   │   ├── constants.ts            # Application constants
│   │   ├── dataTransform.ts        # Data transformation utilities
│   │   ├── colorUtils.ts           # Color management for charts
│   │   ├── timeframe.ts           # Timeframe utilities
│   │   └── validation.ts          # Input validation helpers
│   ├── types/                       # TypeScript type definitions
│   │   ├── api.ts                  # API-related types
│   │   ├── chart.ts               # Chart data types
│   │   ├── indicator.ts           # Indicator configuration types
│   │   └── strategy.ts            # Strategy types
│   ├── styles/                      # Global styles
│   │   ├── globals.css             # Global CSS variables and resets
│   │   ├── components.css          # Component-specific styles
│   │   └── themes.css              # Theme definitions
│   ├── views/                       # Page-level components
│   │   ├── ResearchView.tsx        # Main research interface
│   │   ├── TrainView.tsx          # Model training interface (placeholder)
│   │   └── RunView.tsx            # Strategy execution interface (placeholder)
│   ├── App.tsx                      # Main app component
│   ├── main.tsx                     # React 18 entry point
│   └── vite-env.d.ts               # Vite type definitions
├── tests/                           # Test files
│   ├── setup.ts                    # Test configuration
│   ├── utils/                      # Test utilities
│   └── __tests__/                  # Component tests
├── package.json                     # Dependencies and scripts
├── tsconfig.json                   # TypeScript configuration
├── vite.config.ts                  # Vite configuration
├── vitest.config.ts                # Vitest test configuration
├── eslint.config.js                # ESLint configuration
└── README.md                       # Frontend documentation
```

## Component Standards

### Component Template

All React components should follow this standardized template with TypeScript, proper imports, and clear interfaces:

```typescript
import React from 'react';
import { ComponentProps } from '../../types/component';
import './ComponentName.css';

// Props interface with clear documentation
interface ComponentNameProps {
  /** Primary data for the component */
  data: ComponentProps[];
  /** Optional callback for user interactions */
  onAction?: (id: string) => void;
  /** Optional CSS class name for styling */
  className?: string;
  /** Whether the component is in loading state */
  isLoading?: boolean;
}

/**
 * ComponentName - Brief description of what this component does
 * 
 * @param props - Component props
 * @returns JSX element
 */
export const ComponentName: React.FC<ComponentNameProps> = ({
  data,
  onAction,
  className = '',
  isLoading = false,
}) => {
  // Local state if needed
  const [localState, setLocalState] = React.useState<string>('');

  // Event handlers
  const handleClick = React.useCallback((id: string) => {
    onAction?.(id);
  }, [onAction]);

  // Early returns for edge cases
  if (isLoading) {
    return <div className="loading">Loading...</div>;
  }

  if (!data.length) {
    return <div className="empty">No data available</div>;
  }

  return (
    <div className={`component-name ${className}`}>
      {data.map((item) => (
        <div 
          key={item.id}
          className="component-name__item"
          onClick={() => handleClick(item.id)}
        >
          {item.name}
        </div>
      ))}
    </div>
  );
};

export default ComponentName;
```

### Naming Conventions

**Files and Components:**
- **Components**: PascalCase for both files and component names (`BasicChart.tsx`, `IndicatorSidebar.tsx`)
- **Hooks**: camelCase starting with "use" (`useIndicatorManager.ts`, `useChartSync.ts`)
- **Services**: camelCase with "Service" suffix (`dataService.ts`, `apiService.ts`)
- **Types**: camelCase for interfaces, PascalCase for types (`ComponentProps`, `ApiResponse`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`, `DEFAULT_TIMEFRAME`)

**CSS Classes:**
- **BEM methodology**: `block__element--modifier`
- **Component prefix**: Match component name (`basic-chart__container`, `sidebar__item--active`)
- **Utility classes**: `u-margin-top`, `u-text-center`

**State and Variables:**
- **State variables**: Descriptive camelCase (`indicatorList`, `isChartLoading`)
- **Event handlers**: Start with "handle" (`handleSymbolChange`, `handleIndicatorAdd`)
- **Boolean props/state**: Start with "is", "has", "can", or "should" (`isLoading`, `hasError`, `canEdit`)

## State Management

### Store Structure

The Redux store is organized into logical slices that mirror the application's feature domains:

```
src/store/
├── index.ts                  # Store configuration with middleware
├── rootReducer.ts           # Combines all slice reducers
├── types.ts                 # Root state and common types
└── slices/
    ├── dataSlice.ts         # Market data (OHLCV, symbols, timeframes)
    ├── indicatorSlice.ts    # Technical indicators state
    ├── chartSlice.ts        # Chart configuration and synchronization
    ├── uiSlice.ts          # UI state (sidebar collapse, modals, loading)
    └── strategySlice.ts    # Strategy configuration (future)
```

### State Management Template

Here's the standard pattern for creating Redux Toolkit slices with TypeScript:

```typescript
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { RootState } from '../types';

// State interface
interface IndicatorState {
  indicators: Indicator[];
  activeIndicators: ActiveIndicator[];
  loading: boolean;
  error: string | null;
  selectedIndicator: string | null;
}

// Initial state
const initialState: IndicatorState = {
  indicators: [],
  activeIndicators: [],
  loading: false,
  error: null,
  selectedIndicator: null,
};

// Async thunks for API calls
export const fetchIndicators = createAsyncThunk(
  'indicator/fetchIndicators',
  async (_, { rejectWithValue }) => {
    try {
      const response = await indicatorService.getAvailable();
      return response.data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

export const addIndicator = createAsyncThunk(
  'indicator/addIndicator',
  async (config: IndicatorConfig, { rejectWithValue }) => {
    try {
      const response = await indicatorService.calculate(config);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.message);
    }
  }
);

// Slice definition
const indicatorSlice = createSlice({
  name: 'indicator',
  initialState,
  reducers: {
    // Synchronous actions
    selectIndicator: (state, action: PayloadAction<string>) => {
      state.selectedIndicator = action.payload;
    },
    clearError: (state) => {
      state.error = null;
    },
    removeIndicator: (state, action: PayloadAction<string>) => {
      state.activeIndicators = state.activeIndicators.filter(
        (indicator) => indicator.id !== action.payload
      );
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch indicators
      .addCase(fetchIndicators.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchIndicators.fulfilled, (state, action) => {
        state.loading = false;
        state.indicators = action.payload;
      })
      .addCase(fetchIndicators.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Add indicator
      .addCase(addIndicator.fulfilled, (state, action) => {
        state.activeIndicators.push(action.payload);
      });
  },
});

// Export actions and reducer
export const { selectIndicator, clearError, removeIndicator } = indicatorSlice.actions;

// Selectors
export const selectIndicators = (state: RootState) => state.indicator.indicators;
export const selectActiveIndicators = (state: RootState) => state.indicator.activeIndicators;
export const selectIndicatorLoading = (state: RootState) => state.indicator.loading;

export default indicatorSlice.reducer;
```

## API Integration

### Service Template

All API services follow this standardized pattern with proper TypeScript types, error handling, and async patterns:

```typescript
import { apiClient } from './api/client';
import { ApiResponse, LoadDataRequest, LoadDataResponse } from '../types/api';

/**
 * Data Service - Handles market data operations
 * Provides methods for loading OHLCV data, symbols, and timeframes
 */
export class DataService {
  /**
   * Load market data for a symbol and timeframe
   */
  static async loadData(request: LoadDataRequest): Promise<ApiResponse<LoadDataResponse>> {
    try {
      const response = await apiClient.post('/data/load', request);
      
      if (!response.data.success) {
        throw new Error(response.data.error?.message || 'Failed to load data');
      }
      
      return response.data;
    } catch (error) {
      console.error('DataService.loadData error:', error);
      throw error;
    }
  }

  /**
   * Get list of available symbols
   */
  static async getSymbols(): Promise<ApiResponse<string[]>> {
    try {
      const response = await apiClient.get('/symbols');
      return response.data;
    } catch (error) {
      console.error('DataService.getSymbols error:', error);
      throw error;
    }
  }

  /**
   * Get list of available timeframes
   */
  static async getTimeframes(): Promise<ApiResponse<string[]>> {
    try {
      const response = await apiClient.get('/timeframes');
      return response.data;
    } catch (error) {
      console.error('DataService.getTimeframes error:', error);
      throw error;
    }
  }

  /**
   * Transform backend OHLCV data to TradingView format
   */
  static transformToTradingView(data: OHLCVPoint[]): CandlestickData[] {
    return data.map((point) => ({
      time: new Date(point.timestamp).getTime() / 1000 as UTCTimestamp,
      open: point.open,
      high: point.high,
      low: point.low,
      close: point.close,
    }));
  }
}

export const dataService = DataService;
```

### API Client Configuration

The HTTP client is configured with authentication interceptors, error handling, and base URL management:

```typescript
import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios';

// Create axios instance with base configuration
const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add request timestamp for debugging
    config.metadata = { startTime: Date.now() };
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    // Log response time for performance monitoring
    const duration = Date.now() - response.config.metadata?.startTime;
    console.debug(`API ${response.config.method?.toUpperCase()} ${response.config.url} - ${duration}ms`);
    
    return response;
  },
  (error: AxiosError) => {
    // Handle common error scenarios
    if (error.response?.status === 401) {
      // Token expired or invalid
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    
    if (error.response?.status === 403) {
      console.error('Access forbidden:', error.response.data);
    }
    
    if (error.code === 'NETWORK_ERROR') {
      console.error('Network error - backend may be unavailable');
    }
    
    // Enhanced error object for consistent handling
    const enhancedError = {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
      code: error.code,
    };
    
    return Promise.reject(enhancedError);
  }
);

export { apiClient };
```

## Routing

### Route Configuration

The application uses React Router v6 with nested routes, lazy loading, and authentication guards:

```typescript
import React, { Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Outlet } from 'react-router-dom';
import { Layout } from '../components/presentation/layout/Layout';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { ErrorBoundary } from '../components/common/ErrorBoundary';

// Lazy-loaded components for code splitting
const ResearchView = React.lazy(() => import('../views/ResearchView'));
const TrainView = React.lazy(() => import('../views/TrainView'));
const RunView = React.lazy(() => import('../views/RunView'));
const SettingsView = React.lazy(() => import('../views/SettingsView'));

// Layout wrapper with error boundary
const AppLayout: React.FC = () => (
  <ErrorBoundary>
    <Layout>
      <Suspense fallback={<LoadingSpinner />}>
        <Outlet />
      </Suspense>
    </Layout>
  </ErrorBoundary>
);

// Route definitions
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: <ResearchView />,
      },
      {
        path: 'research',
        element: <ResearchView />,
      },
      {
        path: 'train',
        element: <TrainView />,
        // loader: async () => {
        //   // Pre-load data for training view
        //   return await trainingService.getAvailableStrategies();
        // },
      },
      {
        path: 'run',
        element: <RunView />,
        // Add authentication guard when needed
        // loader: requireAuth,
      },
      {
        path: 'settings',
        element: <SettingsView />,
      },
    ],
  },
  {
    path: '*',
    element: <div>Page not found</div>,
  },
]);

// Router component
export const AppRouter: React.FC = () => (
  <RouterProvider router={router} />
);
```

## Styling Guidelines

### Styling Approach

The application uses **CSS with CSS Custom Properties (CSS Variables)** for theming and **CSS Modules pattern** for component-specific styles. This approach provides excellent performance with no runtime overhead while maintaining excellent maintainability.

**Key Principles:**
- **CSS Variables** for global theme values (colors, spacing, typography)
- **Component-specific CSS files** co-located with components
- **BEM methodology** for consistent class naming
- **Mobile-first responsive design** with breakpoint variables
- **Dark mode support** through CSS variable switching

### Global Theme Variables

Global theme system using CSS custom properties for consistent styling across the application:

```css
/* styles/globals.css */
:root {
  /* Color System */
  --color-primary: #2196f3;
  --color-primary-dark: #1976d2;
  --color-primary-light: #64b5f6;
  
  --color-secondary: #ff5722;
  --color-secondary-dark: #e64a19;
  --color-secondary-light: #ff8a65;
  
  --color-success: #4caf50;
  --color-warning: #ff9800;
  --color-error: #f44336;
  --color-info: #2196f3;
  
  /* Neutral Colors */
  --color-background: #ffffff;
  --color-surface: #f5f5f5;
  --color-surface-variant: #e0e0e0;
  
  --color-text-primary: #212121;
  --color-text-secondary: #757575;
  --color-text-disabled: #bdbdbd;
  
  --color-border: #e0e0e0;
  --color-divider: #e0e0e0;
  
  /* Trading-specific Colors */
  --color-bullish: #4caf50;
  --color-bearish: #f44336;
  --color-neutral: #9e9e9e;
  
  /* Chart Colors */
  --color-candlestick-up: #4caf50;
  --color-candlestick-down: #f44336;
  --color-volume: rgba(33, 150, 243, 0.3);
  
  /* Typography */
  --font-family-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-family-mono: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
  
  --font-size-xs: 0.75rem;    /* 12px */
  --font-size-sm: 0.875rem;   /* 14px */
  --font-size-base: 1rem;     /* 16px */
  --font-size-lg: 1.125rem;   /* 18px */
  --font-size-xl: 1.25rem;    /* 20px */
  --font-size-2xl: 1.5rem;    /* 24px */
  
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.75;
  
  /* Spacing System */
  --spacing-xs: 0.25rem;   /* 4px */
  --spacing-sm: 0.5rem;    /* 8px */
  --spacing-md: 1rem;      /* 16px */
  --spacing-lg: 1.5rem;    /* 24px */
  --spacing-xl: 2rem;      /* 32px */
  --spacing-2xl: 3rem;     /* 48px */
  --spacing-3xl: 4rem;     /* 64px */
  
  /* Border Radius */
  --border-radius-sm: 0.25rem;    /* 4px */
  --border-radius-md: 0.375rem;   /* 6px */
  --border-radius-lg: 0.5rem;     /* 8px */
  --border-radius-xl: 0.75rem;    /* 12px */
  --border-radius-full: 9999px;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  
  /* Z-Index Scale */
  --z-dropdown: 1000;
  --z-sticky: 1020;
  --z-fixed: 1030;
  --z-modal: 1040;
  --z-popover: 1050;
  --z-tooltip: 1060;
  
  /* Breakpoints */
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;
  
  /* Animation */
  --transition-fast: 150ms ease-in-out;
  --transition-normal: 300ms ease-in-out;
  --transition-slow: 500ms ease-in-out;
}

/* Dark Mode Theme */
[data-theme="dark"] {
  --color-background: #121212;
  --color-surface: #1e1e1e;
  --color-surface-variant: #2d2d2d;
  
  --color-text-primary: #ffffff;
  --color-text-secondary: #b3b3b3;
  --color-text-disabled: #666666;
  
  --color-border: #2d2d2d;
  --color-divider: #2d2d2d;
  
  /* Adjust chart colors for dark mode */
  --color-volume: rgba(33, 150, 243, 0.2);
}

/* Global Resets */
*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  font-family: var(--font-family-primary);
  font-size: var(--font-size-base);
  line-height: var(--line-height-normal);
}

body {
  margin: 0;
  padding: 0;
  background-color: var(--color-background);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-normal);
}

/* Utility Classes */
.u-margin-0 { margin: 0; }
.u-margin-sm { margin: var(--spacing-sm); }
.u-margin-md { margin: var(--spacing-md); }

.u-padding-0 { padding: 0; }
.u-padding-sm { padding: var(--spacing-sm); }
.u-padding-md { padding: var(--spacing-md); }

.u-text-center { text-align: center; }
.u-text-left { text-align: left; }
.u-text-right { text-align: right; }

.u-font-mono { font-family: var(--font-family-mono); }
.u-font-bold { font-weight: var(--font-weight-bold); }

.u-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

## Testing Requirements

### Component Test Template

All components should have corresponding test files using Vitest and React Testing Library:

```typescript
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { IndicatorSidebar } from '../IndicatorSidebar';
import { rootReducer } from '../../../store/rootReducer';

// Mock dependencies
vi.mock('../../../services/indicatorService', () => ({
  indicatorService: {
    getAvailable: vi.fn(),
    calculate: vi.fn(),
  },
}));

// Test utilities
const createTestStore = (initialState = {}) => {
  return configureStore({
    reducer: rootReducer,
    preloadedState: initialState,
  });
};

const renderWithProviders = (
  ui: React.ReactElement,
  {
    preloadedState = {},
    store = createTestStore(preloadedState),
    ...renderOptions
  } = {}
) => {
  const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <Provider store={store}>{children}</Provider>
  );

  return {
    store,
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
  };
};

// Test data
const mockIndicators = [
  { name: 'SMA', displayName: 'Simple Moving Average', parameters: { period: 20 } },
  { name: 'RSI', displayName: 'Relative Strength Index', parameters: { period: 14 } },
];

const defaultProps = {
  indicators: mockIndicators,
  onAddIndicator: vi.fn(),
  onRemoveIndicator: vi.fn(),
  isLoading: false,
};

describe('IndicatorSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render indicator list correctly', () => {
    renderWithProviders(<IndicatorSidebar {...defaultProps} />);
    
    expect(screen.getByText('Simple Moving Average')).toBeInTheDocument();
    expect(screen.getByText('Relative Strength Index')).toBeInTheDocument();
  });

  it('should handle add indicator button click', async () => {
    const onAddIndicator = vi.fn();
    
    renderWithProviders(
      <IndicatorSidebar {...defaultProps} onAddIndicator={onAddIndicator} />
    );
    
    // Click add button for SMA
    const addButton = screen.getByTestId('add-indicator-SMA');
    fireEvent.click(addButton);
    
    await waitFor(() => {
      expect(onAddIndicator).toHaveBeenCalledWith({
        name: 'SMA',
        parameters: { period: 20 },
      });
    });
  });

  it('should show loading state', () => {
    renderWithProviders(
      <IndicatorSidebar {...defaultProps} isLoading={true} />
    );
    
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('should handle empty indicator list', () => {
    renderWithProviders(
      <IndicatorSidebar {...defaultProps} indicators={[]} />
    );
    
    expect(screen.getByText('No indicators available')).toBeInTheDocument();
  });

  it('should be accessible', () => {
    renderWithProviders(<IndicatorSidebar {...defaultProps} />);
    
    // Check for proper ARIA attributes
    expect(screen.getByRole('region')).toHaveAttribute('aria-label', 'Indicator Controls');
    expect(screen.getAllByRole('button')).toHaveLength(2); // Add buttons for each indicator
  });
});
```

### Testing Best Practices

1. **Unit Tests**: Test individual components in isolation with mocked dependencies
2. **Integration Tests**: Test component interactions and data flow between components
3. **E2E Tests**: Test critical user flows using Cypress or Playwright for full system validation
4. **Coverage Goals**: Maintain 80% code coverage minimum with focus on critical business logic
5. **Test Structure**: Follow Arrange-Act-Assert pattern for clear and maintainable tests
6. **Mock External Dependencies**: Mock API calls, routing, state management, and third-party libraries

## Environment Configuration

### Required Environment Variables

The application requires the following environment variables with specific naming conventions for Vite:

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=KTRDR Research Platform
VITE_APP_VERSION=1.0.7.2
VITE_ENVIRONMENT=development

# Authentication (when implemented)
VITE_AUTH_ENABLED=false
VITE_AUTH_PROVIDER=jwt

# Feature Flags
VITE_FEATURE_FUZZY_VISUALIZATION=true
VITE_FEATURE_NEURAL_TRAINING=true
VITE_FEATURE_STRATEGY_BACKTESTING=true

# Chart Configuration
VITE_CHART_DEFAULT_TIMEFRAME=1h
VITE_CHART_MAX_CANDLES=1000
VITE_CHART_ENABLE_CROSSHAIR_SYNC=true

# Development Tools
VITE_ENABLE_REDUX_DEVTOOLS=true
VITE_ENABLE_API_LOGGING=true
VITE_MOCK_API=false

# .env.production
VITE_API_BASE_URL=https://api.ktrdr.com/api/v1
VITE_APP_NAME=KTRDR Research Platform
VITE_APP_VERSION=1.0.7.2
VITE_ENVIRONMENT=production

VITE_AUTH_ENABLED=true
VITE_AUTH_PROVIDER=jwt

VITE_FEATURE_FUZZY_VISUALIZATION=true
VITE_FEATURE_NEURAL_TRAINING=true
VITE_FEATURE_STRATEGY_BACKTESTING=true

VITE_CHART_DEFAULT_TIMEFRAME=1h
VITE_CHART_MAX_CANDLES=1000
VITE_CHART_ENABLE_CROSSHAIR_SYNC=true

VITE_ENABLE_REDUX_DEVTOOLS=false
VITE_ENABLE_API_LOGGING=false
VITE_MOCK_API=false
```

**Environment Variable Access:**
```typescript
// utils/env.ts
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  appName: import.meta.env.VITE_APP_NAME,
  environment: import.meta.env.VITE_ENVIRONMENT,
  features: {
    fuzzyVisualization: import.meta.env.VITE_FEATURE_FUZZY_VISUALIZATION === 'true',
    neuralTraining: import.meta.env.VITE_FEATURE_NEURAL_TRAINING === 'true',
  },
  chart: {
    defaultTimeframe: import.meta.env.VITE_CHART_DEFAULT_TIMEFRAME || '1h',
    maxCandles: parseInt(import.meta.env.VITE_CHART_MAX_CANDLES || '1000'),
  },
  dev: {
    enableReduxDevTools: import.meta.env.VITE_ENABLE_REDUX_DEVTOOLS === 'true',
    enableApiLogging: import.meta.env.VITE_ENABLE_API_LOGGING === 'true',
  },
} as const;
```

## Frontend Developer Standards

### Critical Coding Rules

These rules prevent common AI mistakes and ensure consistent, maintainable code:

**React-Specific Rules:**
- **Always use React.FC type for functional components** with proper TypeScript interfaces
- **Never use any type** - always provide specific TypeScript interfaces
- **Use useCallback for event handlers** passed to child components to prevent unnecessary re-renders
- **Use useMemo for expensive calculations** but not for simple object creation
- **Always provide dependency arrays** for useEffect, useMemo, and useCallback hooks
- **Use proper error boundaries** - wrap components that might fail in ErrorBoundary
- **Never mutate Redux state directly** - always use Redux Toolkit's createSlice for immutable updates

**Performance Rules:**
- **Chart components must use fixed dimensions** - never use responsive sizing that can cause infinite resize loops
- **Debounce user input** for API calls with minimum 300ms delay
- **Use React.lazy for code splitting** - lazy load views and large components
- **Implement proper cleanup** in useEffect hooks to prevent memory leaks
- **Cache chart instances** in refs and properly dispose on unmount

**TradingView Charts Rules:**
- **Always use TradingView v5 API** - `chart.addSeries(SeriesType, options)` not v4 methods
- **Set autoResize={false}** and use fixed dimensions to prevent resize loops
- **Implement proper chart cleanup** in component unmount
- **Use UTCTimestamp type** for all time values
- **Handle chart errors with try/catch** blocks

**State Management Rules:**
- **Container components handle state, presentation components receive props**
- **Use custom hooks for reusable logic** - don't duplicate state management code
- **Keep local state minimal** - prefer props and Redux store over local state
- **Async actions must use createAsyncThunk** with proper error handling

### Quick Reference

**Development Commands:**
```bash
# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run test:coverage

# Lint and format
npm run lint
npm run lint:fix
npm run format

# Type checking
npm run typecheck
```

**Key Import Patterns:**
```typescript
// React and hooks
import React, { useState, useEffect, useCallback, useMemo } from 'react';

// Redux
import { useSelector, useDispatch } from 'react-redux';
import { selectIndicators, addIndicator } from '../store/slices/indicatorSlice';

// Routing
import { useNavigate, useParams, Link } from 'react-router-dom';

// TradingView Charts
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';

// Custom hooks
import { useIndicatorManager } from '../hooks/useIndicatorManager';
```

**Component Creation Checklist:**
- [ ] TypeScript interface for props
- [ ] React.FC type annotation
- [ ] PropTypes or default props where appropriate
- [ ] CSS file co-located with component
- [ ] Test file in same directory
- [ ] Proper error handling
- [ ] Accessibility attributes (ARIA)
- [ ] Responsive design considerations

**File Naming Examples:**
- Components: `BasicChart.tsx`, `IndicatorSidebar.tsx`
- Hooks: `useIndicatorManager.ts`, `useChartSync.ts`
- Services: `dataService.ts`, `indicatorService.ts`
- Types: `api.ts`, `chart.ts`, `indicator.ts`
- Tests: `BasicChart.test.tsx`, `useIndicatorManager.test.ts`

This frontend architecture document provides comprehensive guidance for developing and maintaining the KTRDR React application. It emphasizes performance, maintainability, and consistency while providing clear patterns for AI agents and human developers to follow.

---

## Integration with Backend Architecture

This frontend architecture is designed to work seamlessly with the backend architecture documented in `docs/backend-architecture.md`. Key integration points include:

- **API Alignment**: Service layer matches backend REST API endpoints
- **Data Models**: TypeScript types correspond to Pydantic models in backend
- **Error Handling**: Frontend error handling aligns with backend error response format
- **Authentication**: Frontend auth patterns support backend JWT implementation
- **Real-time Features**: WebSocket support for backend streaming capabilities

The combined architecture provides a robust, scalable platform for quantitative trading research and development.