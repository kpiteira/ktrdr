import React, { useEffect, useRef, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, LineData } from 'lightweight-charts';

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
  showErrorOverlay = true
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    console.log('[BasicChart] Initializing chart...');

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
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
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

    // Set up event listeners
    if (onTimeRangeChange) {
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range) {
          onTimeRangeChange({
            start: new Date(range.from * 1000).toISOString(),
            end: new Date(range.to * 1000).toISOString()
          });
        }
      });
    }

    if (onCrosshairMove) {
      chart.subscribeCrosshairMove(onCrosshairMove);
    }

    // Notify parent
    if (onChartCreated) {
      onChartCreated(chart);
    }

    console.log('[BasicChart] Chart initialized successfully');

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
  }, [width, height]); // Only recreate chart when dimensions change

  // Update chart data when it changes
  useEffect(() => {
    if (!chartData || !candlestickSeriesRef.current || !chartRef.current) {
      return;
    }

    console.log('[BasicChart] Updating chart data:', chartData.candlestick.length, 'candlesticks,', chartData.indicators.length, 'indicators');

    // Update candlestick data
    candlestickSeriesRef.current.setData(chartData.candlestick);

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
        console.log('[BasicChart] Created indicator series:', indicator.id);
      }
      
      if (series) {
        // Update series data and options
        series.setData(indicator.data);
        (series as any).applyOptions({
          color: indicator.color,
          visible: indicator.visible,
          title: indicator.name
        });
        console.log('[BasicChart] Updated indicator series:', indicator.id);
      }
    });

    // Fit content after data update
    chartRef.current.timeScale().fitContent();
    
  }, [chartData]);

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
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: '0.5rem'
        }}>
          <div style={{
            width: '32px',
            height: '32px',
            border: '3px solid #f3f3f3',
            borderTop: '3px solid #1976d2',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }} />
          <div style={{ fontSize: '0.9rem', color: '#666' }}>
            Loading chart data...
          </div>
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
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: '0.5rem'
        }}>
          <div style={{ fontSize: '2rem', color: '#f44336' }}>⚠️</div>
          <div style={{ fontSize: '0.9rem', color: '#f44336', textAlign: 'center' }}>
            {error}
          </div>
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
      
      {/* CSS for loading spinner */}
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default BasicChart;