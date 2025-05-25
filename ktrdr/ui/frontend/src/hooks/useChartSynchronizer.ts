import { useRef, useCallback } from 'react';
import { IChartApi } from 'lightweight-charts';

/**
 * Custom hook for synchronizing multiple charts
 * 
 * Provides utilities for synchronizing time scale, crosshair position,
 * and zoom/pan operations across multiple TradingView charts.
 */

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
}

export const useChartSynchronizer = (): UseChartSynchronizerReturn => {
  const chartsRef = useRef<Map<string, ChartReference>>(new Map());
  const syncInProgressRef = useRef<boolean>(false);

  // Register a chart for synchronization
  const registerChart = useCallback((id: string, chart: IChartApi, name?: string) => {
    console.log('[useChartSynchronizer] Registering chart:', id, name);
    
    const chartRef: ChartReference = { id, chart, name };
    chartsRef.current.set(id, chartRef);

    // Set up automatic synchronization listeners
    chart.timeScale().subscribeVisibleTimeRangeChange(() => {
      if (!syncInProgressRef.current) {
        synchronizeTimeScale(id);
      }
    });

    chart.subscribeCrosshairMove(param => {
      if (!syncInProgressRef.current) {
        synchronizeCrosshair(id, param);
      }
    });

    console.log('[useChartSynchronizer] Chart registered with listeners:', id);
  }, []);

  // Unregister a chart
  const unregisterChart = useCallback((id: string) => {
    console.log('[useChartSynchronizer] Unregistering chart:', id);
    chartsRef.current.delete(id);
  }, []);

  // Synchronize time scale across all charts
  const synchronizeTimeScale = useCallback((sourceChartId: string) => {
    const sourceChart = chartsRef.current.get(sourceChartId);
    if (!sourceChart) {
      console.warn('[useChartSynchronizer] Source chart not found:', sourceChartId);
      return;
    }

    const sourceTimeScale = sourceChart.chart.timeScale();
    const visibleRange = sourceTimeScale.getVisibleRange();
    
    if (!visibleRange) {
      console.warn('[useChartSynchronizer] No visible range available from source chart');
      return;
    }

    console.log('[useChartSynchronizer] Synchronizing time scale from:', sourceChartId, visibleRange);
    
    // Set flag to prevent infinite sync loops
    syncInProgressRef.current = true;

    try {
      chartsRef.current.forEach((chartRef, chartId) => {
        if (chartId !== sourceChartId) {
          try {
            chartRef.chart.timeScale().setVisibleRange(visibleRange);
            console.log('[useChartSynchronizer] Time scale synchronized for:', chartId);
          } catch (error) {
            console.error('[useChartSynchronizer] Error synchronizing time scale for:', chartId, error);
          }
        }
      });
    } finally {
      // Reset flag after a short delay to allow for chart updates
      setTimeout(() => {
        syncInProgressRef.current = false;
      }, 50);
    }
  }, []);

  // Synchronize crosshair position across all charts
  const synchronizeCrosshair = useCallback((sourceChartId: string, point: any) => {
    if (!point || !point.time) {
      return;
    }

    console.log('[useChartSynchronizer] Synchronizing crosshair from:', sourceChartId, point.time);
    
    // Set flag to prevent infinite sync loops
    syncInProgressRef.current = true;

    try {
      chartsRef.current.forEach((chartRef, chartId) => {
        if (chartId !== sourceChartId) {
          try {
            // Create a crosshair position for the target chart
            chartRef.chart.setCrosshairPosition(point.time, point.seriesData?.get(point.seriesData.keys().next().value));
            console.log('[useChartSynchronizer] Crosshair synchronized for:', chartId);
          } catch (error) {
            console.error('[useChartSynchronizer] Error synchronizing crosshair for:', chartId, error);
          }
        }
      });
    } finally {
      // Reset flag after a short delay
      setTimeout(() => {
        syncInProgressRef.current = false;
      }, 10);
    }
  }, []);

  // Fit content for all charts
  const fitAllChartsContent = useCallback(() => {
    console.log('[useChartSynchronizer] Fitting content for all charts');
    
    chartsRef.current.forEach((chartRef, chartId) => {
      try {
        chartRef.chart.timeScale().fitContent();
        console.log('[useChartSynchronizer] Content fitted for:', chartId);
      } catch (error) {
        console.error('[useChartSynchronizer] Error fitting content for:', chartId, error);
      }
    });
  }, []);

  // Set visible range for all charts
  const setAllChartsVisibleRange = useCallback((from: number, to: number) => {
    console.log('[useChartSynchronizer] Setting visible range for all charts:', { from, to });
    
    syncInProgressRef.current = true;

    try {
      chartsRef.current.forEach((chartRef, chartId) => {
        try {
          chartRef.chart.timeScale().setVisibleRange({ from, to });
          console.log('[useChartSynchronizer] Visible range set for:', chartId);
        } catch (error) {
          console.error('[useChartSynchronizer] Error setting visible range for:', chartId, error);
        }
      });
    } finally {
      setTimeout(() => {
        syncInProgressRef.current = false;
      }, 50);
    }
  }, []);

  // Get all registered charts (for debugging/inspection)
  const getRegisteredCharts = useCallback((): ChartReference[] => {
    return Array.from(chartsRef.current.values());
  }, []);

  return {
    registerChart,
    unregisterChart,
    synchronizeTimeScale,
    synchronizeCrosshair,
    fitAllChartsContent,
    setAllChartsVisibleRange,
    getRegisteredCharts
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

    console.log('[useBasicChartSync] Charts registered for synchronization');
  }, [primaryChartId, secondaryChartId, synchronizer]);

  const cleanup = useCallback(() => {
    synchronizer.unregisterChart(primaryChartId);
    synchronizer.unregisterChart(secondaryChartId);
    console.log('[useBasicChartSync] Charts unregistered');
  }, [primaryChartId, secondaryChartId, synchronizer]);

  return {
    syncCharts,
    cleanup,
    fitAllContent: synchronizer.fitAllChartsContent,
    setVisibleRange: synchronizer.setAllChartsVisibleRange
  };
};