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
  /** Whether the chart is synchronized (for chart jumping prevention) */
  preserveTimeScale?: boolean;
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
  indicatorId = 'unknown',
  preserveTimeScale = false
}) => {
  // Ref to store active fuzzy series
  const fuzzySeriesRef = useRef<FuzzySeriesRef[]>([]);
  
  // Ref to track operation state and prevent race conditions
  const operationStateRef = useRef({
    isOperating: false,
    operationCount: 0,
    lastSavedRange: null as any
  });

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
   * Update fuzzy overlay rendering with chart jumping prevention
   */
  const updateFuzzyOverlays = useCallback(() => {
    // Prevent overlapping operations
    if (operationStateRef.current.isOperating) {
      console.log(`⏳ [FuzzyOverlay] Operation in progress, skipping for ${indicatorId}`);
      return;
    }
    
    operationStateRef.current.isOperating = true;
    operationStateRef.current.operationCount++;
    const operationId = operationStateRef.current.operationCount;
    
    // Track whether we're adding fuzzy overlays to detect if we need jumping prevention
    const hadFuzzySeries = fuzzySeriesRef.current.length > 0;
    
    // ==================================================================================
    // ENHANCED FIX: Chart jumping prevention with stable range management
    // ==================================================================================
    // 
    // ISSUE: Time range preservation becomes unstable after multiple operations due to
    // accumulated errors and race conditions between fuzzy overlay operations.
    //
    // SOLUTION: 
    // 1. Use a master time range that's only updated when charts are stable
    // 2. Prevent concurrent operations with operation locking
    // 3. Validate time ranges before applying them
    // 4. Use longer delays for TradingView to stabilize
    // ==================================================================================
    
    const isEnablingFuzzyOverlays = !hadFuzzySeries && visible && fuzzyData && fuzzyData.length > 0;
    const isDisablingFuzzyOverlays = hadFuzzySeries && (!visible || !fuzzyData || fuzzyData.length === 0);
    
    // Reduced logging for cleaner output
    if (isEnablingFuzzyOverlays || isDisablingFuzzyOverlays) {
      console.log(`🎯 [FuzzyOverlay] Op ${operationId} ${isEnablingFuzzyOverlays ? 'ENABLE' : 'DISABLE'} for ${indicatorId}`);
    }
    
    // Get a fresh, stable time range - don't reuse potentially corrupted ranges
    let currentTimeRange: any = null;
    if (preserveTimeScale && chartInstance) {
      try {
        const timeScale = chartInstance.timeScale();
        const visibleRange = timeScale.getVisibleRange();
        
        // Validate the range before using it - both values must be numbers
        const isValidRange = visibleRange && 
            typeof visibleRange.from === 'number' && 
            typeof visibleRange.to === 'number' &&
            visibleRange.to > visibleRange.from &&
            isFinite(visibleRange.from) && 
            isFinite(visibleRange.to) &&
            visibleRange.from > 0 &&  // Sanity check for reasonable timestamps
            visibleRange.to > 0;
            
        if (isValidRange) {
          currentTimeRange = {
            from: Number(visibleRange.from),  // Ensure it's a number
            to: Number(visibleRange.to)       // Ensure it's a number
          };
          // Only update our master range if this one looks stable
          if (operationId <= 3 || !operationStateRef.current.lastSavedRange) {
            operationStateRef.current.lastSavedRange = { ...currentTimeRange };
          }
          // console.log(`💾 [FuzzyOverlay] Op ${operationId} - Valid time range:`, currentTimeRange);
        } else {
          console.warn(`⚠️ [FuzzyOverlay] Op ${operationId} - Invalid time range detected:`, {
            visibleRange,
            fromType: typeof visibleRange?.from,
            toType: typeof visibleRange?.to,
            fromValue: visibleRange?.from,
            toValue: visibleRange?.to
          });
          
          // Use the last saved range if available and valid
          if (operationStateRef.current.lastSavedRange) {
            const lastRange = operationStateRef.current.lastSavedRange;
            const isLastRangeValid = typeof lastRange.from === 'number' && 
                                   typeof lastRange.to === 'number' &&
                                   isFinite(lastRange.from) && 
                                   isFinite(lastRange.to);
            if (isLastRangeValid) {
              currentTimeRange = lastRange;
              // console.log(`🔄 [FuzzyOverlay] Op ${operationId} - Using last saved range:`, currentTimeRange);
            } else {
              console.warn(`⚠️ [FuzzyOverlay] Op ${operationId} - Last saved range also invalid, skipping time preservation`);
              currentTimeRange = null;
            }
          } else {
            console.warn(`⚠️ [FuzzyOverlay] Op ${operationId} - No valid saved range available`);
            currentTimeRange = null;
          }
        }
      } catch (error) {
        console.warn(`⚠️ [FuzzyOverlay] Op ${operationId} - Failed to get time range:`, error);
        currentTimeRange = operationStateRef.current.lastSavedRange;
      }
    }
    
    // Perform the operation
    const performOperation = () => {
      // Clean up existing series first
      cleanupSeries();

      // Don't create new series if not visible or no data
      if (!visible || !fuzzyData || fuzzyData.length === 0) {
        // console.log(`🧹 [FuzzyOverlay] Op ${operationId} - Cleaned up, no new series needed`);
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
      
      // console.log(`✨ [FuzzyOverlay] Op ${operationId} - Created ${fuzzySeriesRef.current.length} series`);
    };
    
    // Restore time range with enhanced stability
    const restoreTimeRange = () => {
      if (currentTimeRange && preserveTimeScale && chartInstance) {
        try {
          chartInstance.timeScale().setVisibleRange(currentTimeRange);
          // console.log(`🔄 [FuzzyOverlay] Op ${operationId} - Restored time range:`, currentTimeRange);
        } catch (error) {
          console.warn(`⚠️ [FuzzyOverlay] Op ${operationId} - Failed to restore time range:`, error);
        }
      }
      
      // Mark operation complete
      operationStateRef.current.isOperating = false;
    };
    
    // Execute the operation with proper timing
    performOperation();
    
    // Restore time range after a longer delay for stability
    if (currentTimeRange && preserveTimeScale) {
      setTimeout(restoreTimeRange, 50); // Increased delay for TradingView stability
    } else {
      operationStateRef.current.isOperating = false;
    }
    
    // ==================================================================================
    // END ENHANCED FIX - Fuzzy overlay chart jumping prevention
    // ==================================================================================
    
  }, [
    visible, 
    fuzzyData, 
    chartInstance, 
    opacity, 
    colorScheme, 
    indicatorId,
    preserveTimeScale,
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