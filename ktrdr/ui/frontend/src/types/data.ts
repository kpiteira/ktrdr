/**
 * Data types for KTRDR frontend
 */

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

export interface OHLCVPoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}