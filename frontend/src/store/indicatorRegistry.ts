/**
 * Centralized Indicator Registry System
 * 
 * This registry eliminates hardcoded indicator logic and provides a 
 * configuration-driven approach for managing indicators.
 */

export interface ParameterDefinition {
  name: string;
  type: 'number' | 'string' | 'boolean' | 'select' | 'color';
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  default: any;
  label?: string;
  description?: string;
}

export interface IndicatorConfig {
  name: string;
  displayName: string;
  category: string;
  chartType: 'overlay' | 'separate';
  defaultParameters: Record<string, any>;
  parameterDefinitions: ParameterDefinition[];
  colorOptions: string[];
  description?: string;
  // Fuzzy overlay support configuration
  fuzzySupport?: {
    enabled: boolean;
    scalingType: 'fixed' | 'dynamic';
    defaultRange?: { min: number; max: number }; // For fixed scaling
  };
  // Future: validation functions, calculation hints, etc.
}

export interface IndicatorInfo {
  id: string;
  name: string;
  displayName: string;
  parameters: Record<string, any>;
  visible: boolean;
  chartType: 'overlay' | 'separate';
  data?: number[];
  // Fuzzy overlay properties
  /** Whether fuzzy membership overlays are visible on the chart (default: false) */
  fuzzyVisible?: boolean;
  /** Opacity of fuzzy overlays, range 0.0-1.0 (default: 0.3) */
  fuzzyOpacity?: number;
  /** Color scheme for fuzzy sets: 'default', 'monochrome', 'trading' (default: 'default') */
  fuzzyColorScheme?: string;
}

