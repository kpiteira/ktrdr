/**
 * FuzzyOverlay Presentation Component
 * 
 * Pure component for rendering fuzzy membership overlays on TradingView charts.
 * Follows Container/Presentation pattern - receives all data via props,
 * no internal state or side effects.
 */

import React, { useEffect, useRef, memo, useCallback } from 'react';
import { 
  IChartApi, 
  ISeriesApi, 
  AreaSeries,
  AreaData,
  UTCTimestamp 
} from 'lightweight-charts';
import { ChartFuzzyData } from '../../../api/types/fuzzy';
import { createLogger } from '../../../utils/logger';

const logger = createLogger('FuzzyOverlay');

/**
 * Props interface for FuzzyOverlay component
 */
export interface FuzzyOverlayProps {
  /** TradingView chart instance to render overlays on */
  chartInstance: IChartApi | null;
  /** Fuzzy membership data to render */
  fuzzyData: ChartFuzzyData[] | null;
  /** Whether the overlay is visible */
  visible: boolean;
  /** Global opacity for all fuzzy sets */
  opacity?: number;
  /** Color scheme for fuzzy sets */
  colorScheme?: string;
  /** Indicator ID for debugging/logging */
  indicatorId?: string;
}

/**
 * Interface for managing fuzzy series
 */
interface FuzzySeriesRef {
  series: ISeriesApi<'Area'>;
  setName: string;
}

/**
 * FuzzyOverlay Component
 * 
 * Renders fuzzy membership overlays as AreaSeries on a TradingView chart.
 * Uses proper z-index ordering to place overlays behind indicator lines.
 */
export const FuzzyOverlay: React.FC<FuzzyOverlayProps> = memo(({
  chartInstance,
  fuzzyData,
  visible,
  opacity = 0.3,
  colorScheme = 'default',
  indicatorId = 'unknown'
}) => {
  // Ref to store active fuzzy series
  const fuzzySeriesRef = useRef<FuzzySeriesRef[]>([]);

  /**
   * Clean up all fuzzy series
   */
  const cleanupSeries = useCallback(() => {
    if (fuzzySeriesRef.current.length > 0) {
      logger.debug(`Cleaning up ${fuzzySeriesRef.current.length} fuzzy series for ${indicatorId}`);
      
      fuzzySeriesRef.current.forEach(({ series }) => {
        try {
          // Check if chart instance is still valid before trying to remove series
          if (chartInstance && series) {
            chartInstance.removeSeries(series);
          }
        } catch (error) {
          // This is expected when the chart has been destroyed (e.g., panel collapse)
          // Just log at debug level instead of warning to avoid noise
          logger.debug(`Fuzzy series cleanup skipped - chart likely destroyed for ${indicatorId}`);
        }
      });
      
      // Always clear the ref regardless of success/failure
      fuzzySeriesRef.current = [];
    }
  }, [chartInstance, indicatorId]);

  /**
   * Create and configure a fuzzy area series
   */
  const createFuzzySeries = useCallback((
    fuzzySet: ChartFuzzyData
  ): ISeriesApi<'Area'> | null => {
    if (!chartInstance) {
      logger.warn(`Cannot create fuzzy series - no chart instance for ${indicatorId}`);
      return null;
    }

    try {
      // Create area series with fuzzy-specific configuration
      const series = chartInstance.addSeries(AreaSeries, {
        // Color configuration
        topColor: fuzzySet.color,
        bottomColor: fuzzySet.color,
        lineColor: fuzzySet.color,
        lineWidth: 1,
        
        // Transparency and styling
        crosshairMarkerVisible: false,
        lastValueVisible: false,
        priceLineVisible: false,
        
        // Title for legend/tooltip
        title: `Fuzzy ${fuzzySet.setName}`,
        
        // Ensure fuzzy overlays are behind other series
        priceScaleId: 'right',
      });

      // Set the fuzzy membership data
      const areaData: AreaData[] = fuzzySet.data.map(point => ({
        time: point.time as UTCTimestamp,
        value: point.value
      }));

      series.setData(areaData);

      // Debug: Check what we actually created
      const nonZeroData = areaData.filter(point => point.value > 0);
      console.log(`[FuzzyOverlay] Created series for ${fuzzySet.setName}:`, {
        color: fuzzySet.color,
        dataPoints: areaData.length,
        nonZeroPoints: nonZeroData.length,
        sampleData: areaData.slice(0, 3),
        sampleNonZero: nonZeroData.slice(0, 3),
        valueRange: {
          min: Math.min(...areaData.map(p => p.value)),
          max: Math.max(...areaData.map(p => p.value))
        }
      });
      
      return series;
    } catch (error) {
      logger.error(`Failed to create fuzzy series for ${fuzzySet.setName}:`, error);
      return null;
    }
  }, [chartInstance, indicatorId]);

  /**
   * Update fuzzy overlay rendering
   */
  const updateFuzzyOverlays = useCallback(() => {
    // Clean up existing series first
    cleanupSeries();

    // Don't create new series if not visible or no data
    if (!visible || !fuzzyData || fuzzyData.length === 0) {
      return;
    }

    if (!chartInstance) {
      logger.debug(`Cannot update fuzzy overlays - no chart instance for ${indicatorId}`);
      return;
    }

    // Create new series for each fuzzy set
    fuzzyData.forEach(fuzzySet => {
      const series = createFuzzySeries(fuzzySet);
      if (series) {
        fuzzySeriesRef.current.push({
          series,
          setName: fuzzySet.setName
        });
      }
    });
  }, [
    visible, 
    fuzzyData, 
    chartInstance, 
    opacity, 
    colorScheme, 
    indicatorId,
    cleanupSeries,
    createFuzzySeries
  ]);

  /**
   * Effect to update overlays when props change
   */
  useEffect(() => {
    updateFuzzyOverlays();
  }, [updateFuzzyOverlays]);

  /**
   * Effect to handle chart instance changes
   */
  useEffect(() => {
    if (!chartInstance) {
      cleanupSeries();
    }
  }, [chartInstance, cleanupSeries]);

  /**
   * Cleanup effect on unmount
   */
  useEffect(() => {
    return () => {
      cleanupSeries();
    };
  }, [cleanupSeries]);

  // This is a pure rendering component that works with TradingView charts
  // It doesn't render any React elements directly, only manages chart series
  return null;
});

FuzzyOverlay.displayName = 'FuzzyOverlay';

export default FuzzyOverlay;