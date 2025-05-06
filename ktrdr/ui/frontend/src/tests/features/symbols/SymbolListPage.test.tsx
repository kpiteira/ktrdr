/**
 * Tests for SymbolListPage component
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { MemoryRouter } from 'react-router-dom';
import SymbolListPage from '../../../features/symbols/SymbolListPage';
import symbolsReducer from '../../../features/symbols/store/symbolsSlice';
import * as symbolHooks from '../../../features/symbols/hooks/useSymbolSelection';

// Mock useNavigate
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate
}));

// Sample symbol data for testing
const mockSymbols = [
  { 
    symbol: 'AAPL', 
    name: 'Apple Inc.', 
    exchange: 'NASDAQ', 
    type: 'stock' 
  },
  { 
    symbol: 'MSFT', 
    name: 'Microsoft Corporation', 
    exchange: 'NASDAQ', 
    type: 'stock' 
  },
  { 
    symbol: 'EURUSD', 
    name: 'Euro/USD', 
    exchange: 'FOREX', 
    type: 'forex' 
  }
];

// Create a mock store for testing
const createMockStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      symbols: symbolsReducer
    },
    preloadedState: {
      symbols: {
        symbols: [],
        timeframes: [],
        currentSymbol: null,
        currentTimeframe: null,
        symbolsStatus: 'idle',
        timeframesStatus: 'idle',
        error: null,
        ...initialState
      }
    }
  });
};

describe('SymbolListPage', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  // Test loading state
  it('displays loading state when symbols are loading', () => {
    // Mock the useSymbolSelection hook
    jest.spyOn(symbolHooks, 'useSymbolSelection').mockReturnValue({
      symbols: [],
      timeframes: [],
      currentSymbol: null,
      currentTimeframe: null,
      symbolsStatus: 'loading',
      timeframesStatus: 'idle',
      error: null,
      isLoading: true,
      loadMetadata: jest.fn(),
      selectSymbol: jest.fn(),
      selectTimeframe: jest.fn(),
      hasActiveSelection: false
    });

    render(
      <Provider store={createMockStore()}>
        <MemoryRouter>
          <SymbolListPage />
        </MemoryRouter>
      </Provider>
    );

    expect(screen.getByText(/Loading symbols/i)).toBeInTheDocument();
  });

  // Test error state
  it('displays error state', () => {
    const mockError = new Error('Failed to fetch symbols');
    
    // Mock the useSymbolSelection hook with error
    jest.spyOn(symbolHooks, 'useSymbolSelection').mockReturnValue({
      symbols: [],
      timeframes: [],
      currentSymbol: null,
      currentTimeframe: null,
      symbolsStatus: 'failed',
      timeframesStatus: 'idle',
      error: mockError,
      isLoading: false,
      loadMetadata: jest.fn(),
      selectSymbol: jest.fn(),
      selectTimeframe: jest.fn(),
      hasActiveSelection: false
    });

    render(
      <Provider store={createMockStore()}>
        <MemoryRouter>
          <SymbolListPage />
        </MemoryRouter>
      </Provider>
    );

    expect(screen.getByText(/Failed to fetch symbols/i)).toBeInTheDocument();
    expect(screen.getByText(/Try Again/i)).toBeInTheDocument();
  });

  // Test successful data loading and display
  it('displays symbol list when data is loaded', () => {
    // Mock the useSymbolSelection hook with data
    jest.spyOn(symbolHooks, 'useSymbolSelection').mockReturnValue({
      symbols: mockSymbols,
      timeframes: [],
      currentSymbol: null,
      currentTimeframe: null,
      symbolsStatus: 'succeeded',
      timeframesStatus: 'idle',
      error: null,
      isLoading: false,
      loadMetadata: jest.fn(),
      selectSymbol: jest.fn(),
      selectTimeframe: jest.fn(),
      hasActiveSelection: false
    });

    render(
      <Provider store={createMockStore({ symbols: mockSymbols })}>
        <MemoryRouter>
          <SymbolListPage />
        </MemoryRouter>
      </Provider>
    );

    // Check that symbols are displayed
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('Microsoft Corporation')).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();
    
    // Check the table headers
    expect(screen.getByText('Symbol')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Exchange')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
  });

  // Test filtering functionality
  it('filters symbols based on search input', () => {
    const mockLoadMetadata = jest.fn();
    
    // Mock the useSymbolSelection hook with data
    jest.spyOn(symbolHooks, 'useSymbolSelection').mockReturnValue({
      symbols: mockSymbols,
      timeframes: [],
      currentSymbol: null,
      currentTimeframe: null,
      symbolsStatus: 'succeeded',
      timeframesStatus: 'idle',
      error: null,
      isLoading: false,
      loadMetadata: mockLoadMetadata,
      selectSymbol: jest.fn(),
      selectTimeframe: jest.fn(),
      hasActiveSelection: false
    });

    render(
      <Provider store={createMockStore({ symbols: mockSymbols })}>
        <MemoryRouter>
          <SymbolListPage />
        </MemoryRouter>
      </Provider>
    );

    // Initially all symbols should be visible
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('EURUSD')).toBeInTheDocument();

    // Filter for Apple
    const searchInput = screen.getByLabelText(/Search/i);
    fireEvent.change(searchInput, { target: { value: 'Apple' } });
    
    // Wait for the filtering effect to complete
    waitFor(() => {
      // AAPL should still be visible
      expect(screen.getByText('AAPL')).toBeInTheDocument();
      // MSFT and EURUSD should not be visible (filtered out)
      expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
      expect(screen.queryByText('EURUSD')).not.toBeInTheDocument();
    });
  });

  // Test navigation to chart page
  it('navigates to chart page when View Chart button is clicked', async () => {
    // Mock the useSymbolSelection hook with data
    jest.spyOn(symbolHooks, 'useSymbolSelection').mockReturnValue({
      symbols: mockSymbols,
      timeframes: [],
      currentSymbol: null,
      currentTimeframe: null,
      symbolsStatus: 'succeeded',
      timeframesStatus: 'idle',
      error: null,
      isLoading: false,
      loadMetadata: jest.fn(),
      selectSymbol: jest.fn(),
      selectTimeframe: jest.fn(),
      hasActiveSelection: false
    });

    render(
      <Provider store={createMockStore({ symbols: mockSymbols })}>
        <MemoryRouter>
          <SymbolListPage />
        </MemoryRouter>
      </Provider>
    );

    // Find all View Chart buttons and click the first one (AAPL)
    const viewChartButtons = screen.getAllByText('View Chart');
    fireEvent.click(viewChartButtons[0]);
    
    // Check that navigate was called with the correct path
    expect(mockNavigate).toHaveBeenCalledWith('/charts/AAPL');
  });
});