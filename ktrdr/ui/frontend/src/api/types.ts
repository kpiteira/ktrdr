/**
 * API types for KTRDR frontend
 * These types define the structure of API requests and responses
 */

/**
 * Standard API response envelope
 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

/**
 * API error structure
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

/**
 * Symbol information
 */
export interface SymbolInfo {
  symbol: string;
  name: string;
  exchange?: string;
  type?: string;
  currency?: string;
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
 * Indicator parameter definition
 */
export interface IndicatorParameter {
  name: string;
  type: string;
  description: string;
  default: any;
  min_value?: number;
  max_value?: number;
  options?: string[];
}

/**
 * Indicator metadata
 */
export interface IndicatorInfo {
  id: string;
  name: string;
  description: string;
  type: string;
  parameters: IndicatorParameter[];
}

/**
 * Indicator configuration for API requests
 */
export interface IndicatorConfig {
  id: string;
  parameters: Record<string, any>;
  output_name?: string;
}

/**
 * Indicator calculation result
 */
export interface IndicatorData {
  dates: string[];
  indicators: Record<string, number[]>;
  metadata: {
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    points: number;
    total_items: number;
    total_pages: number;
    current_page: number;
    page_size: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

/**
 * Date range parameters
 */
export interface DateRangeParams {
  startDate?: string;
  endDate?: string;
}

/**
 * Pagination parameters
 */
export interface PaginationParams {
  page?: number;
  pageSize?: number;
}

/**
 * Data load request parameters
 */
export interface DataLoadParams extends DateRangeParams, PaginationParams {
  symbol: string;
  timeframe: string;
}

/**
 * Cache control parameters
 */
export interface CacheControlParams {
  forceRefresh?: boolean;
  cacheTtl?: number;
}