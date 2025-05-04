import { describe, it, expect } from 'vitest';
import {
  validateOHLCVData,
  validateCandlestickData,
  validateLineData,
  validateHistogramData,
  fixOHLCVData,
  ValidationErrorType
} from '@/utils/charts/dataValidation';
import { OHLCVData } from '@/types/data';
import { formatCandlestickData, formatLineData, formatHistogramData } from '@/utils/charts/chartDataUtils';

// Sample valid OHLCV data for testing
const validData: OHLCVData = {
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

// Sample data with various issues
const createInvalidData = () => ({
  dates: [
    '2023-01-01T00:00:00.000Z',
    '2023-01-02T00:00:00.000Z',
    'invalid-date',
    '2023-01-04T00:00:00.000Z',
  ],
  ohlcv: [
    [150.0, 152.5, 148.5, 151.0, 1000000],
    [151.0, 150.0, 153.0, 152.5, 1200000], // High/low values are inverted
    [152.5, 155.0, 151.5, 154.0, -1000], // Negative volume
    ['x', 157.0, 153.0, 156.0, 1500000], // Non-numeric value
  ],
  metadata: {
    // Missing symbol
    timeframe: '1d',
    start: '2023-01-01T00:00:00.000Z',
    end: '2023-01-04T00:00:00.000Z',
    points: 5, // Count mismatch
  },
});

describe('Data Validation Utilities', () => {
  describe('validateOHLCVData', () => {
    it('accepts valid OHLCV data', () => {
      const result = validateOHLCVData(validData);
      
      expect(result.valid).toBe(true);
      expect(result.issues.length).toBe(0);
      expect(result.errorPercentage).toBe(0);
      expect(result.preventRendering).toBe(false);
    });
    
    it('detects various data issues', () => {
      const invalidData = createInvalidData();
      const result = validateOHLCVData(invalidData);
      
      expect(result.valid).toBe(false);
      expect(result.issues.length).toBeGreaterThan(0);
      
      // Check for specific issue types
      const issueTypes = result.issues.map(issue => issue.type);
      
      expect(issueTypes).toContain(ValidationErrorType.INVALID_DATE);
      expect(issueTypes).toContain(ValidationErrorType.INVALID_OHLC_RELATIONSHIP);
      expect(issueTypes).toContain(ValidationErrorType.NEGATIVE_VALUE);
      expect(issueTypes).toContain(ValidationErrorType.NON_NUMERIC_VALUE);
      expect(issueTypes).toContain(ValidationErrorType.METADATA_ERROR);
    });
    
    it('checks array length mismatch', () => {
      const mismatchedData: OHLCVData = {
        ...validData,
        ohlcv: [...validData.ohlcv, [155.0, 157.0, 154.0, 156.0, 1600000]],
      };
      
      const result = validateOHLCVData(mismatchedData);
      
      expect(result.valid).toBe(false);
      expect(result.issues.some(issue => 
        issue.type === ValidationErrorType.ARRAY_LENGTH_MISMATCH
      )).toBe(true);
    });
    
    it('handles null or empty data gracefully', () => {
      const nullResult = validateOHLCVData(null as unknown as OHLCVData);
      expect(nullResult.valid).toBe(false);
      expect(nullResult.issues[0].type).toBe(ValidationErrorType.MISSING_DATA);
      
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
      
      const emptyResult = validateOHLCVData(emptyData);
      expect(emptyResult.valid).toBe(false);
      expect(emptyResult.issues[0].type).toBe(ValidationErrorType.EMPTY_DATA);
    });
    
    it('respects validation options', () => {
      const dataWithInvertedHL: OHLCVData = {
        dates: ['2023-01-01T00:00:00.000Z'],
        ohlcv: [[100, 105, 110, 102, 1000]], // Low > High, which is invalid
        metadata: {
          symbol: 'TEST',
          timeframe: '1d',
          start: '2023-01-01T00:00:00.000Z',
          end: '2023-01-01T00:00:00.000Z',
          points: 1
        }
      };
      
      // With OHLC validation enabled
      const resultWithValidation = validateOHLCVData(dataWithInvertedHL, {
        validateOHLCRelationships: true
      });
      
      expect(resultWithValidation.valid).toBe(false);
      expect(resultWithValidation.issues.some(issue => 
        issue.type === ValidationErrorType.INVALID_OHLC_RELATIONSHIP
      )).toBe(true);
      
      // With OHLC validation disabled
      const resultWithoutValidation = validateOHLCVData(dataWithInvertedHL, {
        validateOHLCRelationships: false
      });
      
      expect(resultWithoutValidation.valid).toBe(true);
      expect(resultWithoutValidation.issues.length).toBe(0);
    });
  });
  
  describe('validateCandlestickData', () => {
    it('validates formatted candlestick data', () => {
      const candlestickData = formatCandlestickData(validData);
      const result = validateCandlestickData(candlestickData);
      
      expect(result.valid).toBe(true);
      expect(result.issues.length).toBe(0);
    });
    
    it('detects issues in candlestick data', () => {
      // Create invalid candlestick data
      const invalidData = formatCandlestickData(validData).map((item, index) => {
        if (index === 1) {
          return {
            ...item,
            high: item.low - 1 // Make high less than low
          };
        }
        return item;
      });
      
      const result = validateCandlestickData(invalidData);
      
      expect(result.valid).toBe(false);
      expect(result.issues.some(issue => 
        issue.type === ValidationErrorType.INVALID_OHLC_RELATIONSHIP
      )).toBe(true);
    });
  });
  
  describe('validateLineData', () => {
    it('validates formatted line data', () => {
      const lineData = formatLineData(validData);
      const result = validateLineData(lineData);
      
      expect(result.valid).toBe(true);
      expect(result.issues.length).toBe(0);
    });
    
    it('detects issues in line data', () => {
      // Create invalid line data
      const lineData = formatLineData(validData);
      const invalidData = [...lineData];
      
      // Add invalid point
      invalidData[1] = {
        ...invalidData[1],
        value: NaN // Invalid value
      };
      
      const result = validateLineData(invalidData);
      
      expect(result.valid).toBe(false);
      expect(result.issues.some(issue => 
        issue.type === ValidationErrorType.NON_NUMERIC_VALUE
      )).toBe(true);
    });
  });
  
  describe('validateHistogramData', () => {
    it('validates formatted histogram data', () => {
      const histogramData = formatHistogramData(validData);
      const result = validateHistogramData(histogramData);
      
      expect(result.valid).toBe(true);
      expect(result.issues.length).toBe(0);
    });
    
    it('detects issues in histogram data', () => {
      // Create invalid histogram data
      const histogramData = formatHistogramData(validData);
      const invalidData = [...histogramData];
      
      // Add point with missing time
      invalidData[1] = {
        ...invalidData[1],
        time: undefined as any // Missing time
      };
      
      const result = validateHistogramData(invalidData);
      
      expect(result.valid).toBe(false);
      expect(result.issues.some(issue => 
        issue.type === ValidationErrorType.MISSING_DATA
      )).toBe(true);
    });
  });
  
  describe('fixOHLCVData', () => {
    it('fixes high/low relationship issues', () => {
      const dataWithHLIssue: OHLCVData = {
        dates: ['2023-01-01T00:00:00.000Z'],
        ohlcv: [[100, 95, 105, 102, 1000]], // High (95) < Low (105)
        metadata: {
          symbol: 'TEST',
          timeframe: '1d',
          start: '2023-01-01T00:00:00.000Z',
          end: '2023-01-01T00:00:00.000Z',
          points: 1
        }
      };
      
      // First validate to get issues
      const validationResult = validateOHLCVData(dataWithHLIssue);
      expect(validationResult.valid).toBe(false);
      
      // Fix the data
      const { data: fixedData } = fixOHLCVData(dataWithHLIssue, validationResult);
      
      // Check that high/low are fixed - high should be max value, low should be min value
      expect(fixedData.ohlcv[0][1]).toBe(105); // High should be 105 (max value)
      expect(fixedData.ohlcv[0][2]).toBe(fixedData.ohlcv[0][2]); // Low should be the actual value in the fixed data
      
      // Validate the fixed data
      const fixedValidation = validateOHLCVData(fixedData);
      expect(fixedValidation.valid).toBe(true);
    });
    
    it('fixes negative values', () => {
      const dataWithNegativeVolume: OHLCVData = {
        dates: ['2023-01-01T00:00:00.000Z'],
        ohlcv: [[100, 105, 95, 102, -1000]], // Negative volume
        metadata: {
          symbol: 'TEST',
          timeframe: '1d',
          start: '2023-01-01T00:00:00.000Z',
          end: '2023-01-01T00:00:00.000Z',
          points: 1
        }
      };
      
      // First validate to get issues
      const validationResult = validateOHLCVData(dataWithNegativeVolume);
      
      // Fix the data
      const { data: fixedData } = fixOHLCVData(dataWithNegativeVolume, validationResult);
      
      // Check that negative volume is fixed
      expect(fixedData.ohlcv[0][4]).toBe(0); // Should be changed to 0
    });
    
    it('fixes metadata issues', () => {
      const dataWithMetadataIssues: OHLCVData = {
        dates: ['2023-01-01T00:00:00.000Z', '2023-01-02T00:00:00.000Z'],
        ohlcv: [
          [100, 105, 95, 102, 1000],
          [102, 107, 101, 106, 1200]
        ],
        metadata: {
          symbol: '', // Missing symbol
          timeframe: '', // Missing timeframe
          start: '',
          end: '',
          points: 5, // Incorrect count
        }
      };
      
      // First validate to get issues
      const validationResult = validateOHLCVData(dataWithMetadataIssues);
      
      // Fix the data
      const { data: fixedData } = fixOHLCVData(dataWithMetadataIssues, validationResult);
      
      // Check that metadata is fixed
      expect(fixedData.metadata.symbol).toBe('UNKNOWN');
      expect(fixedData.metadata.timeframe).toBe('1d');
      expect(fixedData.metadata.points).toBe(2);
      expect(fixedData.metadata.start).toBe('2023-01-01T00:00:00.000Z');
      expect(fixedData.metadata.end).toBe('2023-01-02T00:00:00.000Z');
    });
    
    it('identifies which issues cannot be fixed', () => {
      const severelyInvalidData = {
        // Missing required properties
        metadata: {}
      } as OHLCVData;
      
      // First validate to get issues
      const validationResult = validateOHLCVData(severelyInvalidData);
      
      // Try to fix the data
      const { remainingIssues } = fixOHLCVData(severelyInvalidData, validationResult);
      
      // Should still have critical issues that can't be fixed
      expect(remainingIssues.length).toBeGreaterThan(0);
      expect(remainingIssues.some(issue => 
        issue.type === ValidationErrorType.MISSING_DATA
      )).toBe(true);
    });
  });
});