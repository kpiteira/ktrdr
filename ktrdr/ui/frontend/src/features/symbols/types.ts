/**
 * Symbol types for KTRDR frontend
 * Defines interfaces for symbol data and related functionality
 */

/**
 * Represents a trading symbol with its metadata
 */
export interface SymbolInfo {
  /** Symbol identifier (e.g., 'AAPL', 'MSFT') */
  symbol: string;
  /** Full name of the symbol (e.g., 'Apple Inc.') */
  name?: string;
  /** Exchange where the symbol is traded (e.g., 'NASDAQ') */
  exchange?: string;
  /** Type of the symbol (e.g., 'stock', 'forex', 'crypto') */
  type?: string;
  /** Currency in which the symbol is traded */
  currency?: string;
  /** Available timeframes for this symbol */
  available_timeframes?: string[];
}

/**
 * Filter options for symbol list
 */
export interface SymbolFilterOptions {
  /** Text to search for in symbol name or identifier */
  searchText?: string;
  /** Filter by symbol type */
  type?: string;
  /** Filter by exchange */
  exchange?: string;
}