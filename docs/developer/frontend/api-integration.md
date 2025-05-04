# API Integration for Frontend

This document provides comprehensive guidance on integrating with the KTRDR backend API from the frontend application.

## Table of Contents

- [Overview](#overview)
- [API Client Setup](#api-client-setup)
- [Request and Response Handling](#request-and-response-handling)
- [Data Types](#data-types)
- [API Hooks](#api-hooks)
- [Error Handling](#error-handling)
- [Caching Strategy](#caching-strategy)
- [Authentication](#authentication)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

The KTRDR frontend communicates with the backend through a RESTful API. We use Axios as the HTTP client and Redux Toolkit Query (RTK Query) for managing API state, caching, and automatic re-fetching.

## API Client Setup

The API client is configured in `src/api/client.ts`:

```typescript
// src/api/client.ts
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { getAuthToken } from '../utils/auth';

// Base API configuration
const apiConfig: AxiosRequestConfig = {
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
};

// Create API instance
const apiClient: AxiosInstance = axios.create(apiConfig);

// Request interceptor for authentication
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    // Handle specific error codes
    if (error.response) {
      switch (error.response.status) {
        case 401:
          // Handle unauthorized (e.g., redirect to login)
          break;
        case 403:
          // Handle forbidden
          break;
        case 404:
          // Handle not found
          break;
        case 500:
          // Handle server error
          break;
      }
    }
    
    // Transform error for consistent format
    const transformedError = {
      status: error.response?.status || 0,
      message: error.response?.data?.message || error.message,
      data: error.response?.data || null,
    };
    
    return Promise.reject(transformedError);
  }
);

export default apiClient;
```

## Request and Response Handling

### Making Direct API Requests

For one-off API calls or those not requiring caching, use the API client directly:

```typescript
import apiClient from '../api/client';

// Example GET request
const fetchData = async (symbol: string) => {
  try {
    const response = await apiClient.get(`/data/${symbol}`);
    return response.data;
  } catch (error) {
    console.error('Error fetching data:', error);
    throw error;
  }
};

// Example POST request
const createEntity = async (data: any) => {
  try {
    const response = await apiClient.post('/entities', data);
    return response.data;
  } catch (error) {
    console.error('Error creating entity:', error);
    throw error;
  }
};
```

### RTK Query Setup

For most API calls, use RTK Query for automatic caching and request management:

```typescript
// src/api/dataApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import type { Symbol, OHLCVData, TimeframeOption } from '../types/data';

export const dataApi = createApi({
  reducerPath: 'dataApi',
  baseQuery: fetchBaseQuery({ 
    baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
    prepareHeaders: (headers) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['Symbol', 'OHLCV'],
  endpoints: (builder) => ({
    getSymbols: builder.query<Symbol[], void>({
      query: () => 'symbols',
      providesTags: ['Symbol'],
    }),
    getTimeframes: builder.query<TimeframeOption[], void>({
      query: () => 'timeframes',
    }),
    getSymbolData: builder.query<OHLCVData, { symbol: string; timeframe: string; start?: string; end?: string }>({
      query: ({ symbol, timeframe, start, end }) => {
        let url = `data/${symbol}/${timeframe}`;
        const params = new URLSearchParams();
        if (start) params.append('start', start);
        if (end) params.append('end', end);
        const queryString = params.toString();
        return queryString ? `${url}?${queryString}` : url;
      },
      providesTags: (result, error, arg) => [{ type: 'OHLCV', id: `${arg.symbol}_${arg.timeframe}` }],
    }),
  }),
});

export const {
  useGetSymbolsQuery,
  useGetTimeframesQuery,
  useGetSymbolDataQuery,
} = dataApi;
```

## Data Types

Define TypeScript interfaces for all API data:

```typescript
// src/types/data.ts
export interface Symbol {
  id: string;
  name: string;
  exchange: string;
  type: 'stock' | 'forex' | 'crypto' | 'futures';
}

export interface TimeframeOption {
  id: string;
  label: string;
  value: string;
}

export interface OHLCV {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type OHLCVData = OHLCV[];

export interface APIError {
  status: number;
  message: string;
  data: any;
}
```

## API Hooks

RTK Query automatically generates hooks for each endpoint:

```tsx
import { useGetSymbolsQuery, useGetSymbolDataQuery } from '../api/dataApi';

// In a component:
const SymbolSelector = () => {
  // Fetch all symbols with automatic loading and error states
  const { data: symbols, isLoading, error } = useGetSymbolsQuery();
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Failed to load symbols" />;
  
  return (
    <Select
      options={symbols.map(s => ({ value: s.id, label: s.name }))}
      // ...other props
    />
  );
};

// Using with parameters
const ChartContainer = ({ symbol, timeframe }) => {
  const { data, isLoading, error } = useGetSymbolDataQuery({ 
    symbol, 
    timeframe,
    start: '2023-01-01',
    end: '2023-12-31'
  });
  
  // ...component implementation
};
```

### Creating Custom API Hooks

For more complex API interactions, create custom hooks:

```typescript
import { useState, useEffect } from 'react';
import apiClient from '../api/client';

export const useApiRequest = <T>(url: string, options?: any) => {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get(url, options);
        setData(response.data);
        setError(null);
      } catch (error) {
        setError(error as Error);
        setData(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, [url]);
  
  return { data, isLoading, error };
};
```

## Error Handling

### Standard Error Format

All API errors should follow a consistent format:

```typescript
interface APIError {
  status: number;        // HTTP status code
  message: string;       // User-friendly error message
  details?: unknown;     // Additional error details
  code?: string;         // Error code for specific handling
}
```

### Component-Level Error Handling

Handle API errors gracefully in components:

```tsx
import { useGetSymbolDataQuery } from '../api/dataApi';

const DataDisplay = ({ symbol, timeframe }) => {
  const { data, error, isLoading, refetch } = useGetSymbolDataQuery({ symbol, timeframe });
  
  if (isLoading) return <LoadingSpinner />;
  
  if (error) {
    return (
      <ErrorMessage 
        message={`Failed to load data: ${error.message}`}
        onRetry={refetch}
      />
    );
  }
  
  return <DataVisualization data={data} />;
};
```

### Global Error Handling

Set up global error handling for API calls:

```typescript
// src/utils/errorHandling.ts
import { toast } from 'react-toastify';
import { APIError } from '../types/data';

export const handleApiError = (error: APIError) => {
  // Log error for debugging
  console.error('API Error:', error);
  
  // Show appropriate notification based on error type
  switch (error.status) {
    case 401:
      toast.error('Your session has expired. Please login again.');
      // Redirect to login
      break;
      
    case 403:
      toast.error('You do not have permission to perform this action.');
      break;
      
    case 404:
      toast.error('The requested resource was not found.');
      break;
      
    case 500:
      toast.error('A server error occurred. Please try again later.');
      break;
      
    default:
      toast.error(error.message || 'An unexpected error occurred.');
  }
  
  return error;
};
```

## Caching Strategy

RTK Query provides automatic caching with configurable behavior:

### Cache Configuration

```typescript
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';

export const dataApi = createApi({
  reducerPath: 'dataApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  tagTypes: ['Symbol', 'OHLCV', 'Settings'],
  endpoints: (builder) => ({
    getSymbolData: builder.query<OHLCVData, { symbol: string; timeframe: string }>({
      query: ({ symbol, timeframe }) => `data/${symbol}/${timeframe}`,
      // Cache tags for this query
      providesTags: (result, error, arg) => [
        { type: 'OHLCV', id: `${arg.symbol}_${arg.timeframe}` }
      ],
      // Keep cached data for 5 minutes
      keepUnusedDataFor: 300,
    }),
    
    updateSettings: builder.mutation<any, any>({
      query: (settings) => ({
        url: 'settings',
        method: 'PUT',
        body: settings,
      }),
      // Invalidate the Settings cache when this mutation runs
      invalidatesTags: ['Settings'],
    }),
  }),
});
```

### Manual Cache Invalidation

```typescript
import { useDispatch } from 'react-redux';
import { dataApi } from '../api/dataApi';

const CacheControl = () => {
  const dispatch = useDispatch();
  
  const invalidateAllSymbolData = () => {
    // Invalidate all OHLCV cache entries
    dispatch(dataApi.util.invalidateTags(['OHLCV']));
  };
  
  const invalidateSpecificSymbol = (symbol: string, timeframe: string) => {
    // Invalidate specific cache entry
    dispatch(dataApi.util.invalidateTags([{ type: 'OHLCV', id: `${symbol}_${timeframe}` }]));
  };
  
  return (
    <div>
      <button onClick={invalidateAllSymbolData}>Refresh All Data</button>
    </div>
  );
};
```

## Authentication

The API client automatically handles authentication token management:

### Token Management

```typescript
// src/utils/auth.ts
export const setAuthToken = (token: string) => {
  localStorage.setItem('auth_token', token);
};

export const getAuthToken = (): string | null => {
  return localStorage.getItem('auth_token');
};

export const clearAuthToken = () => {
  localStorage.removeItem('auth_token');
};

// Authentication state listener
export const setupAuthListener = (store) => {
  window.addEventListener('storage', (event) => {
    if (event.key === 'auth_token' && !event.newValue) {
      // Token was removed in another tab/window
      store.dispatch({ type: 'auth/logout' });
    }
  });
};
```

### Authentication API

```typescript
// src/api/authApi.ts
import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { setAuthToken, clearAuthToken } from '../utils/auth';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: {
    id: string;
    username: string;
    email: string;
  };
}

export const authApi = createApi({
  reducerPath: 'authApi',
  baseQuery: fetchBaseQuery({ baseUrl: '/api' }),
  endpoints: (builder) => ({
    login: builder.mutation<LoginResponse, LoginCredentials>({
      query: (credentials) => ({
        url: 'auth/login',
        method: 'POST',
        body: credentials,
      }),
      // Save token on successful login
      onQueryStarted: async (args, { queryFulfilled }) => {
        try {
          const { data } = await queryFulfilled;
          setAuthToken(data.token);
        } catch (error) {
          // Handle login error
        }
      },
    }),
    logout: builder.mutation<void, void>({
      query: () => ({
        url: 'auth/logout',
        method: 'POST',
      }),
      // Clear token on logout
      onQueryStarted: async (args, { queryFulfilled }) => {
        try {
          await queryFulfilled;
          clearAuthToken();
        } catch (error) {
          // Handle logout error
        }
      },
    }),
  }),
});

export const { useLoginMutation, useLogoutMutation } = authApi;
```

## Best Practices

### Optimistic Updates

For better user experience, implement optimistic updates:

```typescript
import { dataApi } from '../api/dataApi';

export const useUpdateFavoriteMutation = dataApi.injectEndpoints({
  endpoints: (builder) => ({
    updateFavorite: builder.mutation<void, { symbolId: string; isFavorite: boolean }>({
      query: ({ symbolId, isFavorite }) => ({
        url: `symbols/${symbolId}/favorite`,
        method: 'PUT',
        body: { isFavorite },
      }),
      // Optimistically update the cache
      async onQueryStarted({ symbolId, isFavorite }, { dispatch, queryFulfilled }) {
        // Get the patch helper for this cache entry
        const patchResult = dispatch(
          dataApi.util.updateQueryData('getSymbols', undefined, (draft) => {
            const symbol = draft.find((s) => s.id === symbolId);
            if (symbol) {
              symbol.isFavorite = isFavorite;
            }
          })
        );
        
        try {
          // Wait for the mutation to finish
          await queryFulfilled;
        } catch {
          // If the mutation fails, revert the optimistic update
          patchResult.undo();
          
          // Show error message
          toast.error('Failed to update favorite status');
        }
      },
    }),
  }),
});

export const { useUpdateFavoriteMutation } = useUpdateFavoriteMutation;
```

### Request Throttling and Debouncing

For search inputs and other frequent updates:

```typescript
import { useEffect, useState } from 'react';
import { useDebounce } from '../hooks/useDebounce';
import { useSearchSymbolsQuery } from '../api/dataApi';

export const SymbolSearch = () => {
  const [searchTerm, setSearchTerm] = useState('');
  // Debounce search term to avoid excessive API calls
  const debouncedSearchTerm = useDebounce(searchTerm, 300);
  
  // Only fetch when debounced value changes and is not empty
  const { data, isLoading } = useSearchSymbolsQuery(
    debouncedSearchTerm,
    { skip: !debouncedSearchTerm }
  );
  
  return (
    <div>
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        placeholder="Search symbols..."
      />
      {isLoading && <LoadingSpinner size="small" />}
      <ul>
        {data?.map(symbol => (
          <li key={symbol.id}>{symbol.name}</li>
        ))}
      </ul>
    </div>
  );
};

// useDebounce hook
export const useDebounce = <T>(value: T, delay: number): T => {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);
  
  return debouncedValue;
};
```

### API Retry Logic

For handling transient network issues:

```typescript
import { createApi, fetchBaseQuery, retry } from '@reduxjs/toolkit/query/react';

// Create a fetch base query with retry logic
const baseQueryWithRetry = retry(
  fetchBaseQuery({ baseUrl: '/api' }),
  {
    maxRetries: 3,
  }
);

export const dataApi = createApi({
  reducerPath: 'dataApi',
  baseQuery: baseQueryWithRetry,
  // ...rest of API definition
});
```

## Examples

### Basic Data Fetching

```tsx
import { useGetSymbolDataQuery } from '../api/dataApi';
import { LoadingSpinner, ErrorMessage, Chart } from '../components';

const SymbolChart = ({ symbol, timeframe }) => {
  const { data, isLoading, error, refetch } = useGetSymbolDataQuery({
    symbol,
    timeframe,
  });
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message="Failed to load data" onRetry={refetch} />;
  
  return <Chart data={data} />;
};
```

### Form Submission

```tsx
import { useCreateSettingsMutation } from '../api/settingsApi';

const SettingsForm = () => {
  const [formData, setFormData] = useState({ /* initial form state */ });
  const [saveSettings, { isLoading, isSuccess, error }] = useCreateSettingsMutation();
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await saveSettings(formData).unwrap();
      toast.success('Settings saved successfully');
    } catch (error) {
      // Error handling done by the mutation automatically
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Saving...' : 'Save Settings'}
      </button>
      {error && <ErrorMessage message={error.message} />}
      {isSuccess && <SuccessMessage message="Settings saved successfully" />}
    </form>
  );
};
```

### Conditional Fetching

```tsx
import { useGetSymbolDataQuery } from '../api/dataApi';

const ConditionalData = ({ symbol, timeframe, enabled }) => {
  // Skip query when not enabled
  const { data } = useGetSymbolDataQuery(
    { symbol, timeframe },
    { skip: !enabled }
  );
  
  return (
    <div>
      {enabled ? (
        data ? <DataDisplay data={data} /> : <LoadingSpinner />
      ) : (
        <p>Select options to load data</p>
      )}
    </div>
  );
};
```

### Polling for Real-time Updates

```tsx
import { useGetLiveDataQuery } from '../api/liveDataApi';

const LiveDataDisplay = () => {
  // Poll for updates every 5 seconds
  const { data, isLoading } = useGetLiveDataQuery(undefined, {
    pollingInterval: 5000,
  });
  
  return (
    <div>
      <h2>Live Data</h2>
      {isLoading && <LoadingIndicator />}
      {data && <DataVisualization data={data} />}
    </div>
  );
};
```

### Lazy Query Execution

```tsx
import { useLazyGetSymbolDataQuery } from '../api/dataApi';

const DataLoader = () => {
  // Create a trigger function that can be called on demand
  const [fetchData, { data, isLoading, error }] = useLazyGetSymbolDataQuery();
  
  const handleLoadData = () => {
    fetchData({ symbol: 'AAPL', timeframe: '1d' });
  };
  
  return (
    <div>
      <button onClick={handleLoadData} disabled={isLoading}>
        {isLoading ? 'Loading...' : 'Load Data'}
      </button>
      {data && <Chart data={data} />}
      {error && <ErrorMessage message={error.message} />}
    </div>
  );
};
```