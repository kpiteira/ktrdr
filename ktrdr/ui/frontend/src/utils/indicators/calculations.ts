// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/utils/indicators/calculations.ts
import { OHLCVData, IndicatorData } from '../../types/data';

/**
 * Technical indicator calculation utilities
 */

/**
 * Get the appropriate price value based on price type
 * 
 * @param candle OHLCV data point
 * @param priceType Type of price to use
 * @returns Price value
 */
export function getPrice(candle: number[], priceType: string): number {
  switch (priceType) {
    case 'open':
      return candle[0];
    case 'high':
      return candle[1];
    case 'low':
      return candle[2];
    case 'typical':
      return (candle[1] + candle[2] + candle[3]) / 3;
    case 'close':
    default:
      return candle[3];
  }
}

/**
 * Calculate Simple Moving Average (SMA)
 * 
 * @param data Array of price data points
 * @param period Number of periods to average
 * @returns Array of SMA values
 */
export function calculateSMA(
  data: number[],
  period: number
): number[] {
  const result: number[] = [];
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(NaN); // Not enough data for a complete average
      continue;
    }
    
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j];
    }
    
    result.push(sum / period);
  }
  
  return result;
}

/**
 * Calculate Exponential Moving Average (EMA)
 * 
 * @param data Array of price data points
 * @param period Number of periods for EMA
 * @returns Array of EMA values
 */
export function calculateEMA(
  data: number[],
  period: number
): number[] {
  const result: number[] = [];
  const k = 2 / (period + 1); // Smoothing factor
  
  // First value is SMA
  let ema = 0;
  let validDataPoints = 0;
  
  for (let i = 0; i < period && i < data.length; i++) {
    if (!isNaN(data[i])) {
      ema += data[i];
      validDataPoints++;
    }
  }
  
  // Fill with NaNs until we have enough data
  for (let i = 0; i < period - 1; i++) {
    result.push(NaN);
  }
  
  if (validDataPoints > 0) {
    ema /= validDataPoints;
  } else {
    ema = NaN;
  }
  
  result.push(ema);
  
  // Calculate EMA for remaining data points
  for (let i = period; i < data.length; i++) {
    const price = data[i];
    ema = price * k + ema * (1 - k);
    result.push(ema);
  }
  
  return result;
}

/**
 * Calculate Relative Strength Index (RSI)
 * 
 * @param data Input price data
 * @param period Period for calculation
 * @returns Array of RSI values, NaN for the first (period) values
 */
export function calculateRSI(data: number[], period: number): number[] {
  const result: number[] = Array(data.length).fill(NaN);
  const gains: number[] = [0];
  const losses: number[] = [0];
  
  // Calculate gains and losses
  for (let i = 1; i < data.length; i++) {
    const difference = data[i] - data[i - 1];
    gains.push(difference > 0 ? difference : 0);
    losses.push(difference < 0 ? Math.abs(difference) : 0);
  }
  
  // Calculate average gains and losses
  let avgGain = 0;
  let avgLoss = 0;
  
  // First average
  for (let i = 1; i <= period && i < gains.length; i++) {
    avgGain += gains[i];
    avgLoss += losses[i];
  }
  
  avgGain /= period;
  avgLoss /= period;
  
  // Calculate RS and RSI
  let rs = avgGain / (avgLoss === 0 ? 0.001 : avgLoss); // Avoid division by zero
  result[period] = 100 - (100 / (1 + rs));
  
  // Calculate remaining RSI values
  for (let i = period + 1; i < data.length; i++) {
    avgGain = ((avgGain * (period - 1)) + gains[i]) / period;
    avgLoss = ((avgLoss * (period - 1)) + losses[i]) / period;
    
    rs = avgGain / (avgLoss === 0 ? 0.001 : avgLoss); // Avoid division by zero
    result[i] = 100 - (100 / (1 + rs));
  }
  
  return result;
}

