import React, { useEffect, useRef, FC } from 'react';
import { 
  createChart, 
  IChartApi, 
  ISeriesApi, 
  CandlestickData, 
  LineData,
  CandlestickSeries,
  LineSeries
} from 'lightweight-charts';
import LoadingSpinner from '../../common/LoadingSpinner';
import ErrorDisplay from '../../common/ErrorDisplay';

/**
 * Pure presentation component for the basic price chart
 * 
 * This component focuses purely on rendering the TradingView chart
 * and handling TradingView-specific operations. All data and state
 * management is handled by the container component.
 */

export interface ChartData {
  candlestick: CandlestickData[];
  indicators: IndicatorSeries[];
}

export interface IndicatorSeries {
  id: string;
  name: string;
  data: LineData[];
  color: string;
  visible: boolean;
}

export interface ChartInfo {
  startDate: string;
  endDate: string;
  pointCount: number;
}

interface BasicChartProps {
  // Chart configuration
  width?: number;
  height?: number;
  
  // Data props
  chartData: ChartData | null;
  chartInfo: ChartInfo | null;
  isLoading: boolean;
  error: string | null;
  
  // Chart synchronization
  onChartCreated?: (chart: IChartApi) => void;
  onChartDestroyed?: () => void;
  onTimeRangeChange?: (range: { start: string; end: string }) => void;
  onCrosshairMove?: (params: any) => void;
  
  // Visual state
  showLoadingOverlay?: boolean;
  showErrorOverlay?: boolean;
  
  // Synchronization control
  preserveTimeScale?: boolean;
}

