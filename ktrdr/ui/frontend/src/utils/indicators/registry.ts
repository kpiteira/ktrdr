// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/utils/indicators/registry.ts
import { v4 as uuidv4 } from 'uuid';
import { 
  IndicatorConfig, 
  IndicatorMetadata, 
  IndicatorRegistryItem 
} from '../../types/data';

/**
 * Registry of available indicators with metadata and default configurations
 */

/**
 * Simple Moving Average (SMA) indicator metadata
 */
export const SMA_METADATA: IndicatorMetadata = {
  id: 'sma',
  name: 'Simple Moving Average',
  description: 'Average price over a specific number of periods.',
  type: 'overlay',
  parameters: [
    {
      name: 'period',
      label: 'Period',
      type: 'number',
      default: 20,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'priceType',
      label: 'Price Type',
      type: 'select',
      default: 'close',
      options: [
        { label: 'Close', value: 'close' },
        { label: 'Open', value: 'open' },
        { label: 'High', value: 'high' },
        { label: 'Low', value: 'low' },
        { label: 'Typical (HLC/3)', value: 'typical' }
      ]
    }
  ]
};

/**
 * Exponential Moving Average (EMA) indicator metadata
 */
export const EMA_METADATA: IndicatorMetadata = {
  id: 'ema',
  name: 'Exponential Moving Average',
  description: 'Moving average that gives more weight to recent prices.',
  type: 'overlay',
  parameters: [
    {
      name: 'period',
      label: 'Period',
      type: 'number',
      default: 20,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'priceType',
      label: 'Price Type',
      type: 'select',
      default: 'close',
      options: [
        { label: 'Close', value: 'close' },
        { label: 'Open', value: 'open' },
        { label: 'High', value: 'high' },
        { label: 'Low', value: 'low' },
        { label: 'Typical (HLC/3)', value: 'typical' }
      ]
    }
  ]
};

/**
 * Bollinger Bands indicator metadata
 */
export const BBANDS_METADATA: IndicatorMetadata = {
  id: 'bbands',
  name: 'Bollinger Bands',
  description: 'Volatility bands placed above and below a moving average.',
  type: 'overlay',
  parameters: [
    {
      name: 'period',
      label: 'Period',
      type: 'number',
      default: 20,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'deviations',
      label: 'Standard Deviations',
      type: 'number',
      default: 2,
      min: 0.5,
      max: 10,
      step: 0.1
    },
    {
      name: 'priceType',
      label: 'Price Type',
      type: 'select',
      default: 'close',
      options: [
        { label: 'Close', value: 'close' },
        { label: 'Open', value: 'open' },
        { label: 'High', value: 'high' },
        { label: 'Low', value: 'low' },
        { label: 'Typical (HLC/3)', value: 'typical' }
      ]
    }
  ],
  metadata: {
    type: 'multi-line',
    names: ['Upper Band', 'Middle Band', 'Lower Band']
  }
};

/**
 * Relative Strength Index (RSI) indicator metadata
 */
export const RSI_METADATA: IndicatorMetadata = {
  id: 'rsi',
  name: 'Relative Strength Index',
  description: 'Momentum oscillator that measures the speed and change of price movements.',
  type: 'panel',
  parameters: [
    {
      name: 'period',
      label: 'Period',
      type: 'number',
      default: 14,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'priceType',
      label: 'Price Type',
      type: 'select',
      default: 'close',
      options: [
        { label: 'Close', value: 'close' },
        { label: 'Open', value: 'open' },
        { label: 'High', value: 'high' },
        { label: 'Low', value: 'low' },
        { label: 'Typical (HLC/3)', value: 'typical' }
      ]
    },
    {
      name: 'showOverbought',
      label: 'Show Overbought/Oversold',
      type: 'checkbox',
      default: true
    }
  ],
  metadata: {
    valueRange: {
      min: 0,
      max: 100,
      markers: [
        { value: 70, label: 'Overbought' },
        { value: 30, label: 'Oversold' }
      ]
    }
  }
};

/**
 * Moving Average Convergence Divergence (MACD) indicator metadata
 */
export const MACD_METADATA: IndicatorMetadata = {
  id: 'macd',
  name: 'MACD',
  description: 'Trend-following momentum indicator showing the relationship between two moving averages.',
  type: 'panel',
  parameters: [
    {
      name: 'fastPeriod',
      label: 'Fast Period',
      type: 'number',
      default: 12,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'slowPeriod',
      label: 'Slow Period',
      type: 'number',
      default: 26,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'signalPeriod',
      label: 'Signal Period',
      type: 'number',
      default: 9,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'priceType',
      label: 'Price Type',
      type: 'select',
      default: 'close',
      options: [
        { label: 'Close', value: 'close' },
        { label: 'Open', value: 'open' },
        { label: 'High', value: 'high' },
        { label: 'Low', value: 'low' },
        { label: 'Typical (HLC/3)', value: 'typical' }
      ]
    }
  ],
  metadata: {
    type: 'multi-line-histogram',
    names: ['MACD', 'Signal', 'Histogram'],
    histogramIndex: 2
  }
};

