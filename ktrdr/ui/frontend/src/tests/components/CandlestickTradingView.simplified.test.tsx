import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CandlestickTradingView from '@/components/charts/CandlestickTradingView';
import { renderWithProviders } from '../test-utils';
import { OHLCVData } from '@/types/data';

// Mock the CSS import that's causing issues
vi.mock('@/features/charting/ChartContainer.css', () => ({}));

// Sample OHLCV data for testing
const sampleData: OHLCVData = {
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
    points: 3,
  },
};

// Mock ResizeObserver
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}

// Save originals to restore later
let originalResizeObserver: any;
let originalLightweightCharts: any;

// Mock global objects
beforeEach(() => {
  // Save originals
  originalResizeObserver = global.ResizeObserver;
  originalLightweightCharts = global.LightweightCharts;
  
  // Mock ResizeObserver
  global.ResizeObserver = MockResizeObserver as any;
  
  // Mock window.LightweightCharts
  global.LightweightCharts = {
    createChart: vi.fn().mockReturnValue({
      addCandlestickSeries: vi.fn().mockReturnValue({
        setData: vi.fn()
      }),
      addHistogramSeries: vi.fn().mockReturnValue({
        setData: vi.fn()
      }),
      priceScale: vi.fn().mockReturnValue({
        applyOptions: vi.fn()
      }),
      timeScale: vi.fn().mockReturnValue({
        fitContent: vi.fn()
      }),
      applyOptions: vi.fn(),
      resize: vi.fn(),
      remove: vi.fn(),
      removeSeries: vi.fn() // Add the missing removeSeries function
    })
  };
});

// Restore originals
afterEach(() => {
  global.ResizeObserver = originalResizeObserver;
  global.LightweightCharts = originalLightweightCharts;
});

describe('CandlestickTradingView Component - Simplified Tests', () => {
  /**
   * Test 1: Basic Rendering
   * Checks that the component renders without crashing and displays the title
   */
  it('renders without crashing', () => {
    render(<CandlestickTradingView data={sampleData} />);
    
    expect(screen.getByText('Candlestick Chart')).toBeInTheDocument();
    expect(screen.getByText('AAPL - 1d')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /hide volume/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fit all/i })).toBeInTheDocument();
  });

  /**
   * Test 2: Renders correctly with custom props
   * Checks that the component respects custom props
   */
  it('renders with custom props', () => {
    render(
      <CandlestickTradingView 
        data={sampleData} 
        title="Custom Chart Title"
        showVolume={false}
        height={500}
      />
    );
    
    expect(screen.getByText('Custom Chart Title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /show volume/i })).toBeInTheDocument();
    
    // Check height is applied to container
    const container = document.querySelector('.chart-container-inner');
    expect(container).not.toBeNull();
    expect(container?.style.height).toBe('500px');
  });

  /**
   * Test 3: Displays "No data" message when no data is provided
   * Checks that the component handles empty data gracefully
   */
  it('displays no data message when no data is available', () => {
    const emptyData: OHLCVData = {
      dates: [],
      ohlcv: [],
      metadata: {
        symbol: '',
        timeframe: '',
        start: '',
        end: '',
        points: 0
      }
    };
    
    render(<CandlestickTradingView data={emptyData} />);
    
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  /**
   * Test 4: Button Interactions
   * Tests that the volume toggle and fit buttons respond to clicks
   */
  it('changes volume button text when clicked', async () => {
    const user = userEvent.setup();
    render(<CandlestickTradingView data={sampleData} />);
    
    // Initially should say "Hide Volume"
    const volumeButton = screen.getByRole('button', { name: /hide volume/i });
    expect(volumeButton).toBeInTheDocument();
    
    // Click to toggle
    await user.click(volumeButton);
    
    // Should now say "Show Volume"
    expect(screen.getByRole('button', { name: /show volume/i })).toBeInTheDocument();
  });
});