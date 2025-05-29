import { useRef, useCallback } from 'react';
import { IChartApi } from 'lightweight-charts';
import { createLogger } from '../utils/logger';

/**
 * Custom hook for synchronizing multiple charts
 * 
 * Provides utilities for synchronizing time scale, crosshair position,
 * and zoom/pan operations across multiple TradingView charts.
 */

const logger = createLogger('ChartSynchronizer');

export interface ChartReference {
  id: string;
  chart: IChartApi;
  name?: string;
}

export interface UseChartSynchronizerReturn {
  registerChart: (id: string, chart: IChartApi, name?: string) => void;
  unregisterChart: (id: string) => void;
  synchronizeTimeScale: (sourceChartId: string) => void;
  synchronizeCrosshair: (sourceChartId: string, point: any) => void;
  fitAllChartsContent: () => void;
  setAllChartsVisibleRange: (from: number, to: number) => void;
  getRegisteredCharts: () => ChartReference[];
  syncAllToChart: (sourceChartId: string) => void;
}

export const useChartSynchronizer = (): UseChartSynchronizerReturn => {
  const chartsRef = useRef<Map<string, ChartReference>>(new Map());
  const syncInProgressRef = useRef<boolean>(false);

  // Register a chart for synchronization
  const registerChart = useCallback((id: string, chart: IChartApi, name?: string) => {
    const chartRef: ChartReference = { id, chart, name };
    chartsRef.current.set(id, chartRef);

    // Set up time scale synchronization only (no crosshair sync)
    let timeoutId: number | null = null;
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
      if (!syncInProgressRef.current) {
        try {
          // Only sync if we have more than one chart registered
          const registeredCharts = chartsRef.current.size;
          if (registeredCharts > 1) {
            // Debounce rapid changes to prevent loops
            if (timeoutId) clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
              synchronizeTimeScale(id);
            }, 100); // Quick sync for responsive feel
          }
        } catch (error) {
          logger.error('Error in time range change listener:', error);
        }
      }
    });
  }, []);

  // Unregister a chart
  const unregisterChart = useCallback((id: string) => {
    chartsRef.current.delete(id);
  }, []);

  // Synchronize time scale across all charts
  // Not wrapped in useCallback since it only depends on refs
  const synchronizeTimeScale = (sourceChartId: string) => {
    const sourceChart = chartsRef.current.get(sourceChartId);
    if (!sourceChart) {
      return;
    }

    // Set flag to prevent infinite sync loops first
    syncInProgressRef.current = true;

    try {
      const sourceTimeScale = sourceChart.chart.timeScale();
      let visibleRange;
      
      // Safely get visible range with error handling
      try {
        visibleRange = sourceTimeScale.getVisibleRange();
      } catch (rangeError) {
        logger.debug('Could not get visible range:', rangeError);
        return;
      }
      
      // Defensive check - if no visible range, skip sync
      if (!visibleRange || !visibleRange.from || !visibleRange.to) {
        return;
      }

      // Validate range values - skip if invalid
      if (isNaN(visibleRange.from) || isNaN(visibleRange.to) || visibleRange.from >= visibleRange.to) {
        return;
      }

      // Additional safety: check if range is reasonable (not too far in the future)
      const now = Date.now() / 1000; // Current time in seconds
      const maxFutureTime = now + (365 * 24 * 60 * 60); // 1 year from now
      if (visibleRange.to > maxFutureTime) {
        // Don't sync ranges that are too far in the future
        return;
      }

      // Only log when we have multiple charts to sync
      const targetCharts = Array.from(chartsRef.current.entries()).filter(([id]) => id !== sourceChartId);
      if (targetCharts.length === 0) {
        return;
      }

      targetCharts.forEach(([chartId, chartRef]) => {
        try {
          const targetTimeScale = chartRef.chart.timeScale();
          // Additional safety check before setting range
          if (targetTimeScale && typeof targetTimeScale.setVisibleRange === 'function') {
            targetTimeScale.setVisibleRange(visibleRange);
          }
        } catch (error) {
          logger.error(`Sync failed for: ${chartId}`, error);
        }
      });
    } catch (error) {
      logger.error('Error during sync operation:', error);
    } finally {
      // Reset flag after sync operations complete
      setTimeout(() => {
        syncInProgressRef.current = false;
      }, 150);
    }
  };

  // Crosshair synchronization disabled for simplicity
  const synchronizeCrosshair = useCallback((_sourceChartId: string, _point: any) => {
    // Crosshair sync disabled - only time scale sync is active
  }, []);

  // Fit content for all charts
  const fitAllChartsContent = useCallback(() => {
    chartsRef.current.forEach((chartRef) => {
      try {
        chartRef.chart.timeScale().fitContent();
      } catch (error) {
        logger.error('Error fitting content:', error);
      }
    });
  }, []);

  // Set visible range for all charts
  const setAllChartsVisibleRange = useCallback((from: number, to: number) => {
    syncInProgressRef.current = true;

    try {
      chartsRef.current.forEach((chartRef) => {
        try {
          chartRef.chart.timeScale().setVisibleRange({ from, to });
        } catch (error) {
          logger.error('Error setting visible range:', error);
        }
      });
    } finally {
      setTimeout(() => {
        syncInProgressRef.current = false;
      }, 200);
    }
  }, []);

  // Get all registered charts (for debugging/inspection)
  const getRegisteredCharts = useCallback((): ChartReference[] => {
    return Array.from(chartsRef.current.values());
  }, []);

  // Manual sync method to force sync all charts to a specific chart's time range
  const syncAllToChart = useCallback((sourceChartId: string) => {
    // Temporarily disable the sync flag to allow manual sync
    const wasSyncing = syncInProgressRef.current;
    syncInProgressRef.current = false;
    synchronizeTimeScale(sourceChartId);
    syncInProgressRef.current = wasSyncing;
  }, [synchronizeTimeScale]);

  return {
    registerChart,
    unregisterChart,
    synchronizeTimeScale,
    synchronizeCrosshair,
    fitAllChartsContent,
    setAllChartsVisibleRange,
    getRegisteredCharts,
    syncAllToChart
  };
};

/**
 * Simplified hook for basic chart synchronization
 * 
 * This hook provides a simpler interface for the most common
 * synchronization operations between two charts.
 */
export interface UseBasicChartSyncOptions {
  primaryChartId: string;
  secondaryChartId: string;
}

export const useBasicChartSync = (options: UseBasicChartSyncOptions) => {
  const { primaryChartId, secondaryChartId } = options;
  const synchronizer = useChartSynchronizer();

  const syncCharts = useCallback((primaryChart: IChartApi, secondaryChart: IChartApi) => {
    // Register both charts
    synchronizer.registerChart(primaryChartId, primaryChart, 'Primary Chart');
    synchronizer.registerChart(secondaryChartId, secondaryChart, 'Secondary Chart');

    logger.debug('Charts registered for synchronization');
  }, [primaryChartId, secondaryChartId, synchronizer]);

  const cleanup = useCallback(() => {
    synchronizer.unregisterChart(primaryChartId);
    synchronizer.unregisterChart(secondaryChartId);
    logger.debug('Charts unregistered');
  }, [primaryChartId, secondaryChartId, synchronizer]);

  return {
    syncCharts,
    cleanup,
    fitAllContent: synchronizer.fitAllChartsContent,
    setVisibleRange: synchronizer.setAllChartsVisibleRange
  };
};