/**
 * Average True Range (ATR) indicator metadata
 */
export const ATR_METADATA: IndicatorMetadata = {
  id: 'atr',
  name: 'Average True Range',
  description: 'Measures market volatility by decomposing the entire range of an asset price for a period.',
  type: 'panel',
  parameters: [
    {
      name: 'period',
      label: 'Period',
      type: 'number',
      default: 14,
      min: 2,
      max: 500,
      step: 1
    }
  ]
};

/**
 * Stochastic Oscillator indicator metadata
 */
export const STOCH_METADATA: IndicatorMetadata = {
  id: 'stoch',
  name: 'Stochastic Oscillator',
  description: 'Momentum indicator comparing closing price to price range over time.',
  type: 'panel',
  parameters: [
    {
      name: 'period',
      label: '%K Period',
      type: 'number',
      default: 14,
      min: 2,
      max: 500,
      step: 1
    },
    {
      name: 'smoothK',
      label: '%K Smoothing',
      type: 'number',
      default: 1,
      min: 1,
      max: 10,
      step: 1
    },
    {
      name: 'smoothD',
      label: '%D Period',
      type: 'number',
      default: 3,
      min: 1,
      max: 10,
      step: 1
    },
    {
      name: 'showOverbought',
      label: 'Show Overbought/Oversold',
      type: 'checkbox',
      default: true
    }
  ],
  metadata: {
    type: 'multi-line',
    names: ['%K', '%D'],
    valueRange: {
      min: 0,
      max: 100,
      markers: [
        { value: 80, label: 'Overbought' },
        { value: 20, label: 'Oversold' }
      ]
    }
  }
};

/**
 * Complete registry of all available indicators
 */
export const INDICATORS_REGISTRY: Record<string, IndicatorRegistryItem> = {
  sma: {
    metadata: SMA_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'sma',
      visible: true,
      parameters: {
        period: 20,
        priceType: 'close'
      },
      colors: ['#2196F3'],
      lineWidths: [2],
      lineStyles: ['0']
    })
  },
  ema: {
    metadata: EMA_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'ema',
      visible: true,
      parameters: {
        period: 20,
        priceType: 'close'
      },
      colors: ['#FF9800'],
      lineWidths: [2],
      lineStyles: ['0']
    })
  },
  bbands: {
    metadata: BBANDS_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'bbands',
      visible: true,
      parameters: {
        period: 20,
        deviations: 2,
        priceType: 'close'
      },
      colors: ['#F44336', '#2196F3', '#F44336'],
      lineWidths: [2, 2, 2],
      lineStyles: ['0', '0', '0']
    })
  },
  rsi: {
    metadata: RSI_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'rsi',
      visible: true,
      parameters: {
        period: 14,
        priceType: 'close',
        showOverbought: true
      },
      colors: ['#2196F3'],
      lineWidths: [2],
      lineStyles: ['0']
    })
  },
  macd: {
    metadata: MACD_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'macd',
      visible: true,
      parameters: {
        fastPeriod: 12,
        slowPeriod: 26,
        signalPeriod: 9,
        priceType: 'close'
      },
      colors: ['#2196F3', '#FF9800', '#4CAF50'],
      lineWidths: [2, 2, 1],
      lineStyles: ['0', '0', '0']
    })
  },
  atr: {
    metadata: ATR_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'atr',
      visible: true,
      parameters: {
        period: 14
      },
      colors: ['#9C27B0'],
      lineWidths: [2],
      lineStyles: ['0']
    })
  },
  stoch: {
    metadata: STOCH_METADATA,
    createDefaultConfig: () => ({
      id: uuidv4(),
      indicatorId: 'stoch',
      visible: true,
      parameters: {
        period: 14,
        smoothK: 1,
        smoothD: 3,
        showOverbought: true
      },
      colors: ['#2196F3', '#FF9800'],
      lineWidths: [2, 2],
      lineStyles: ['0', '0']
    })
  }
};

/**
 * Get metadata for a specific indicator
 * 
 * @param indicatorId Identifier of the indicator
 * @returns Indicator metadata or undefined if not found
 */
export function getIndicatorMetadata(indicatorId: string): IndicatorMetadata | undefined {
  return INDICATORS_REGISTRY[indicatorId]?.metadata;
}

/**
 * Create default configuration for a specific indicator
 * 
 * @param indicatorId Identifier of the indicator
 * @returns Default indicator configuration or undefined if not found
 */
export function createDefaultIndicatorConfig(indicatorId: string): IndicatorConfig | undefined {
  return INDICATORS_REGISTRY[indicatorId]?.createDefaultConfig();
}

/**
 * Get all available indicators by type
 * 
 * @param type Optional type filter ('overlay' or 'panel')
 * @returns Array of indicator metadata objects
 */
export function getAvailableIndicators(type?: string): IndicatorMetadata[] {
  return Object.values(INDICATORS_REGISTRY)
    .filter(item => !type || item.metadata.type === type)
    .map(item => item.metadata);
}