import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  createCandlestickSeries,
  createLineSeries,
  createHistogramSeries,
  createVolumeSeries,
  createIndicatorPanels
} from '@/utils/charts/chartFactory';
import { ThemeMode } from '@/types/ui';
import { LineData, CandlestickData, HistogramData } from 'lightweight-charts';
import * as chartUtils from '@/utils/charts/chartUtils';

// Mock data
const mockCandlestickData: CandlestickData[] = [
  { time: 1672531200, open: 150, high: 155, low: 148, close: 152 },
  { time: 1672617600, open: 152, high: 158, low: 151, close: 157 }
];

const mockLineData: LineData[] = [
  { time: 1672531200, value: 152 },
  { time: 1672617600, value: 157 }
];

const mockHistogramData: HistogramData[] = [
  { time: 1672531200, value: 1000000, color: 'rgba(0, 255, 0, 0.5)' },
  { time: 1672617600, value: 1200000, color: 'rgba(255, 0, 0, 0.5)' }
];

describe('Chart Factory Functions', () => {
  // Mock chart API
  const mockSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  
  const mockPriceScale = {
    applyOptions: vi.fn()
  };
  
  const mockChart = {
    addCandlestickSeries: vi.fn().mockReturnValue(mockSeries),
    addLineSeries: vi.fn().mockReturnValue(mockSeries),
    addHistogramSeries: vi.fn().mockReturnValue(mockSeries),
    priceScale: vi.fn().mockReturnValue(mockPriceScale)
  };

  // Spy on chart utils
  vi.spyOn(chartUtils, 'createCandlestickOptions').mockImplementation(() => ({ upColor: '#00FF00' }));
  vi.spyOn(chartUtils, 'createLineOptions').mockImplementation(() => ({ color: '#FF0000', lineWidth: 2 }));
  vi.spyOn(chartUtils, 'createHistogramOptions').mockImplementation(() => ({ color: '#0000FF' }));

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createCandlestickSeries', () => {
    it('creates a candlestick series with theme options', () => {
      const theme: ThemeMode = 'dark';
      const series = createCandlestickSeries(mockChart as any, theme);
      
      expect(chartUtils.createCandlestickOptions).toHaveBeenCalledWith(theme);
      expect(mockChart.addCandlestickSeries).toHaveBeenCalledWith({ upColor: '#00FF00' });
      expect(mockSeries.setData).not.toHaveBeenCalled();
    });
    
    it('sets data when provided', () => {
      const theme: ThemeMode = 'light';
      const series = createCandlestickSeries(mockChart as any, theme, mockCandlestickData);
      
      expect(mockSeries.setData).toHaveBeenCalledWith(mockCandlestickData);
    });
  });

  describe('createLineSeries', () => {
    it('creates a line series with specified options', () => {
      const color = '#FF0000';
      const title = 'MA(50)';
      const lineWidth = 3;
      const priceScaleId = 'right';
      
      const series = createLineSeries(
        mockChart as any, 
        color, 
        title, 
        undefined, 
        lineWidth, 
        priceScaleId
      );
      
      expect(chartUtils.createLineOptions).toHaveBeenCalledWith(color, lineWidth);
      expect(mockChart.addLineSeries).toHaveBeenCalledWith({
        ...{ color: '#FF0000', lineWidth: 2 }, // Mocked return value
        title,
        priceScaleId
      });
    });
    
    it('sets data when provided', () => {
      const series = createLineSeries(mockChart as any, '#FF0000', 'Line', mockLineData);
      
      expect(mockSeries.setData).toHaveBeenCalledWith(mockLineData);
    });
    
    it('uses default line width when not specified', () => {
      const series = createLineSeries(mockChart as any, '#FF0000');
      
      expect(chartUtils.createLineOptions).toHaveBeenCalledWith('#FF0000', 2);
    });
  });

  describe('createHistogramSeries', () => {
    it('creates a histogram series with specified options', () => {
      const color = '#0000FF';
      const title = 'Volume';
      const priceScaleId = 'volume';
      
      const series = createHistogramSeries(
        mockChart as any, 
        color, 
        title, 
        undefined, 
        priceScaleId
      );
      
      expect(chartUtils.createHistogramOptions).toHaveBeenCalledWith(color);
      expect(mockChart.addHistogramSeries).toHaveBeenCalledWith({
        ...{ color: '#0000FF' }, // Mocked return value
        title,
        priceScaleId
      });
    });
    
    it('sets data when provided', () => {
      const series = createHistogramSeries(
        mockChart as any, 
        '#0000FF', 
        'Histogram', 
        mockHistogramData
      );
      
      expect(mockSeries.setData).toHaveBeenCalledWith(mockHistogramData);
    });
  });

  describe('createVolumeSeries', () => {
    it('creates a volume series with correct settings', () => {
      const series = createVolumeSeries(mockChart as any);
      
      // Check histogram series was created with volume format
      expect(mockChart.addHistogramSeries).toHaveBeenCalledWith({
        color: 'rgba(38, 166, 154, 0.5)',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
      
      // Check price scale was configured
      expect(mockChart.priceScale).toHaveBeenCalledWith('volume');
      expect(mockPriceScale.applyOptions).toHaveBeenCalledWith({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });
    });
    
    it('sets data when provided', () => {
      const series = createVolumeSeries(mockChart as any, mockHistogramData);
      
      expect(mockSeries.setData).toHaveBeenCalledWith(mockHistogramData);
    });
  });

  describe('createIndicatorPanels', () => {
    it('creates multiple indicator panels with separate scales', () => {
      const indicators = [
        {
          id: 'rsi',
          type: 'line' as const,
          color: '#FF0000',
          title: 'RSI(14)',
          data: mockLineData,
          height: 100
        },
        {
          id: 'macd',
          type: 'histogram' as const,
          color: '#0000FF',
          title: 'MACD',
          data: mockHistogramData
        }
      ];
      
      const seriesMap = createIndicatorPanels(mockChart as any, indicators);
      
      // Check all indicators were created
      expect(seriesMap.size).toBe(2);
      expect(seriesMap.has('rsi')).toBe(true);
      expect(seriesMap.has('macd')).toBe(true);
      
      // Check line series was created for RSI
      expect(mockChart.addLineSeries).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'RSI(14)',
          priceScaleId: 'indicator-rsi'
        })
      );
      
      // Check histogram series was created for MACD
      expect(mockChart.addHistogramSeries).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'MACD',
          priceScaleId: 'indicator-macd'
        })
      );
      
      // Check price scales were configured for each indicator
      expect(mockChart.priceScale).toHaveBeenCalledWith('indicator-rsi');
      expect(mockChart.priceScale).toHaveBeenCalledWith('indicator-macd');
      
      // Check data was set for each series
      expect(mockSeries.setData).toHaveBeenCalledTimes(2);
    });
    
    it('uses main price scale for overlays when specified', () => {
      const mainPriceScaleId = 'right';
      const indicators = [
        {
          id: 'ma50',
          type: 'line' as const,
          color: '#FF0000',
          title: 'MA(50)',
          data: mockLineData
          // No height - should use main scale
        }
      ];
      
      const seriesMap = createIndicatorPanels(mockChart as any, indicators, mainPriceScaleId);
      
      // Check line series was created with main price scale
      expect(mockChart.addLineSeries).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'MA(50)',
          priceScaleId: mainPriceScaleId
        })
      );
      
      // Should not configure a separate price scale
      expect(mockChart.priceScale).not.toHaveBeenCalled();
    });
  });
});