/**
 * Calculate Moving Average Convergence Divergence (MACD)
 * 
 * @param data Input price data
 * @param fastPeriod Fast period for MACD
 * @param slowPeriod Slow period for MACD
 * @param signalPeriod Signal period for MACD
 * @returns Object with MACD, signal, and histogram values
 */
export function calculateMACD(
  data: number[], 
  fastPeriod: number, 
  slowPeriod: number, 
  signalPeriod: number
): { 
  macd: number[]; 
  signal: number[]; 
  histogram: number[] 
} {
  // Calculate EMA values
  const fastEMA = calculateEMA(data, fastPeriod);
  const slowEMA = calculateEMA(data, slowPeriod);
  
  // Calculate MACD line
  const macdLine: number[] = Array(data.length).fill(NaN);
  for (let i = Math.max(fastPeriod, slowPeriod) - 1; i < data.length; i++) {
    if (!isNaN(fastEMA[i]) && !isNaN(slowEMA[i])) {
      macdLine[i] = fastEMA[i] - slowEMA[i];
    }
  }
  
  // Filter out NaN values for signal calculation
  const macdValues: number[] = [];
  const macdIndices: number[] = [];
  
  for (let i = 0; i < macdLine.length; i++) {
    if (!isNaN(macdLine[i])) {
      macdValues.push(macdLine[i]);
      macdIndices.push(i);
    }
  }
  
  // Calculate signal line
  const signal: number[] = Array(data.length).fill(NaN);
  
  if (macdValues.length >= signalPeriod) {
    const signalEMA = calculateEMA(macdValues, signalPeriod);
    
    // Map the signal values back to the original indices
    for (let i = 0; i < signalEMA.length; i++) {
      if (!isNaN(signalEMA[i]) && i + signalPeriod - 1 < macdIndices.length) {
        const originalIndex = macdIndices[i + signalPeriod - 1];
        signal[originalIndex] = signalEMA[i];
      }
    }
  }
  
  // Calculate histogram
  const histogram: number[] = Array(data.length).fill(NaN);
  for (let i = 0; i < data.length; i++) {
    if (!isNaN(macdLine[i]) && !isNaN(signal[i])) {
      histogram[i] = macdLine[i] - signal[i];
    }
  }
  
  return { macd: macdLine, signal, histogram };
}

/**
 * Calculate Average True Range (ATR)
 * 
 * @param ohlcv OHLCV data
 * @param period Period for calculation
 * @returns Array of ATR values, NaN for the first (period) values
 */
export function calculateATR(ohlcv: OHLCVData, period: number): number[] {
  const result: number[] = Array(ohlcv.ohlcv.length).fill(NaN);
  const trueRanges: number[] = [];
  
  // Calculate true ranges
  for (let i = 0; i < ohlcv.ohlcv.length; i++) {
    const [_, high, low] = ohlcv.ohlcv[i]; // Use underscore to ignore unused variables
    
    if (i === 0) {
      trueRanges.push(high - low); // First TR is simply the range
    } else {
      const prevClose = ohlcv.ohlcv[i - 1][3];
      const tr1 = high - low; // Current high - current low
      const tr2 = Math.abs(high - prevClose); // Current high - previous close
      const tr3 = Math.abs(low - prevClose); // Current low - previous close
      
      trueRanges.push(Math.max(tr1, tr2, tr3));
    }
  }
  
  // Calculate first ATR
  let sum = 0;
  for (let i = 0; i < period && i < trueRanges.length; i++) {
    sum += trueRanges[i];
  }
  result[period - 1] = sum / period;
  
  // Calculate remaining ATR values using smoothing
  for (let i = period; i < ohlcv.ohlcv.length; i++) {
    result[i] = ((result[i - 1] || 0) * (period - 1) + trueRanges[i]) / period;
  }
  
  return result;
}

/**
 * Calculate Stochastic Oscillator
 * 
 * @param ohlcv OHLCV data
 * @param period Period for calculation
 * @param smoothK Smooth K period
 * @param smoothD Smooth D period
 * @returns Object with K and D values
 */