// Centralized indicator registry
export const INDICATOR_REGISTRY: Record<string, IndicatorConfig> = {
  sma: {
    name: 'sma',
    displayName: 'Simple Moving Average',
    category: 'Moving Averages',
    chartType: 'overlay',
    description: 'A trend-following indicator that smooths price data over a specified period',
    defaultParameters: { 
      period: 20, 
      color: '#2196F3' 
    },
    parameterDefinitions: [
      { 
        name: 'period', 
        type: 'number', 
        min: 1, 
        max: 200, 
        step: 1, 
        default: 20,
        label: 'Period',
        description: 'Number of periods to average'
      },
      { 
        name: 'color', 
        type: 'color', 
        default: '#2196F3',
        label: 'Color',
        description: 'Line color for the indicator'
      }
    ],
    colorOptions: ['#2196F3', '#FF5722', '#4CAF50', '#9C27B0', '#FF9800']
  },
  rsi: {
    name: 'rsi',
    displayName: 'Relative Strength Index',
    category: 'Oscillators',
    chartType: 'separate',
    description: 'Momentum oscillator measuring the speed and magnitude of price changes',
    defaultParameters: { 
      period: 14, 
      color: '#FF5722' 
    },
    parameterDefinitions: [
      { 
        name: 'period', 
        type: 'number', 
        min: 2, 
        max: 100, 
        step: 1, 
        default: 14,
        label: 'Period',
        description: 'Number of periods for RSI calculation'
      },
      { 
        name: 'color', 
        type: 'color', 
        default: '#FF5722',
        label: 'Color',
        description: 'Line color for the indicator'
      }
    ],
    colorOptions: ['#FF5722', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800'],
    fuzzySupport: {
      enabled: true,
      scalingType: 'fixed',
      defaultRange: { min: 0, max: 100 }
    }
  },
  macd: {
    name: 'macd',
    displayName: 'MACD',
    category: 'Oscillators',
    chartType: 'separate',
    description: 'Moving Average Convergence Divergence - trend following momentum indicator',
    defaultParameters: { 
      fast_period: 12,
      slow_period: 26,
      signal_period: 9,
      color: '#9C27B0' 
    },
    parameterDefinitions: [
      { 
        name: 'fast_period', 
        type: 'number', 
        min: 2, 
        max: 50, 
        step: 1, 
        default: 12,
        label: 'Fast Period',
        description: 'Fast moving average period'
      },
      { 
        name: 'slow_period', 
        type: 'number', 
        min: 5, 
        max: 100, 
        step: 1, 
        default: 26,
        label: 'Slow Period',
        description: 'Slow moving average period'
      },
      { 
        name: 'signal_period', 
        type: 'number', 
        min: 2, 
        max: 50, 
        step: 1, 
        default: 9,
        label: 'Signal Period',
        description: 'Signal line period'
      },
      { 
        name: 'color', 
        type: 'color', 
        default: '#9C27B0',
        label: 'Color',
        description: 'Line color for the indicator'
      }
    ],
    colorOptions: ['#9C27B0', '#FF5722', '#2196F3', '#4CAF50', '#FF9800'],
    fuzzySupport: {
      enabled: true,
      scalingType: 'dynamic'
    }
  },
  zigzag: {
    name: 'zigzag',
    displayName: 'ZigZag',
    category: 'Pattern Analysis',
    chartType: 'overlay',
    description: 'Identifies significant price reversals by filtering out minor fluctuations',
    defaultParameters: { 
      threshold: 0.05,
      color: '#FF6B35' 
    },
    parameterDefinitions: [
      { 
        name: 'threshold', 
        type: 'number', 
        min: 0.01, 
        max: 0.5, 
        step: 0.01, 
        default: 0.05,
        label: 'Threshold (%)',
        description: 'Minimum percentage move to constitute a reversal'
      },
      { 
        name: 'color', 
        type: 'color', 
        default: '#FF6B35',
        label: 'Color',
        description: 'Line color for the ZigZag'
      }
    ],
    colorOptions: ['#FF6B35', '#2196F3', '#4CAF50', '#9C27B0', '#FF5722']
  }
};

// Helper functions for working with the registry
export const getIndicatorConfig = (name: string): IndicatorConfig | undefined => {
  return INDICATOR_REGISTRY[name];
};

export const getAvailableIndicators = (): IndicatorConfig[] => {
  return Object.values(INDICATOR_REGISTRY);
};

export const getIndicatorsByCategory = (): Record<string, IndicatorConfig[]> => {
  const indicators = getAvailableIndicators();
  return indicators.reduce((acc, indicator) => {
    const category = indicator.category;
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(indicator);
    return acc;
  }, {} as Record<string, IndicatorConfig[]>);
};

export const createIndicatorInstance = (
  name: string, 
  id: string, 
  customParameters?: Record<string, any>
): IndicatorInfo | null => {
  const config = getIndicatorConfig(name);
  if (!config) {
    return null;
  }

  return {
    id,
    name: config.name,
    displayName: config.displayName,
    parameters: { ...config.defaultParameters, ...customParameters },
    visible: true,
    chartType: config.chartType,
    // Fuzzy overlay defaults
    fuzzyVisible: false,
    fuzzyOpacity: 0.3,
    fuzzyColorScheme: 'default'
  };
};

export const validateIndicatorParameters = (
  name: string, 
  parameters: Record<string, any>
): { valid: boolean; errors: string[] } => {
  const config = getIndicatorConfig(name);
  if (!config) {
    return { valid: false, errors: ['Unknown indicator'] };
  }

  const errors: string[] = [];

  config.parameterDefinitions.forEach(paramDef => {
    const value = parameters[paramDef.name];
    
    if (value === undefined || value === null) {
      errors.push(`Parameter '${paramDef.label || paramDef.name}' is required`);
      return;
    }

    if (paramDef.type === 'number') {
      const num = Number(value);
      if (isNaN(num)) {
        errors.push(`Parameter '${paramDef.label || paramDef.name}' must be a number`);
      } else {
        if (paramDef.min !== undefined && num < paramDef.min) {
          errors.push(`Parameter '${paramDef.label || paramDef.name}' must be at least ${paramDef.min}`);
        }
        if (paramDef.max !== undefined && num > paramDef.max) {
          errors.push(`Parameter '${paramDef.label || paramDef.name}' must be at most ${paramDef.max}`);
        }
      }
    }

    if (paramDef.type === 'select' && paramDef.options) {
      if (!paramDef.options.includes(value)) {
        errors.push(`Parameter '${paramDef.label || paramDef.name}' must be one of: ${paramDef.options.join(', ')}`);
      }
    }
  });

  return { valid: errors.length === 0, errors };
};

// Generate a unique ID for indicator instances
export const generateIndicatorId = (name: string): string => {
  return `${name}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Generate scaling configuration for fuzzy overlays based on indicator registry
export const getIndicatorFuzzyScaling = (
  indicatorName: string,
  oscillatorData?: { indicators: Array<{ id: string; data: Array<{ value: number }> }> },
  indicatorId?: string
): { minValue: number; maxValue: number; indicatorType: 'rsi' | 'macd' | 'other' } | undefined => {
  const config = getIndicatorConfig(indicatorName);
  
  if (!config?.fuzzySupport?.enabled) {
    return undefined;
  }
  
  // Fixed scaling (e.g., RSI 0-100)
  if (config.fuzzySupport.scalingType === 'fixed' && config.fuzzySupport.defaultRange) {
    return {
      minValue: config.fuzzySupport.defaultRange.min,
      maxValue: config.fuzzySupport.defaultRange.max,
      indicatorType: indicatorName as 'rsi' | 'macd' | 'other'
    };
  }
  
  // Dynamic scaling (e.g., MACD calculated from data)
  if (config.fuzzySupport.scalingType === 'dynamic' && oscillatorData && indicatorId) {
    // Find the relevant series data for this indicator
    const indicatorSeries = oscillatorData.indicators.find(series => 
      series.id.includes(indicatorId) && series.id.includes(indicatorName)
    );
    
    if (!indicatorSeries || !indicatorSeries.data.length) {
      return undefined;
    }
    
    // Calculate dynamic range from actual data
    const values = indicatorSeries.data.map(point => point.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    
    // Add padding for better visualization
    const padding = (maxValue - minValue) * 0.1;
    
    return {
      minValue: minValue - padding,
      maxValue: maxValue + padding,
      indicatorType: indicatorName as 'rsi' | 'macd' | 'other'
    };
  }
  
  return undefined;
};