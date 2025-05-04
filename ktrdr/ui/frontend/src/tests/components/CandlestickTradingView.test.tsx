import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import CandlestickTradingView from '@/components/charts/CandlestickTradingView';
import { renderWithProviders } from '../test-utils';
import { OHLCVData } from '@/types/data';

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock the LightweightCharts global object
const mockChart = {
  resize: vi.fn(),
  remove: vi.fn(),
  timeScale: vi.fn().mockReturnValue({
    fitContent: vi.fn()
  }),
  priceScale: vi.fn().mockReturnValue({
    applyOptions: vi.fn()
  }),
  applyOptions: vi.fn(),
  addCandlestickSeries: vi.fn().mockReturnValue({
    setData: vi.fn()
  }),
  addHistogramSeries: vi.fn().mockReturnValue({
    setData: vi.fn()
  }),
  removeSeries: vi.fn()
};

// Mock LightweightCharts
const mockCreateChart = vi.fn().mockReturnValue(mockChart);

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

describe('CandlestickTradingView Component', () => {
  // Set up mocks
  let windowBackup: Partial<Window> = {};

  beforeEach(() => {
    // Back up window.LightweightCharts
    windowBackup = { LightweightCharts: window.LightweightCharts };
    
    // Mock the script loading behavior
    const originalCreateElement = document.createElement;
    const mockScript = originalCreateElement.call(document, 'div');
    // Add mock properties to make it look like a script
    Object.defineProperties(mockScript, {
      src: {
        set: vi.fn(),
        get: vi.fn().mockReturnValue(''),
      },
      async: {
        set: vi.fn(),
        get: vi.fn().mockReturnValue(false),
      },
      onload: {
        set: function(fn) {
          // Execute the onload handler immediately to simulate script loading
          setTimeout(fn, 0);
        },
        get: vi.fn(),
      },
      onerror: {
        set: vi.fn(),
        get: vi.fn(),
      },
    });
    
    // Mock createElement only for script tags
    vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'script') {
        return mockScript;
      }
      return originalCreateElement.call(document, tagName);
    });
    
    // Mock container.contains to avoid issues in cleanup
    vi.spyOn(document.head, 'contains').mockImplementation(() => false);
    
    // Mock appendChild
    vi.spyOn(document.head, 'appendChild').mockImplementation(() => null as any);
    
    // Mock removeChild
    vi.spyOn(document.head, 'removeChild').mockImplementation(() => null as any);
    
    // Mock the LightweightCharts global object
    window.LightweightCharts = { createChart: mockCreateChart };
    
    // Reset all mocks before each test
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    
    // Restore window.LightweightCharts
    window.LightweightCharts = windowBackup.LightweightCharts as any;
    
    // Restore all mocks
    vi.restoreAllMocks();
  });

  /**
   * Test 1: Component Rendering
   * Verifies the basic rendering of the component
   */
  it('renders the chart container', () => {
    const { container } = renderWithProviders(
      <CandlestickTradingView data={sampleData} />
    );
    
    expect(container.querySelector('.chart-wrapper')).toBeInTheDocument();
    expect(container.querySelector('.chart-container-inner')).toBeInTheDocument();
    expect(screen.getByText('Candlestick Chart')).toBeInTheDocument();
  });

  /**
   * Test 2: Library Loading
   * Verifies the library is loaded if not already available
   */
  it('loads the Lightweight Charts library if not available', () => {
    // Remove global LightweightCharts
    delete window.LightweightCharts;
    
    renderWithProviders(<CandlestickTradingView />);
    
    // Verify script loading logic
    expect(document.createElement).toHaveBeenCalledWith('script');
    expect(document.head.appendChild).toHaveBeenCalled();
    expect(screen.getByText('Loading chart library...')).toBeInTheDocument();
  });

  /**
   * Test 3: Chart Initialization
   * Verifies the chart is created when library is loaded
   */
  it('initializes chart when library is loaded', async () => {
    // Render with LightweightCharts available
    renderWithProviders(<CandlestickTradingView data={sampleData} />);
    
    // Check if chart was created
    expect(mockCreateChart).toHaveBeenCalled();
    expect(mockChart.addCandlestickSeries).toHaveBeenCalled();
    
    // Check if data was set
    const candleSeries = mockChart.addCandlestickSeries.mock.results[0].value;
    expect(candleSeries.setData).toHaveBeenCalled();
  });

  /**
   * Test 4: Responsive Sizing
   * Verifies the chart resizes with container size changes
   */
  it('handles responsive sizing correctly', async () => {
    // Set explicit dimensions
    const width = 800;
    const height = 500;
    
    renderWithProviders(
      <CandlestickTradingView 
        data={sampleData} 
        width={width} 
        height={height} 
        autoResize={true} 
      />
    );
    
    // Check if chart was created with specified dimensions
    expect(mockCreateChart).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        width,
        height
      })
    );
    
    // Trigger resize observer callback
    const resizeObserver = ResizeObserver as unknown as jest.Mock;
    const observerInstance = resizeObserver.mock.instances[0];
    const observerCallback = resizeObserver.mock.calls[0][0];
    
    // Call observer callback to simulate resize
    observerCallback();
    
    // Verify resize methods were called
    expect(mockChart.resize).toHaveBeenCalledWith(width, height);
    expect(mockChart.applyOptions).toHaveBeenCalledWith({
      width,
      height
    });
  });

  /**
   * Test 5: Theme Synchronization
   * Verifies the chart adapts to theme changes
   */
  it('synchronizes with theme changes', async () => {
    // We'll need to mock the chartInstance state and effect to test theme changes
    const mockSetChartInstance = vi.fn();
    const originalUseState = React.useState;
    
    // Mock useState for chartInstance
    vi.spyOn(React, 'useState').mockImplementation((initial) => {
      // Only intercept useState for chartInstance
      if (initial === null) {
        return [mockChart, mockSetChartInstance];
      }
      return originalUseState(initial);
    });
    
    const { rerender } = renderWithProviders(
      <CandlestickTradingView data={sampleData} />
    );
    
    // Manually trigger the theme effect
    // Find the useEffect that handles theme changes (index 3 in this component)
    const useEffectSpy = vi.spyOn(React, 'useEffect');
    // Get the effect callback - this is the 4th useEffect in the component (index 3)
    const effectCallback = useEffectSpy.mock.calls[3][0];
    // Call the effect callback manually
    effectCallback();
    
    // Now applyOptions should have been called with theme options
    expect(mockChart.applyOptions).toHaveBeenCalledWith(
      expect.objectContaining({
        layout: expect.anything(),
        grid: expect.anything()
      })
    );
    
    // Clean up
    vi.restoreAllMocks();
  });

  /**
   * Test 6: Volume Toggle
   * Verifies the volume series can be toggled on/off
   */
  it('toggles volume series correctly', async () => {
    const user = userEvent.setup();
    
    // Mock the necessary state hooks and instance variables
    const mockSetVolumeVisible = vi.fn();
    const mockSetVolumeSeries = vi.fn();
    const mockSetChartInstance = vi.fn();
    const mockSetCandlestickSeries = vi.fn();
    
    // Save original useState
    const originalUseState = React.useState;
    
    // Mock useState to return controlled values for volume visibility
    vi.spyOn(React, 'useState').mockImplementation((initialValue) => {
      // Handle each useState call based on its initial value
      if (initialValue === null) {
        return [mockChart, mockSetChartInstance]; // chartInstance state
      } else if (initialValue === true || initialValue === false) {
        // This should handle volumeVisible state - initial is usually showVolume (true)
        return [true, mockSetVolumeVisible]; // Start with volume visible
      } else if (initialValue === null || initialValue === undefined) {
        // This handles volumeSeries and candlestickSeries
        return [mockSeries, mockSetVolumeSeries];
      }
      
      // Fall back to original for any other useState calls
      return originalUseState(initialValue);
    });
    
    renderWithProviders(
      <CandlestickTradingView data={sampleData} showVolume={true} />
    );
    
    // Should show volume by default
    expect(mockChart.addHistogramSeries).toHaveBeenCalled();
    
    // Find volume toggle button
    const volumeButton = screen.getByRole('button', { name: /hide volume/i });
    expect(volumeButton).toBeInTheDocument();
    
    // Click to hide volume - this calls the handleVolumeToggle function
    await user.click(volumeButton);
    
    // Check if setVolumeVisible was called with the opposite of current value (false)
    expect(mockSetVolumeVisible).toHaveBeenCalledWith(false);
    
    // Clean up
    vi.restoreAllMocks();
  });

  /**
   * Test 7: Fit Content
   * Verifies the fit content button works
   */
  it('handles fit content button correctly', async () => {
    const user = userEvent.setup();
    
    renderWithProviders(
      <CandlestickTradingView data={sampleData} />
    );
    
    // Find fit content button
    const fitButton = screen.getByRole('button', { name: /fit all/i });
    expect(fitButton).toBeInTheDocument();
    
    // Click fit content button
    await user.click(fitButton);
    
    // Should call timeScale().fitContent()
    expect(mockChart.timeScale).toHaveBeenCalled();
    expect(mockChart.timeScale().fitContent).toHaveBeenCalled();
  });

  /**
   * Test 8: Cleanup
   * Verifies the chart is properly cleaned up when unmounted
   */
  it('cleans up chart resources on unmount', () => {
    // Mock the useEffect cleanup function
    const cleanupMock = vi.fn();
    
    // Keep track of all registered cleanup functions
    const cleanupFunctions: Function[] = [];
    
    // Mock useEffect to capture cleanup function
    vi.spyOn(React, 'useEffect').mockImplementation((effect, deps) => {
      // Call the effect to get the cleanup function
      const cleanup = effect();
      
      // If a cleanup function is returned, store it
      if (typeof cleanup === 'function') {
        cleanupFunctions.push(cleanup);
      }
      
      // Return the original cleanup to maintain component behavior
      return cleanup;
    });
    
    // Mock chartInstance state
    vi.spyOn(React, 'useState').mockImplementation((initial) => {
      if (initial === null) {
        return [mockChart, vi.fn()]; // For chartInstance
      }
      return React.useState(initial);
    });
    
    const { unmount } = renderWithProviders(
      <CandlestickTradingView data={sampleData} />
    );
    
    // Execute the first cleanup function which should be from chart initialization
    if (cleanupFunctions.length > 0) {
      cleanupFunctions[1](); // The chart initialization effect is usually the second one
    }
    
    // Chart should be removed
    expect(mockChart.remove).toHaveBeenCalled();
    
    // Clean up
    vi.restoreAllMocks();
  });

  /**
   * Test 9: Data Updates
   * Verifies the chart updates when data changes
   */
  it('updates chart when data changes', () => {
    const { rerender } = renderWithProviders(
      <CandlestickTradingView data={sampleData} />
    );
    
    // Get the candlestick series from the first call
    const candleSeries = mockChart.addCandlestickSeries.mock.results[0].value;
    
    // Clear the mock to check for new calls
    candleSeries.setData.mockClear();
    
    // Create updated data
    const updatedData = {
      ...sampleData,
      ohlcv: [
        [152.0, 154.5, 150.5, 153.0, 1100000],
        [153.0, 155.0, 152.0, 154.5, 1300000],
        [154.5, 157.0, 153.5, 156.0, 1600000],
      ]
    };
    
    // Re-render with new data
    rerender(
      <CandlestickTradingView data={updatedData} />
    );
    
    // Verify data was updated
    expect(candleSeries.setData).toHaveBeenCalled();
  });

  /**
   * Test 10: No Data Handling
   * Verifies the chart displays appropriate message when there's no data
   */
  it('shows no data message when data is empty', () => {
    const emptyData: OHLCVData = {
      dates: [],
      ohlcv: [],
      metadata: {
        symbol: 'AAPL',
        timeframe: '1d',
        start: '',
        end: '',
        points: 0
      }
    };
    
    renderWithProviders(
      <CandlestickTradingView data={emptyData} />
    );
    
    // Should show no data message
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });
});