export function calculateStochastic(
  ohlcv: OHLCVData, 
  period: number,
  smoothK: number,
  smoothD: number
): { k: number[]; d: number[] } {
  const high = extractPriceData(ohlcv, 'high');
  const low = extractPriceData(ohlcv, 'low');
  const close = extractPriceData(ohlcv, 'close');
  
  const rawK: number[] = Array(ohlcv.ohlcv.length).fill(NaN);
  
  // Calculate raw %K
  for (let i = period - 1; i < ohlcv.ohlcv.length; i++) {
    let highestHigh = -Infinity;
    let lowestLow = Infinity;
    
    for (let j = 0; j < period; j++) {
      highestHigh = Math.max(highestHigh, high[i - j]);
      lowestLow = Math.min(lowestLow, low[i - j]);
    }
    
    if (highestHigh === lowestLow) {
      rawK[i] = 50; // If there's no range, default to 50
    } else {
      rawK[i] = 100 * ((close[i] - lowestLow) / (highestHigh - lowestLow));
    }
  }
  
  // Apply smoothing to %K
  let k: number[] = rawK;
  
  if (smoothK > 1) {
    // Extract valid values for SMA calculation
    const validK: number[] = [];
    const validIndices: number[] = [];
    
    for (let i = 0; i < rawK.length; i++) {
      if (!isNaN(rawK[i])) {
        validK.push(rawK[i]);
        validIndices.push(i);
      }
    }
    
    // Calculate SMA for smoothing
    const smoothedK = calculateSMA(validK, smoothK);
    k = Array(ohlcv.ohlcv.length).fill(NaN);
    
    // Map smoothed values back to original indices
    for (let i = 0; i < smoothedK.length; i++) {
      if (!isNaN(smoothedK[i]) && i + smoothK - 1 < validIndices.length) {
        const originalIndex = validIndices[i + smoothK - 1];
        k[originalIndex] = smoothedK[i];
      }
    }
  }
  
  // Calculate %D (SMA of %K)
  let d: number[] = Array(ohlcv.ohlcv.length).fill(NaN);
  
  // Extract valid values for D calculation
  const validK: number[] = [];
  const validIndices: number[] = [];
  
  for (let i = 0; i < k.length; i++) {
    if (!isNaN(k[i])) {
      validK.push(k[i]);
      validIndices.push(i);
    }
  }
  
  // Calculate SMA for %D
  const smoothedD = calculateSMA(validK, smoothD);
  
  // Map smoothed values back to original indices
  for (let i = 0; i < smoothedD.length; i++) {
    if (!isNaN(smoothedD[i]) && i + smoothD - 1 < validIndices.length) {
      const originalIndex = validIndices[i + smoothD - 1];
      d[originalIndex] = smoothedD[i];
    }
  }
  
  return { k, d };
}

/**
 * Calculate Bollinger Bands
 * 
 * @param data Input price data
 * @param period Period for the calculation (typically 20)
 * @param stdDev Number of standard deviations (typically 2)
 * @returns Object with upper, middle, and lower band values
 */
export function calculateBollingerBands(
  data: number[],
  period: number,
  stdDev: number
): { 
  upper: number[]; 
  middle: number[]; 
  lower: number[] 
} {
  const middle = calculateSMA(data, period);
  const upper: number[] = Array(data.length).fill(NaN);
  const lower: number[] = Array(data.length).fill(NaN);
  
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      const deviation = data[i - j] - middle[i];
      sum += deviation * deviation;
    }
    
    const standardDeviation = Math.sqrt(sum / period);
    upper[i] = middle[i] + (standardDeviation * stdDev);
    lower[i] = middle[i] - (standardDeviation * stdDev);
  }
  
  return { upper, middle, lower };
}

/**
 * Extract price data from OHLCV data based on price type
 * 
 * @param data OHLCV data
 * @param priceType Type of price to extract
 * @returns Array of price values
 */
