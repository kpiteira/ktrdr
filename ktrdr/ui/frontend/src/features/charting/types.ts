/**
 * Types related to charting functionality
 */

/**
 * OHLCV data structure
 */
export interface OHLCVData {
  dates: string[];
  ohlcv: number[][];
  metadata: {
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    point_count: number;
    source?: string;
  };
}

/**
 * Data range information
 */
export interface DataRangeInfo {
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  point_count: number;
}

/**
 * Timeframe information
 */
export interface TimeframeInfo {
  id: string;
  name: string;
  seconds: number;
  description: string;
}