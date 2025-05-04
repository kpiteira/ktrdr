import { describe, it, expect, vi } from 'vitest';
import {
  convertToChartTime,
  detectTimeFormat,
  formatTimeForDisplay,
  getTimeFormatForTimeframe,
  formatCandlestickData,
  formatLineData,
  formatHistogramData,
  formatBarData,
  preprocessData,
  createTestData,
  TIME_FORMAT
} from '@/utils/charts/chartDataUtils';
import { OHLCVData } from '@/types/data';

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

// Sample data with missing values
const dataWithMissingValues: OHLCVData = {
  dates: [
    '2023-01-01T00:00:00.000Z',
    '2023-01-02T00:00:00.000Z',
    '2023-01-03T00:00:00.000Z',
  ],
  ohlcv: [
    [150.0, 152.5, 148.5, 151.0, 1000000],
    // @ts-ignore - deliberately creating invalid data for testing
    [151.0, null, 150.0, 152.5, undefined],
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

describe('Chart Data Utilities', () => {
  describe('Time Format Detection and Conversion', () => {
    it('detects ISO time format', () => {
      const format = detectTimeFormat('2023-01-01T00:00:00.000Z');
      expect(format).toBe(TIME_FORMAT.ISO);
    });
    
    it('detects Unix timestamp format', () => {
      const format = detectTimeFormat(1672531200); // 2023-01-01 00:00:00 UTC
      expect(format).toBe(TIME_FORMAT.UNIX);
    });
    
    it('detects YYYY-MM-DD format', () => {
      const format = detectTimeFormat('2023-01-01');
      expect(format).toBe(TIME_FORMAT.YEAR_MONTH_DAY);
    });
    
    it('converts ISO string to chart time', () => {
      const time = convertToChartTime('2023-01-01T00:00:00.000Z');
      // Verify it's a number (Unix timestamp in seconds)
      expect(typeof time).toBe('number');
      // Close to 1672531200 (2023-01-01 00:00:00 UTC)
      expect(Math.abs((time as number) - 1672531200)).toBeLessThan(10);
    });
    
    it('converts Unix timestamp to chart time', () => {
      const time = convertToChartTime(1672531200);
      expect(time).toBe(1672531200);
    });
    
    it('converts Unix timestamp in milliseconds to chart time in seconds', () => {
      const time = convertToChartTime(1672531200000);
      expect(time).toBe(1672531200);
    });
  });
  
  describe('Time Display Formatting', () => {
    it('formats time for display based on timeframe', () => {
      const timestamp = 1672531200; // 2023-01-01 00:00:00 UTC
      
      // Test daily format
      const dailyFormat = formatTimeForDisplay(
        timestamp, 
        '1d',
        TIME_FORMAT.MONTH_DAY_YEAR
      );
      expect(dailyFormat).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
      
      // Test hour format
      const hourFormat = formatTimeForDisplay(
        timestamp, 
        '1h',
        TIME_FORMAT.MONTH_DAY_HOUR_MINUTE
      );
      expect(hourFormat).toMatch(/\d{1,2}\/\d{1,2} \d{2}:\d{2}/);
    });
    
    it('selects appropriate format for timeframe', () => {
      expect(getTimeFormatForTimeframe('1m')).toBe(TIME_FORMAT.HOUR_MINUTE);
      expect(getTimeFormatForTimeframe('1h')).toBe(TIME_FORMAT.MONTH_DAY_HOUR_MINUTE);
      expect(getTimeFormatForTimeframe('1d')).toBe(TIME_FORMAT.MONTH_DAY_YEAR);
      expect(getTimeFormatForTimeframe('1w')).toBe(TIME_FORMAT.MONTH_DAY_YEAR);
    });
  });
  
  describe('Data Format Conversion', () => {
    it('converts OHLCV data to candlestick format', () => {
      const candlestickData = formatCandlestickData(sampleData);
      
      expect(candlestickData.length).toBe(3);
      expect(candlestickData[0]).toHaveProperty('time');
      expect(candlestickData[0]).toHaveProperty('open', 150.0);
      expect(candlestickData[0]).toHaveProperty('high', 152.5);
      expect(candlestickData[0]).toHaveProperty('low', 148.5);
      expect(candlestickData[0]).toHaveProperty('close', 151.0);
    });
    
    it('converts OHLCV data to line format', () => {
      const lineData = formatLineData(sampleData, 'close');
      
      expect(lineData.length).toBe(3);
      expect(lineData[0]).toHaveProperty('time');
      expect(lineData[0]).toHaveProperty('value', 151.0); // Close value
      
      // Test with different value field
      const highData = formatLineData(sampleData, 'high');
      expect(highData[0]).toHaveProperty('value', 152.5); // High value
    });
    
    it('converts OHLCV data to histogram format', () => {
      const histogramData = formatHistogramData(sampleData);
      
      expect(histogramData.length).toBe(3);
      expect(histogramData[0]).toHaveProperty('time');
      expect(histogramData[0]).toHaveProperty('value', 1000000); // Volume value
      expect(histogramData[0]).toHaveProperty('color');
      
      // Test with custom colors
      const customColors = formatHistogramData(
        sampleData, 
        'volume', 
        'green', 
        'red'
      );
      
      expect(customColors[0].color).toMatch(/green|red/);
    });
    
    it('converts OHLCV data to bar format', () => {
      const barData = formatBarData(sampleData);
      
      expect(barData.length).toBe(3);
      expect(barData[0]).toHaveProperty('time');
      expect(barData[0]).toHaveProperty('open', 150.0);
      expect(barData[0]).toHaveProperty('high', 152.5);
      expect(barData[0]).toHaveProperty('low', 148.5);
      expect(barData[0]).toHaveProperty('close', 151.0);
    });
    
    it('handles empty or invalid data gracefully', () => {
      expect(formatCandlestickData(null as unknown as OHLCVData)).toEqual([]);
      expect(formatLineData(null as unknown as OHLCVData)).toEqual([]);
      expect(formatHistogramData(null as unknown as OHLCVData)).toEqual([]);
      expect(formatBarData(null as unknown as OHLCVData)).toEqual([]);
      
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
      
      expect(formatCandlestickData(emptyData)).toEqual([]);
    });
  });
  
  describe('Data Preprocessing', () => {
    it('fills missing values with previous values', () => {
      const processed = preprocessData(dataWithMissingValues, 'previous');
      
      // Check that the null high value was filled with previous value
      expect(processed.ohlcv[1][1]).toBe(152.5);
      
      // Check that undefined volume was filled with previous value
      expect(processed.ohlcv[1][4]).toBe(1000000);
    });
    
    it('fills missing values with zeros', () => {
      const processed = preprocessData(dataWithMissingValues, 'zero');
      
      // Check that the null high value was filled with zero
      expect(processed.ohlcv[1][1]).toBe(0);
      
      // Check that undefined volume was filled with zero
      expect(processed.ohlcv[1][4]).toBe(0);
    });
    
    it('fills missing values with linear interpolation', () => {
      const processed = preprocessData(dataWithMissingValues, 'linear');
      
      // Calculate expected value: linear interpolation between
      // first and third point high values
      const expectedHigh = 152.5 + (155.0 - 152.5) * 0.5;
      
      // Check that the null high value was filled with linear interpolation
      expect(processed.ohlcv[1][1]).toBeCloseTo(expectedHigh);
      
      // Calculate expected volume
      const expectedVolume = 1000000 + (1500000 - 1000000) * 0.5;
      
      // Check that undefined volume was filled with linear interpolation
      expect(processed.ohlcv[1][4]).toBeCloseTo(expectedVolume);
    });
    
    it('leaves data unchanged with "none" method', () => {
      const processed = preprocessData(dataWithMissingValues, 'none');
      
      // Values should remain null/undefined
      expect(processed.ohlcv[1][1]).toBeNull();
      expect(processed.ohlcv[1][4]).toBeUndefined();
    });
  });
  
  describe('Test Data Generation', () => {
    it('creates test data with specified parameters', () => {
      const points = 10;
      const symbol = 'TEST';
      const timeframe = '1d';
      const testData = createTestData(points, symbol, timeframe);
      
      expect(testData.dates.length).toBe(points);
      expect(testData.ohlcv.length).toBe(points);
      expect(testData.metadata.symbol).toBe(symbol);
      expect(testData.metadata.timeframe).toBe(timeframe);
      expect(testData.metadata.points).toBe(points);
    });
    
    it('generates realistic OHLCV values', () => {
      const testData = createTestData(100);
      
      // Check for reasonable price values
      for (const [open, high, low, close, volume] of testData.ohlcv) {
        // Prices should be near the starting value of 100
        expect(open).toBeGreaterThan(50);
        expect(open).toBeLessThan(150);
        
        // High should be highest, low should be lowest
        expect(high).toBeGreaterThanOrEqual(open);
        expect(high).toBeGreaterThanOrEqual(close);
        expect(low).toBeLessThanOrEqual(open);
        expect(low).toBeLessThanOrEqual(close);
        
        // Volume should be reasonable
        expect(volume).toBeGreaterThan(0);
      }
    });
  });
});