import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ChartPage from '../../features/charting/ChartPage';
import { useOHLCVData } from '../../api/hooks/useData';
import { ThemeProvider } from '../../components/layouts/ThemeProvider';

// Mock the API hook
jest.mock('../../api/hooks/useData', () => ({
  useOHLCVData: jest.fn()
}));

// Mock the ChartPanel component
jest.mock('../../features/charting/ChartPanel', () => ({
  __esModule: true,
  default: jest.fn(() => <div data-testid="chart-panel">Chart Panel Mock</div>)
}));

describe('ChartPage Component', () => {
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();
  });

  test('renders loading state when data is loading', () => {
    // Setup the mock to return loading state
    (useOHLCVData as jest.Mock).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      refetch: jest.fn()
    });

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/charts/AAPL']}>
          <Routes>
            <Route path="/charts/:symbol" element={<ChartPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Check that loading spinner is shown
    expect(screen.getByText('Loading chart data...')).toBeInTheDocument();
  });

  test('renders error state when API returns an error', () => {
    // Setup the mock to return error state
    (useOHLCVData as jest.Mock).mockReturnValue({
      data: null,
      isLoading: false,
      error: { message: 'Failed to load data' },
      refetch: jest.fn()
    });

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/charts/AAPL']}>
          <Routes>
            <Route path="/charts/:symbol" element={<ChartPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Check that error message is shown
    expect(screen.getByText(/Error loading chart data:/)).toBeInTheDocument();
  });

  test('renders chart panel when data is loaded successfully', async () => {
    // Mock data for the test
    const mockData = {
      dates: ['2023-01-01', '2023-01-02'],
      ohlcv: [
        [100, 110, 90, 105, 1000],
        [105, 115, 95, 110, 1200]
      ],
      metadata: {
        symbol: 'AAPL',
        timeframe: '1d'
      }
    };

    // Setup the mock to return success state with data
    (useOHLCVData as jest.Mock).mockReturnValue({
      data: mockData,
      isLoading: false,
      error: null,
      refetch: jest.fn()
    });

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/charts/AAPL']}>
          <Routes>
            <Route path="/charts/:symbol" element={<ChartPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Check that chart panel is rendered
    await waitFor(() => {
      expect(screen.getByTestId('chart-panel')).toBeInTheDocument();
    });
    
    // Check that symbol info is shown
    expect(screen.getByText(/AAPL - 1d Chart/)).toBeInTheDocument();
  });

  test('shows error when no symbol is provided', () => {
    // Setup the test with no symbol parameter
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/charts/']}>
          <Routes>
            <Route path="/charts/:symbol" element={<ChartPage />} />
            <Route path="/charts/" element={<ChartPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Check that error message is shown for missing symbol
    expect(screen.getByText('No symbol specified. Please select a symbol.')).toBeInTheDocument();
  });
});