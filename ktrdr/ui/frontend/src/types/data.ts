/**
 * Data types for KTRDR frontend
 * Defines types for OHLCV data and related structures
 */

// Parameters for loading OHLCV data
export interface DataLoadParams {
  symbol: string;
  timeframe: string;
  startDate?: string;
  endDate?: string;
}

// OHLCV data point structure
export interface OHLCVPoint {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// OHLCV data structure
export interface OHLCVData {
  dates: string[];
  ohlcv: number[][];
  metadata: {
    symbol: string;
    timeframe: string;
    start: string;
    end: string;
    points: number;
  };
}