const BasicChart: FC<BasicChartProps> = ({
  width = 800,
  height = 400,
  chartData,
  chartInfo,
  isLoading,
  error,
  onChartCreated,
  onChartDestroyed,
  onTimeRangeChange,
  onCrosshairMove,
  showLoadingOverlay = true,
  showErrorOverlay = true,
  preserveTimeScale = false
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<any | null>(null);
  const indicatorSeriesRef = useRef<Map<string, any>>(new Map());

  // Component-level error handler to prevent memory leaks
  useEffect(() => {
    const handleWindowError = (event: ErrorEvent) => {
      if (event.message && event.message.includes('Value is null')) {
        console.warn('[BasicChart] Caught TradingView null error, preventing crash');
        event.preventDefault();
        return false;
      }
      return true;
    };
    
    window.addEventListener('error', handleWindowError);
    
    return () => {
      window.removeEventListener('error', handleWindowError);
    };
  }, []); // Only run once per component

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) {
      return;
    }

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      if (onChartDestroyed) {
        onChartDestroyed();
      }
    }

    // Create new chart
    // Remove debug logging and try to catch the actual error
    let chart;
    try {
      chart = createChart(chartContainerRef.current, {
        width,
        height,
        layout: {
          background: { color: '#ffffff' },
          textColor: '#333',
        },
        grid: {
          vertLines: { color: '#f0f0f0' },
          horzLines: { color: '#f0f0f0' },
        },
        crosshair: {
          mode: 1,
        },
        rightPriceScale: {
          borderColor: '#cccccc',
        },
        timeScale: {
          borderColor: '#cccccc',
          timeVisible: true,
          secondsVisible: false,
          rightOffset: 5,
          barSpacing: 6,
          minBarSpacing: 0.5,
          rightBarStaysOnScroll: true,
          shiftVisibleRangeOnNewBar: false,
        },
      });
    } catch (error) {
      console.error('Failed to create chart:', error);
      throw error;
    }

    chartRef.current = chart;

    // Create candlestick series using v5 unified API
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Set up event listeners
    if (onTimeRangeChange) {
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range && range.from && range.to && !isNaN(range.from) && !isNaN(range.to)) {
          onTimeRangeChange({
            start: new Date(range.from * 1000).toISOString(),
            end: new Date(range.to * 1000).toISOString()
          });
        }
      });
    }

    if (onCrosshairMove) {
      chart.subscribeCrosshairMove((param) => {
        onCrosshairMove(param);
      });
    }

    // Notify parent
    if (onChartCreated) {
      onChartCreated(chart);
    }

    // Cleanup function
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        candlestickSeriesRef.current = null;
        indicatorSeriesRef.current.clear();
        if (onChartDestroyed) {
          onChartDestroyed();
        }
      }
    };
  }, [width, height]);

  // Update chart data when it changes
  useEffect(() => {
    if (!chartData || !candlestickSeriesRef.current || !chartRef.current) {
      return;
    }

    // Capture the current range to detect jumps
    const rangeBeforeUpdate = chartRef.current.timeScale().getVisibleRange();
    const existingIndicatorCount = indicatorSeriesRef.current.size;

    // Update candlestick data
    if (chartData.candlestick && chartData.candlestick.length > 0) {
      const validData = chartData.candlestick.filter(item => 
        item && 
        typeof item.time !== 'undefined' && 
        typeof item.open === 'number' && 
        typeof item.high === 'number' && 
        typeof item.low === 'number' && 
        typeof item.close === 'number' &&
        !isNaN(item.open) && !isNaN(item.high) && !isNaN(item.low) && !isNaN(item.close)
      );
      
      if (validData.length > 0 && candlestickSeriesRef.current) {
        candlestickSeriesRef.current.setData(validData);
      }
    }

    // Update indicator series
    const currentIndicatorIds = new Set(indicatorSeriesRef.current.keys());
    const newIndicatorIds = new Set(chartData.indicators.map(ind => ind.id));

    // Remove old indicators
    currentIndicatorIds.forEach(id => {
      if (!newIndicatorIds.has(id)) {
        const series = indicatorSeriesRef.current.get(id);
        if (series && chartRef.current) {
          chartRef.current.removeSeries(series);
          indicatorSeriesRef.current.delete(id);
        }
      }
    });

    // Add or update indicators
    chartData.indicators.forEach(indicator => {
      if (!indicator || !indicator.id || !Array.isArray(indicator.data)) {
        return;
      }
      
      let series = indicatorSeriesRef.current.get(indicator.id);
      
      if (!series && chartRef.current) {
        // Use v5 unified API for line series
        series = chartRef.current.addSeries(LineSeries, {
          color: indicator.color || '#2196F3',
          lineWidth: 2,
          title: indicator.name || 'Indicator'
        });
        if (series) {
          indicatorSeriesRef.current.set(indicator.id, series);
        }
      }
      
      if (series) {
        if (indicator.data && indicator.data.length > 0) {
          series.setData(indicator.data);
        }
        
        // Apply all options at once including visibility
        series.applyOptions({
          color: indicator.color || '#2196F3',
          title: indicator.name || 'Indicator',
          lineVisible: indicator.visible !== false,
          lastValueVisible: indicator.visible !== false,
          priceLineVisible: indicator.visible !== false
        });
      }
    });

    // Fit content after data update (only if not preserving time scale for sync)
    if (!preserveTimeScale && chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }

    // ==================================================================================
    // CRITICAL FIX: Chart jumping bug when adding indicators - DO NOT REMOVE
    // ==================================================================================
    // 
    // ISSUE: TradingView Lightweight Charts v5 automatically adjusts the visible time 
    // range when indicators are added to synchronized charts, causing unwanted forward 
    // jumps in time that break the user experience.
    //
    // ROOT CAUSE: TradingView's internal auto-scaling logic conflicts with chart 
    // synchronization (preserveTimeScale=true), particularly when adding the first 
    // overlay indicator to a chart.
    //
    // SOLUTION: Preventive visibility toggle (hide/show) of the first indicator 
    // immediately after it's added. This forces TradingView to recalculate the 
    // correct time range without the unwanted jump.
    //
    // TIMING: 1ms delays are critical - tested down from 300ms to find minimum 
    // effective timing that's imperceptible to users.
    //
    // TRIGGER: Only on first overlay indicator addition to avoid unnecessary 
    // processing and maintain performance.
    //
    // TESTED: Confirmed working with TradingView Lightweight Charts v5.0.7
    // DATE: May 28, 2025
    // SEVERITY: CRITICAL - Removing this fix will cause chart jumping regression
    // ==================================================================================
    
    const indicatorCountChanged = chartData.indicators.length !== existingIndicatorCount;
    
    // Apply preventive fix only when adding the first overlay indicator to synchronized charts
    if (indicatorCountChanged && preserveTimeScale && chartRef.current) {
      // Check if this is the first overlay indicator being added
      const isFirstOverlayIndicator = chartData.indicators.length === 1 && existingIndicatorCount === 0;
      
      if (isFirstOverlayIndicator) {
        // CRITICAL: Apply the visibility fix preventively - DO NOT MODIFY TIMING
        setTimeout(() => {
          const eyeButtons = document.querySelectorAll('button[title="Hide"], button[title="Show"]');
          if (eyeButtons.length > 0) {
            (eyeButtons[0] as HTMLButtonElement).click();
            setTimeout(() => {
              const eyeButtonsAgain = document.querySelectorAll('button[title="Hide"], button[title="Show"]');
              if (eyeButtonsAgain.length > 0) {
                (eyeButtonsAgain[0] as HTMLButtonElement).click();
              }
            }, 1); // CRITICAL: 1ms timing - tested minimum effective delay
          }
        }, 1); // CRITICAL: 1ms timing - tested minimum effective delay
      }
    }
    
    // ==================================================================================
    // END CRITICAL FIX - Chart jumping prevention
    // ==================================================================================
    
  }, [chartData, preserveTimeScale]);

  // Handle resize
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ width, height });
    }
  }, [width, height]);


  return (
    <div style={{ position: 'relative', width, height }}>
      {/* Chart container */}
      <div 
        ref={chartContainerRef} 
        style={{ width: '100%', height: '100%' }}
      />
    
    {/* Loading overlay */}
    {isLoading && showLoadingOverlay && (
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <LoadingSpinner 
          size="large" 
          message="Loading chart data..." 
        />
      </div>
    )}
    
    {/* Error overlay */}
    {error && showErrorOverlay && (
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem'
      }}>
        <ErrorDisplay 
          error={error}
          title="Chart Error"
          compact={true}
        />
      </div>
    )}
    
    {/* Chart info display */}
    {chartInfo && !isLoading && !error && (
      <div style={{
        position: 'absolute',
        bottom: '8px',
        left: '8px',
        fontSize: '0.75rem',
        color: '#666',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        padding: '0.25rem 0.5rem',
        borderRadius: '3px',
        border: '1px solid #e0e0e0'
      }}>
        {chartInfo.pointCount} data points | {chartInfo.startDate} to {chartInfo.endDate}
      </div>
    )}
    
  </div>
  );
};

export default BasicChart;