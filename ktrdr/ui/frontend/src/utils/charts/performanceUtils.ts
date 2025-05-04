/**
 * Performance optimization utilities for charts
 */
import { OHLCVData } from '../../types/data';
import { ChartData } from '../../types/charts';

/**
 * Downsamples OHLCV data to improve rendering performance for large datasets
 * @param data Original OHLCV data
 * @param targetPoints Target number of data points
 * @returns Downsampled OHLCV data
 */
export const downsampleOHLCVData = (
  data: OHLCVData,
  targetPoints: number = 500
): OHLCVData => {
  if (!data || !data.dates || !data.ohlcv) {
    return data;
  }

  const totalPoints = data.dates.length;
  
  // If data is already under the target, return it as is
  if (totalPoints <= targetPoints) {
    return data;
  }

  // Calculate sampling rate
  const samplingRate = Math.ceil(totalPoints / targetPoints);
  
  // Sample the data
  const sampledDates: string[] = [];
  const sampledOHLCV: number[][] = [];
  
  for (let i = 0; i < totalPoints; i += samplingRate) {
    sampledDates.push(data.dates[i]);
    sampledOHLCV.push(data.ohlcv[i]);
  }
  
  // Ensure the last point is included
  if (sampledDates[sampledDates.length - 1] !== data.dates[totalPoints - 1]) {
    sampledDates.push(data.dates[totalPoints - 1]);
    sampledOHLCV.push(data.ohlcv[totalPoints - 1]);
  }
  
  return {
    dates: sampledDates,
    ohlcv: sampledOHLCV,
    metadata: {
      ...data.metadata,
      points: sampledDates.length,
    },
  };
};

/**
 * Determines if data should be downsampled based on visible range
 * @param visibleRange Visible range on the chart
 * @param totalPoints Total number of data points
 * @returns Whether data should be downsampled
 */
export const shouldDownsample = (
  visibleRange: { from: number; to: number } | null,
  totalPoints: number
): boolean => {
  if (!visibleRange) {
    return totalPoints > 500;
  }
  
  const visiblePoints = visibleRange.to - visibleRange.from;
  const pointDensity = totalPoints / visiblePoints;
  
  // Downsample if density is more than 3 points per visible point
  return pointDensity > 3;
};

/**
 * Throttles a function to limit how often it can be called
 * @param fn Function to throttle
 * @param delay Minimum delay between calls in milliseconds
 * @returns Throttled function
 */
export const throttle = <T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let lastCall = 0;
  let timeoutId: number | null = null;
  
  return (...args: Parameters<T>) => {
    const now = Date.now();
    const timeSinceLastCall = now - lastCall;
    
    if (timeSinceLastCall >= delay) {
      lastCall = now;
      fn(...args);
    } else if (!timeoutId) {
      timeoutId = window.setTimeout(() => {
        lastCall = Date.now();
        timeoutId = null;
        fn(...args);
      }, delay - timeSinceLastCall);
    }
  };
};

/**
 * Debounces a function to delay its execution until after a specified delay
 * @param fn Function to debounce
 * @param delay Delay in milliseconds
 * @returns Debounced function
 */
export const debounce = <T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: number | null = null;
  
  return (...args: Parameters<T>) => {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    
    timeoutId = window.setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  };
};

/**
 * Incrementally loads large datasets to improve initial rendering performance
 * @param data Full OHLCV data
 * @param initialCount Initial number of points to load
 * @param batchSize Size of each subsequent batch
 * @param onBatchReady Callback when a batch is ready
 * @param onComplete Callback when all data is loaded
 */
export const incrementalDataLoader = (
  data: OHLCVData,
  initialCount: number,
  batchSize: number,
  onBatchReady: (batchData: OHLCVData) => void,
  onComplete: () => void
): void => {
  if (!data || !data.dates || !data.ohlcv) {
    onComplete();
    return;
  }
  
  const totalPoints = data.dates.length;
  
  // If data is small enough, load it all at once
  if (totalPoints <= initialCount) {
    onBatchReady(data);
    onComplete();
    return;
  }
  
  // Load initial batch
  const initialBatch: OHLCVData = {
    dates: data.dates.slice(0, initialCount),
    ohlcv: data.ohlcv.slice(0, initialCount),
    metadata: {
      ...data.metadata,
      points: initialCount,
    },
  };
  
  onBatchReady(initialBatch);
  
  // Load remaining batches incrementally
  let loadedCount = initialCount;
  
  const loadNextBatch = () => {
    if (loadedCount >= totalPoints) {
      onComplete();
      return;
    }
    
    const nextBatchSize = Math.min(batchSize, totalPoints - loadedCount);
    const nextBatch: OHLCVData = {
      dates: data.dates.slice(0, loadedCount + nextBatchSize),
      ohlcv: data.ohlcv.slice(0, loadedCount + nextBatchSize),
      metadata: {
        ...data.metadata,
        points: loadedCount + nextBatchSize,
      },
    };
    
    onBatchReady(nextBatch);
    loadedCount += nextBatchSize;
    
    // Schedule next batch with requestAnimationFrame for better user experience
    if (loadedCount < totalPoints) {
      requestAnimationFrame(loadNextBatch);
    } else {
      onComplete();
    }
  };
  
  // Start loading remaining batches after a short delay
  setTimeout(loadNextBatch, 100);
};