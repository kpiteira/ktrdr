/**
 * Centralized Indicator Registry System
 * 
 * This registry eliminates hardcoded indicator logic and provides a 
 * configuration-driven approach for managing indicators.
 */

export interface ParameterDefinition {
  name: string;
  type: 'number' | 'string' | 'boolean' | 'select';
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
        type: 'select', 
        options: ['#2196F3', '#FF5722', '#4CAF50', '#9C27B0', '#FF9800'], 
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
        type: 'select', 
        options: ['#FF5722', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800'], 
        default: '#FF5722',
        label: 'Color',
        description: 'Line color for the indicator'
      }
    ],
    colorOptions: ['#FF5722', '#2196F3', '#4CAF50', '#9C27B0', '#FF9800']
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
    chartType: config.chartType
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