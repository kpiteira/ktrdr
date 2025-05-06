/**
 * Types related to indicators functionality
 */

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