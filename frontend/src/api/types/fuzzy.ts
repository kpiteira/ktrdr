/**
 * Type definitions for fuzzy overlay API
 * These types define the structure of fuzzy membership data from the backend
 */

/**
 * A single fuzzy membership point with timestamp and value
 */
export interface FuzzyMembershipPoint {
  timestamp: string;
  value: number | null;
}

/**
 * Fuzzy membership data for a single fuzzy set
 */
export interface FuzzySetMembership {
  set: string;
  membership: FuzzyMembershipPoint[];
}

/**
 * Complete fuzzy overlay data for all indicators
 * Key is indicator name (e.g., 'rsi', 'macd')
 * Value is array of fuzzy sets for that indicator
 */
export interface FuzzyOverlayData {
  [indicator: string]: FuzzySetMembership[];
}

/**
 * Response from the fuzzy overlay API endpoint
 */
export interface FuzzyOverlayResponse {
  symbol: string;
  timeframe: string;
  data: FuzzyOverlayData;
  warnings?: string[];
}

/**
 * Parameters for requesting fuzzy overlay data
 */
export interface FuzzyOverlayParams {
  symbol: string;
  timeframe: string;
  indicators?: string[];
  start_date?: string;
  end_date?: string;
}

/**
 * Processed fuzzy data ready for chart rendering
 * This is the format used internally by the frontend components
 */
export interface ChartFuzzyData {
  setName: string;
  data: Array<{
    time: number; // Unix timestamp for TradingView
    value: number; // Membership value 0.0-1.0
  }>;
  color: string;
  opacity: number;
}

/**
 * Error response from fuzzy API
 */
export interface FuzzyApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}