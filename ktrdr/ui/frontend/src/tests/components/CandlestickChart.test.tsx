import React from 'react';
import { render, screen } from '@testing-library/react';
import CandlestickChart from '../../features/charting/components/CandlestickChart';

// Mock the ThemeProvider hook
jest.mock('../../app/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light' }),
}));

// Mock the Button component
jest.mock('../../components/common/Button', () => ({
  Button: ({ children, onClick }: { children: React.ReactNode, onClick?: () => void }) => 
    <button onClick={onClick} data-testid="mock-button">{children}</button>
}));

// Mock the formatCandlestickData and formatHistogramData functions
jest.mock('../../features/charting/components/transformers/dataAdapters', () => ({
  formatCandlestickData: () => [],
  formatHistogramData: () => [],
}));

// Mock the window.LightweightCharts
global.LightweightCharts = {
  createChart: jest.fn().mockReturnValue({
    applyOptions: jest.fn(),
    resize: jest.fn(),
    timeScale: jest.fn().mockReturnValue({
      fitContent: jest.fn(),
    }),
    priceScale: jest.fn().mockReturnValue({
      applyOptions: jest.fn(),
    }),
    addCandlestickSeries: jest.fn().mockReturnValue({
      setData: jest.fn(),
    }),
    addHistogramSeries: jest.fn().mockReturnValue({
      setData: jest.fn(),
    }),
    removeSeries: jest.fn(),
    remove: jest.fn(),
  }),
};

const mockData = {
  dates: ['2023-01-01', '2023-01-02', '2023-01-03'],
  ohlcv: [
    [100, 110, 90, 105, 1000],
    [105, 115, 100, 110, 1200],
    [110, 120, 105, 115, 900],
  ],
  metadata: {
    symbol: 'AAPL',
    timeframe: '1D',
    start: '2023-01-01',
    end: '2023-01-03',
    points: 3
  }
};

describe('CandlestickChart Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders chart with title and controls', () => {
    render(<CandlestickChart data={mockData} />);
    
    expect(screen.getByText('Candlestick Chart')).toBeInTheDocument();
    expect(screen.getByText('AAPL - 1D')).toBeInTheDocument();
    expect(screen.getByText('Hide Volume')).toBeInTheDocument();
    expect(screen.getByText('Fit All')).toBeInTheDocument();
  });

  test('renders with custom title', () => {
    render(<CandlestickChart data={mockData} title="Custom Chart Title" />);
    
    expect(screen.getByText('Custom Chart Title')).toBeInTheDocument();
  });

  test('renders loading message when library not loaded', () => {
    // Temporarily remove the LightweightCharts from window
    const originalLightweightCharts = window.LightweightCharts;
    delete window.LightweightCharts;
    
    render(<CandlestickChart />);
    
    expect(screen.getByText('Loading chart library...')).toBeInTheDocument();
    
    // Restore the mock
    window.LightweightCharts = originalLightweightCharts;
  });

  test('renders no data message when data is empty', () => {
    render(<CandlestickChart data={{ dates: [], ohlcv: [], metadata: { symbol: '', timeframe: '', start: '', end: '', points: 0 } }} />);
    
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });
});