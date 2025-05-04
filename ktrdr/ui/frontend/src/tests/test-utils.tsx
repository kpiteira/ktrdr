import React, { PropsWithChildren, ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { configureStore, PreloadedState } from '@reduxjs/toolkit';
import { Provider } from 'react-redux';
import userEvent from '@testing-library/user-event';

// Mock root reducer instead of importing the actual one
const mockRootReducer = {
  data: (state = {}, action) => state,
  ui: (state = {}, action) => state,
  indicators: (state = {}, action) => state
};

// RootState type that matches our mock reducer
export interface RootState {
  data: any;
  ui: any;
  indicators: any;
}

// Mock theme and notification providers
const MockThemeProvider: React.FC<PropsWithChildren<{}>> = ({ children }) => (
  <div data-testid="theme-provider">{children}</div>
);

const MockNotificationProvider: React.FC<PropsWithChildren<{}>> = ({ children }) => (
  <div data-testid="notification-provider">{children}</div>
);

// This type interface extends the default options for render from RTL
// It allows for having the store preloaded with specific state
interface ExtendedRenderOptions extends Omit<RenderOptions, 'queries'> {
  preloadedState?: PreloadedState<RootState>;
  store?: ReturnType<typeof configureStore>;
}

/**
 * Creates a testing wrapper with Redux and other providers
 */
export function renderWithProviders(
  ui: ReactElement,
  {
    preloadedState = {},
    // Automatically create a store instance if no store was passed in
    store = configureStore({
      reducer: mockRootReducer,
      preloadedState,
    }),
    ...renderOptions
  }: ExtendedRenderOptions = {}
) {
  function Wrapper({ children }: PropsWithChildren<{}>): JSX.Element {
    return (
      <Provider store={store}>
        <MockThemeProvider>
          <MockNotificationProvider>
            {children}
          </MockNotificationProvider>
        </MockThemeProvider>
      </Provider>
    );
  }

  // Return an object with the store and all of RTL's query functions
  return { 
    store, 
    user: userEvent.setup(),
    ...render(ui, { wrapper: Wrapper, ...renderOptions }) 
  };
}

/**
 * Creates mock API responses for testing
 */
export const mockApiResponses = {
  symbols: ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META'],
  timeframes: ['1m', '5m', '15m', '30m', '1h', '4h', '1d'],
  ohlcvData: {
    dates: [
      '2023-01-01T00:00:00.000Z',
      '2023-01-02T00:00:00.000Z',
      '2023-01-03T00:00:00.000Z',
    ],
    ohlcv: [
      [150.0, 152.5, 148.5, 151.0, 1000000],
      [151.0, 153.0, 150.0, 152.5, 1200000],
      [152.5, 155.0, 151.5, 154.0, 1500000],
    ],
    metadata: {
      symbol: 'AAPL',
      timeframe: '1d',
      start: '2023-01-01T00:00:00.000Z',
      end: '2023-01-03T00:00:00.000Z',
      count: 3,
    },
  },
};

/**
 * Test helper for mocking API responses
 */
export const mockFetch = (mockData: any) => {
  global.fetch = vi.fn().mockImplementation(() => 
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockData),
    })
  ) as any;
};

/**
 * Clean up fetch mocks after tests
 */
export const cleanupMocks = () => {
  if (global.fetch) {
    (global.fetch as any).mockRestore();
  }
};