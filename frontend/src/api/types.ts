/**
 * Core API types for KTRDR frontend
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

// Re-export moved types for backward compatibility
export * from '../features/charting/types';
export * from '../features/indicators/types';