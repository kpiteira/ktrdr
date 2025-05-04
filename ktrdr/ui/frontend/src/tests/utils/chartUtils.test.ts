import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  createChartOptions,
  createCandlestickOptions,
  createLineOptions,
  createHistogramOptions,
  formatCandlestickData,
  formatVolumeData,
  createPriceLine,
  handleChartResize,
  cleanupChart
} from '@/utils/charts/chartUtils';
import { chartThemes } from '@/types/charts';
import { ThemeMode } from '@/types/ui';
import { OHLCVData } from '@/types/data';

// Test data
const sampleOHLCVData: OHLCVData = {
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

describe('Chart Utility Functions', () => {
  const mockChart = {
    resize: vi.fn(),
    remove: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createChartOptions', () => {
    it('returns default chart options with specified theme', () => {
      const lightConfig = { theme: 'light' as ThemeMode, width: 800, height: 400 };
      const darkConfig = { theme: 'dark' as ThemeMode, width: 800, height: 400 };
      
      const lightOptions = createChartOptions(lightConfig);
      const darkOptions = createChartOptions(darkConfig);
      
      // Check dimensions are passed correctly
      expect(lightOptions.width).toBe(800);
      expect(lightOptions.height).toBe(400);
      
      // Check theme values are applied
      expect(lightOptions.layout?.background?.color).toBe(chartThemes.light.backgroundColor);
      expect(darkOptions.layout?.background?.color).toBe(chartThemes.dark.backgroundColor);
      
      // Check grid lines colors
      expect(lightOptions.grid?.vertLines?.color).toBe(chartThemes.light.gridLinesColor);
      expect(darkOptions.grid?.vertLines?.color).toBe(chartThemes.dark.gridLinesColor);
    });

    it('applies default values when options are not provided', () => {
      const options = createChartOptions({});
      
      // Should use light theme by default
      expect(options.layout?.background?.color).toBe(chartThemes.light.backgroundColor);
      
      // Should have default autoSize true
      expect(options.autoSize).toBe(true);
      
      // Should have timeVisible true by default
      expect(options.timeScale?.timeVisible).toBe(true);
    });
  });

  describe('createCandlestickOptions', () => {
    it('returns candlestick options with correct theme colors', () => {
      const lightOptions = createCandlestickOptions('light');
      const darkOptions = createCandlestickOptions('dark');
      
      // Check candle colors
      expect(lightOptions.upColor).toBe(chartThemes.light.candlestick.upColor);
      expect(darkOptions.downColor).toBe(chartThemes.dark.candlestick.downColor);
      
      // Check wick colors
      expect(lightOptions.wickUpColor).toBe(chartThemes.light.candlestick.wickUpColor);
      expect(darkOptions.wickDownColor).toBe(chartThemes.dark.candlestick.wickDownColor);
      
      // Check border visibility
      expect(lightOptions.borderVisible).toBe(true);
      expect(darkOptions.borderVisible).toBe(true);
    });
  });

  describe('createLineOptions', () => {
    it('returns line options with specified color and width', () => {
      const color = '#FF0000';
      const lineWidth = 3;
      
      const options = createLineOptions(color, lineWidth);
      
      expect(options.color).toBe(color);
      expect(options.lineWidth).toBe(lineWidth);
      expect(options.crosshairMarkerVisible).toBe(true);
    });
    
    it('applies default line width when not specified', () => {
      const color = '#0000FF';
      
      const options = createLineOptions(color);
      
      expect(options.color).toBe(color);
      expect(options.lineWidth).toBe(2); // Default line width
    });
  });

  describe('createHistogramOptions', () => {
    it('returns histogram options with specified color', () => {
      const color = '#00FF00';
      
      const options = createHistogramOptions(color);
      
      expect(options.color).toBe(color);
      expect(options.base).toBe(0);
    });
  });

  describe('formatCandlestickData', () => {
    it('formats OHLCV data into candlestick format', () => {
      const formattedData = formatCandlestickData(sampleOHLCVData);
      
      // Check length matches
      expect(formattedData.length).toBe(sampleOHLCVData.dates.length);
      
      // Check format of first item
      const [open, high, low, close] = sampleOHLCVData.ohlcv[0];
      
      expect(formattedData[0].open).toBe(open);
      expect(formattedData[0].high).toBe(high);
      expect(formattedData[0].low).toBe(low);
      expect(formattedData[0].close).toBe(close);
      
      // Check time conversion
      const date = new Date(sampleOHLCVData.dates[0]);
      expect(formattedData[0].time).toBe(date.getTime() / 1000);
    });
    
    it('returns empty array for invalid or empty data', () => {
      expect(formatCandlestickData({ dates: [], ohlcv: [], metadata: {} as any })).toEqual([]);
      expect(formatCandlestickData(null as any)).toEqual([]);
      expect(formatCandlestickData(undefined as any)).toEqual([]);
    });
  });

  describe('formatVolumeData', () => {
    it('formats OHLCV data into volume histogram format', () => {
      const positiveColor = 'rgba(0, 255, 0, 0.5)';
      const negativeColor = 'rgba(255, 0, 0, 0.5)';
      
      const formattedData = formatVolumeData(sampleOHLCVData, positiveColor, negativeColor);
      
      // Check length matches
      expect(formattedData.length).toBe(sampleOHLCVData.dates.length);
      
      // Check volume value
      const [open, , , close, volume] = sampleOHLCVData.ohlcv[0];
      expect(formattedData[0].value).toBe(volume);
      
      // Check color based on price movement
      const firstCandleColor = close >= open ? positiveColor : negativeColor;
      expect(formattedData[0].color).toBe(firstCandleColor);
      
      // Check time conversion
      const date = new Date(sampleOHLCVData.dates[0]);
      expect(formattedData[0].time).toBe(date.getTime() / 1000);
    });
    
    it('uses default colors when not specified', () => {
      const formattedData = formatVolumeData(sampleOHLCVData);
      
      // Default positive color is green
      const [open, , , close] = sampleOHLCVData.ohlcv[0];
      const expectedColor = close >= open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)';
      
      expect(formattedData[0].color).toBe(expectedColor);
    });
    
    it('returns empty array for invalid or empty data', () => {
      expect(formatVolumeData({ dates: [], ohlcv: [], metadata: {} as any })).toEqual([]);
      expect(formatVolumeData(null as any)).toEqual([]);
      expect(formatVolumeData(undefined as any)).toEqual([]);
    });
  });

  describe('createPriceLine', () => {
    it('creates price line options with specified values', () => {
      const price = 150.5;
      const color = '#FF00FF';
      const lineWidth = 2;
      const lineStyle = 1; // Solid
      const text = 'Support Level';
      
      const options = createPriceLine(price, color, lineWidth, lineStyle, text);
      
      expect(options.price).toBe(price);
      expect(options.color).toBe(color);
      expect(options.lineWidth).toBe(lineWidth);
      expect(options.lineStyle).toBe(lineStyle);
      expect(options.title).toBe(text);
      expect(options.axisLabelVisible).toBe(true);
    });
    
    it('applies default values when not specified', () => {
      const price = 200;
      
      const options = createPriceLine(price);
      
      expect(options.price).toBe(price);
      expect(options.color).toBe('rgba(114, 116, 119, 0.5)'); // Default color
      expect(options.lineWidth).toBe(1); // Default line width
      expect(options.lineStyle).toBe(2); // Default line style (dashed)
    });
  });

  describe('handleChartResize', () => {
    it('resizes chart based on container dimensions', () => {
      const container = {
        getBoundingClientRect: () => ({
          width: 1000,
          height: 500,
          x: 0,
          y: 0,
          top: 0,
          left: 0,
          right: 1000,
          bottom: 500,
          toJSON: () => {}
        })
      } as HTMLElement;
      
      handleChartResize(mockChart as any, container);
      
      expect(mockChart.resize).toHaveBeenCalledWith(1000, 500);
    });
    
    it('does nothing when chart or container is null', () => {
      handleChartResize(null, null);
      handleChartResize(mockChart as any, null);
      handleChartResize(null, {} as HTMLElement);
      
      expect(mockChart.resize).not.toHaveBeenCalled();
    });
  });

  describe('cleanupChart', () => {
    it('calls remove on the chart instance', () => {
      cleanupChart(mockChart as any);
      
      expect(mockChart.remove).toHaveBeenCalled();
    });
    
    it('does nothing when chart is null', () => {
      cleanupChart(null);
      // No error should be thrown
    });
  });
});