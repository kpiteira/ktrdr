/**
 * Indicator types for KTRDR frontend
 * Defines types for technical indicators and their configurations
 */

// Indicator metadata structure
export interface IndicatorMetadata {
  name: string;
  description: string;
  defaultParameters: Record<string, any>;
  category: string;
  availableSources: string[];
}

// Indicator configuration structure
export interface IndicatorConfig {
  name: string;
  parameters: Record<string, any>;
  source?: string;
  color?: string;
  visible?: boolean;
}

// Indicator calculation request parameters
export interface IndicatorCalculationParams {
  symbol: string;
  timeframe: string;
  indicators: IndicatorConfig[];
}