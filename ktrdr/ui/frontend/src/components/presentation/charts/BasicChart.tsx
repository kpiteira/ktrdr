import React, { useEffect, useRef, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData } from 'lightweight-charts';
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
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    try {
      // Clean up existing chart
      if (chartRef.current) {
        chartRef.current.remove();
        if (onChartDestroyed) {
          onChartDestroyed();
        }
      }

      // Create new chart with global error handling
      const chart = createChart(chartContainerRef.current, {
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
        mode: 1, // Normal crosshair mode
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5, // Minimal right offset
        barSpacing: 6,
        minBarSpacing: 0.5,
        // Prevent excessive panning
        rightBarStaysOnScroll: true,
        shiftVisibleRangeOnNewBar: false,
      },
    });

    chartRef.current = chart;

    // Create candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Set up event listeners with error handling
    if (onTimeRangeChange) {
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        try {
          if (range && range.from && range.to && !isNaN(range.from) && !isNaN(range.to)) {
            onTimeRangeChange({
              start: new Date(range.from * 1000).toISOString(),
              end: new Date(range.to * 1000).toISOString()
            });
          }
        } catch (error) {
          console.warn('[BasicChart] Error in time range change handler:', error);
        }
      });
    }
    

    if (onCrosshairMove) {
      chart.subscribeCrosshairMove((param) => {
        try {
          onCrosshairMove(param);
        } catch (error) {
          console.warn('[BasicChart] Error in crosshair move handler:', error);
        }
      });
    }

    // Notify parent
    if (onChartCreated) {
      onChartCreated(chart);
    }

      // Add window error handler for TradingView internal errors
      const handleWindowError = (event: ErrorEvent) => {
        if (event.message && event.message.includes('Value is null')) {
          console.warn('[BasicChart] Caught TradingView null error, preventing crash');
          event.preventDefault();
          return false;
        }
        return true;
      };
      window.addEventListener('error', handleWindowError);
      
      // Store handler reference for cleanup
      (chart as any)._errorHandler = handleWindowError;

      console.log('[BasicChart] Chart initialized successfully');

    } catch (error) {
      console.error('[BasicChart] Error during chart initialization:', error);
      // Fallback: create a minimal chart if possible
      try {
        if (chartContainerRef.current && !chartRef.current) {
          const fallbackChart = createChart(chartContainerRef.current, {
            width,
            height,
            layout: { background: { color: '#ffffff' }, textColor: '#333' },
            timeScale: { rightOffset: 5, rightBarStaysOnScroll: true },
          });
          chartRef.current = fallbackChart;
          const fallbackSeries = fallbackChart.addCandlestickSeries();
          candlestickSeriesRef.current = fallbackSeries;
        }
      } catch (fallbackError) {
        console.error('[BasicChart] Fallback chart creation failed:', fallbackError);
      }
    }

    // Cleanup function
    return () => {
      try {
        if (chartRef.current) {
          // Clean up error handler
          const errorHandler = (chartRef.current as any)._errorHandler;
          if (errorHandler) {
            window.removeEventListener('error', errorHandler);
          }
          
          chartRef.current.remove();
          chartRef.current = null;
          candlestickSeriesRef.current = null;
          indicatorSeriesRef.current.clear();
          if (onChartDestroyed) {
            onChartDestroyed();
          }
        }
      } catch (cleanupError) {
        console.warn('[BasicChart] Error during cleanup:', cleanupError);
      }
    };
  }, [width, height]); // Only recreate chart when dimensions change

  // Update chart data when it changes
  useEffect(() => {
    if (!chartData || !candlestickSeriesRef.current || !chartRef.current) {
      return;
    }

    // Wrap all data operations in error handling to prevent TradingView internal errors
    try {
      // console.log('[BasicChart] 📊 Updating chart with', chartData.indicators.length, 'indicators');

      // Update candlestick data with extensive validation
      if (chartData.candlestick && chartData.candlestick.length > 0) {
        try {
          // Validate data bounds to prevent null errors when panning
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
            // Use defensive data setting with timeout to prevent race conditions
            setTimeout(() => {
              try {
                if (candlestickSeriesRef.current) {
                  candlestickSeriesRef.current.setData(validData);
                }
              } catch (setDataError) {
                console.warn('[BasicChart] Error in setData timeout:', setDataError);
              }
            }, 0);
          }
        } catch (error) {
          console.warn('[BasicChart] Error processing candlestick data:', error);
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
          console.log('[BasicChart] Removed indicator series:', id);
        }
      }
    });

    // Add or update indicators
    chartData.indicators.forEach(indicator => {
      let series = indicatorSeriesRef.current.get(indicator.id);
      
      if (!series && chartRef.current) {
        // Create new series
        series = chartRef.current.addLineSeries({
          color: indicator.color,
          lineWidth: 2,
          title: indicator.name,
          visible: indicator.visible
        });
        indicatorSeriesRef.current.set(indicator.id, series);
        // console.log('[BasicChart] ✅ Created indicator series:', indicator.id);
      }
      
      if (series) {
        // Check for time mismatch
        const indicatorFirstTime = indicator.data[0]?.time;
        const candlestickFirstTime = chartData.candlestick[0]?.time;
        
        // Debug time mismatch only when needed
        // console.log('[BasicChart] 🔍 Time check - Indicator first time:', indicatorFirstTime, 'Candlestick first time:', candlestickFirstTime);
        
        // Update series data and options
        series.setData(indicator.data);
        (series as any).applyOptions({
          color: indicator.color,
          visible: indicator.visible,
          title: indicator.name
        });
        // console.log('[BasicChart] ✅ Updated indicator series:', indicator.id);
      }
    });

      // Fit content after data update (only if not preserving time scale for sync)
      if (!preserveTimeScale && chartRef.current) {
        try {
          chartRef.current.timeScale().fitContent();
        } catch (fitError) {
          console.warn('[BasicChart] Error fitting content:', fitError);
        }
      }
      
    } catch (dataUpdateError) {
      console.error('[BasicChart] Error during data update:', dataUpdateError);
    }
    
  }, [chartData, chartData?.indicators.length, preserveTimeScale]);

  // Handle resize
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ width, height });
    }
  }, [width, height]);


  try {
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
  } catch (error) {
    console.error('[BasicChart] ERROR in component:', error);
    return <div>BasicChart Error: {String(error)}</div>;
  }
};

export default BasicChart;