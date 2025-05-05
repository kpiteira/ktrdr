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

// Indicator type representation
export enum IndicatorType {
  LINE = 'line',           // Single line indicator (SMA, EMA)
  MULTI_LINE = 'multiLine', // Multiple lines (Bollinger Bands)
  HISTOGRAM = 'histogram',  // Bar chart (Volume, MACD histogram)
  AREA = 'area',           // Area chart (ATR, filled areas)
  CLOUD = 'cloud'          // Cloud/ribbon (Ichimoku, Bollinger cloud)
}

// Visual display location
export enum IndicatorDisplay {
  OVERLAY = 'overlay',     // Displayed on main price chart
  SEPARATE = 'separate'    // Displayed in separate panel
}

// Indicator parameter definition
export interface IndicatorParameter {
  name: string;
  label: string;
  type: 'number' | 'string' | 'boolean' | 'select';
  defaultValue: number | string | boolean;
  min?: number;
  max?: number;
  step?: number;
  options?: Array<{value: string | number, label: string}>;
}

// Indicator metadata interface
export interface IndicatorMetadata {
  id: string;
  name: string;
  description: string;
  type: IndicatorType;
  display: IndicatorDisplay;
  parameters: IndicatorParameter[];
  defaultColor: string | string[];
  defaultLineWidth?: number;
  defaultLineStyle?: string;
  references?: {name: string, url: string}[];
}

// Indicator configuration for creating an indicator instance
export interface IndicatorConfig {
  id: string;                // Unique ID for this indicator instance
  indicatorId: string;       // Reference to the indicator type (matches IndicatorMetadata.id)
  visible: boolean;          // Whether indicator is currently visible
  parameters: Record<string, any>; // Parameter values for this instance
  colors: string[];          // Colors for this indicator instance
  lineStyles?: string[];     // Line styles (solid, dotted, dashed)
  lineWidths?: number[];     // Line widths in pixels
  panelHeight?: number;      // Height for separate panel indicators
  opacity?: number;          // Opacity value for area/cloud indicators
}

// Indicator data returned from API/calculation
export interface IndicatorData {
  indicatorId: string;       // Matches the indicator configuration ID
  dates: string[];           // Dates/times matching the base data
  values: number[][];        // Array of values series (can be multiple for multi-line indicators)
  metadata?: {               // Optional metadata about the indicator
    names?: string[];        // Names for each series
    colors?: string[];       // Colors for each series
    min?: number;            // Minimum value (for scaling)
    max?: number;            // Maximum value (for scaling)
    precision?: number;      // Decimal precision
  };
}