export function extractPriceData(data: OHLCVData, priceType: string = 'close'): number[] {
  if (!data || !data.ohlcv || !data.dates || data.ohlcv.length === 0) {
    console.error('Invalid or empty OHLCV data');
    return [];
  }
  
  return data.ohlcv.map(candle => {
    const [open, high, low, close] = candle;
    
    switch (priceType) {
      case 'open':
        return open;
      case 'high':
        return high;
      case 'low':
        return low;
      case 'typical':
        return (high + low + close) / 3;
      case 'close':
      default:
        return close;
    }
  });
}

/**
 * Create indicator data based on specified type and parameters
 * 
 * @param data OHLCV data
 * @param indicatorId Indicator ID from registry
 * @param parameters Indicator parameters
 * @returns Indicator data formatted for visualization
 */
export function createIndicatorData(
  data: OHLCVData, 
  indicatorId: string, 
  parameters: Record<string, any>
): IndicatorData {
  // Extract price data
  const priceType = parameters.priceType || 'close';
  const priceData = extractPriceData(data, priceType);
  
  let values: number[][] = [];
  let metadata: any = {};
  
  // Extract parameters
  const period = parameters.period || 14;
  const deviations = parameters.deviations || 2;
  const fastPeriod = parameters.fastPeriod || 12;
  const slowPeriod = parameters.slowPeriod || 26;
  const signalPeriod = parameters.signalPeriod || 9;
  const smoothK = parameters.smoothK || 1;
  const smoothD = parameters.smoothD || 3;
  
  // Calculate based on indicator type
  switch (indicatorId) {
    case 'sma': {
      const smaValues = calculateSMA(priceData, period);
      values = [smaValues];
      metadata = {
        name: `SMA(${period})`,
      };
      break;
    }
    
    case 'ema': {
      const emaValues = calculateEMA(priceData, period);
      values = [emaValues];
      metadata = {
        name: `EMA(${period})`,
      };
      break;
    }
    
    case 'bbands': {
      const { upper, middle, lower } = calculateBollingerBands(priceData, period, deviations);
      values = [upper, middle, lower];
      metadata = {
        names: [`Upper Band`, `SMA(${period})`, `Lower Band`],
      };
      break;
    }
    
    case 'rsi': {
      const rsiValues = calculateRSI(priceData, period);
      values = [rsiValues];
      metadata = {
        name: `RSI(${period})`,
        valueRange: {
          min: 0,
          max: 100,
          markers: [
            { value: 70, label: 'Overbought' },
            { value: 30, label: 'Oversold' }
          ]
        }
      };
      break;
    }
    
    case 'macd': {
      const { macd, signal, histogram } = calculateMACD(
        priceData, 
        fastPeriod, 
        slowPeriod, 
        signalPeriod
      );
      values = [macd, signal, histogram];
      metadata = {
        type: 'multi-line-histogram',
        names: [`MACD(${fastPeriod},${slowPeriod})`, `Signal(${signalPeriod})`, 'Histogram'],
        histogramIndex: 2
      };
      break;
    }
    
    case 'atr': {
      const atrValues = calculateATR(data, period);
      values = [atrValues];
      metadata = {
        name: `ATR(${period})`,
      };
      break;
    }
    
    case 'stoch': {
      const { k, d } = calculateStochastic(data, period, smoothK, smoothD);
      values = [k, d];
      metadata = {
        names: [`%K(${period},${smoothK})`, `%D(${smoothD})`],
        valueRange: {
          min: 0,
          max: 100,
          markers: [
            { value: 80, label: 'Overbought' },
            { value: 20, label: 'Oversold' }
          ]
        }
      };
      break;
    }
    
    default:
      console.error(`Unsupported indicator type: ${indicatorId}`);
  }
  
  return {
    indicatorId,
    values,
    dates: data.dates,
    metadata
  };
}