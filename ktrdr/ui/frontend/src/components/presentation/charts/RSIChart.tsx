import React, { useEffect, useRef, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData } from 'lightweight-charts';
import LoadingSpinner from '../../common/LoadingSpinner';
import ErrorDisplay from '../../common/ErrorDisplay';
import EmptyState from '../../common/EmptyState';

/**
 * Pure presentation component for the RSI oscillator chart
 * 
 * This component focuses purely on rendering the TradingView chart
 * for RSI indicators. All data and state management is handled 
 * by the container component.
 */

export interface RSIData {
  indicators: RSIIndicatorSeries[];
}

export interface RSIIndicatorSeries {
  id: string;
  name: string;
  data: LineData[];
  color: string;
  visible: boolean;
}

interface RSIChartProps {
  // Chart configuration
  width?: number;
  height?: number;
  
  // Data props
  rsiData: RSIData | null;
  isLoading: boolean;
  error: string | null;
  
  // Chart synchronization
  onChartCreated?: (chart: IChartApi) => void;
  onChartDestroyed?: () => void;
  onCrosshairMove?: (params: any) => void;
  
  // Visual state
  showLoadingOverlay?: boolean;
  showErrorOverlay?: boolean;
  
  // RSI-specific styling
  showOverboughtOversold?: boolean;
  
  // Synchronization control
  preserveTimeScale?: boolean;
}

const RSIChart: FC<RSIChartProps> = ({
  width = 800,
  height = 200,
  rsiData,
  isLoading,
  error,
  onChartCreated,
  onChartDestroyed,
  onCrosshairMove,
  showLoadingOverlay = true,
  showErrorOverlay = true,
  showOverboughtOversold = true,
  preserveTimeScale = false
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const overboughtLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const oversoldLineRef = useRef<ISeriesApi<'Line'> | null>(null);

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    console.log('[RSIChart] Initializing RSI chart...');

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      if (onChartDestroyed) {
        onChartDestroyed();
      }
    }

    // Create new chart
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
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 10, // Prevents panning too far into future
        barSpacing: 6,
        minBarSpacing: 0.5,
      },
    });

    chartRef.current = chart;

    // Add overbought/oversold reference lines if enabled
    if (showOverboughtOversold) {
      // Overbought line at 70
      const overboughtLine = chart.addLineSeries({
        color: '#f44336',
        lineWidth: 1,
        lineStyle: 2, // Dashed line
        title: 'Overbought (70)',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      overboughtLineRef.current = overboughtLine;

      // Oversold line at 30
      const oversoldLine = chart.addLineSeries({
        color: '#4CAF50',
        lineWidth: 1,
        lineStyle: 2, // Dashed line
        title: 'Oversold (30)',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      oversoldLineRef.current = oversoldLine;
    }

    // Set up event listeners with error handling
    if (onCrosshairMove) {
      chart.subscribeCrosshairMove((param) => {
        try {
          onCrosshairMove(param);
        } catch (error) {
          console.warn('[RSIChart] Error in crosshair move handler:', error);
        }
      });
    }

    // Notify parent
    if (onChartCreated) {
      onChartCreated(chart);
    }

    console.log('[RSIChart] RSI chart initialized successfully');

    // Cleanup function
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        indicatorSeriesRef.current.clear();
        overboughtLineRef.current = null;
        oversoldLineRef.current = null;
        if (onChartDestroyed) {
          onChartDestroyed();
        }
      }
    };
  }, [width, height, showOverboughtOversold]); // Only recreate chart when dimensions or config change

  // Update chart data when it changes
  useEffect(() => {
    if (!rsiData || !chartRef.current) {
      return;
    }


    // Update overbought/oversold lines if they exist and we have data
    if (showOverboughtOversold && rsiData.indicators.length > 0) {
      const firstIndicator = rsiData.indicators[0];
      if (firstIndicator.data.length > 0) {
        const startTime = firstIndicator.data[0].time;
        const endTime = firstIndicator.data[firstIndicator.data.length - 1].time;

        // Set overbought line data
        if (overboughtLineRef.current) {
          overboughtLineRef.current.setData([
            { time: startTime, value: 70 },
            { time: endTime, value: 70 }
          ]);
        }

        // Set oversold line data
        if (oversoldLineRef.current) {
          oversoldLineRef.current.setData([
            { time: startTime, value: 30 },
            { time: endTime, value: 30 }
          ]);
        }
      }
    }

    // Update RSI indicator series
    const currentIndicatorIds = new Set(indicatorSeriesRef.current.keys());
    const newIndicatorIds = new Set(rsiData.indicators.map(ind => ind.id));

    // Remove old indicators
    currentIndicatorIds.forEach(id => {
      if (!newIndicatorIds.has(id)) {
        const series = indicatorSeriesRef.current.get(id);
        if (series && chartRef.current) {
          chartRef.current.removeSeries(series);
          indicatorSeriesRef.current.delete(id);
          console.log('[RSIChart] Removed RSI series:', id);
        }
      }
    });

    // Add or update indicators
    rsiData.indicators.forEach(indicator => {
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
        console.log('[RSIChart] Created RSI series:', indicator.id);
      }
      
      if (series) {
        // Update series data and options
        series.setData(indicator.data);
        (series as any).applyOptions({
          color: indicator.color,
          visible: indicator.visible,
          title: indicator.name
        });
      }
    });

    // Fit content after data update (only if not preserving time scale for sync)
    if (!preserveTimeScale) {
      chartRef.current.timeScale().fitContent();
    }
    
  }, [rsiData, showOverboughtOversold, preserveTimeScale]);

  // Handle resize
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ width, height });
    }
  }, [width, height]);

  return (
    <div style={{ position: 'relative', width, height }}>
      {/* Chart title */}
      <div style={{
        position: 'absolute',
        top: '8px',
        left: '8px',
        fontSize: '0.9rem',
        fontWeight: '600',
        color: '#333',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        padding: '0.25rem 0.5rem',
        borderRadius: '3px',
        border: '1px solid #e0e0e0',
        zIndex: 10
      }}>
        RSI Oscillator
      </div>

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
            size="medium" 
            color="#9C27B0"
            message="Loading RSI data..." 
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
          padding: '1rem'
        }}>
          <ErrorDisplay 
            error={error}
            title="RSI Chart Error"
            compact={true}
          />
        </div>
      )}
      
      {/* No data message */}
      {!isLoading && !error && (!rsiData || rsiData.indicators.length === 0) && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '100%'
        }}>
          <EmptyState
            icon="📊"
            title="No RSI indicators"
            description="Add RSI from the indicators sidebar to see oscillator data"
            compact={true}
          />
        </div>
      )}
    </div>
  );
};

export default RSIChart;