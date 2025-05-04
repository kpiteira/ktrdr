import React, { useRef, useEffect, useState, useCallback } from 'react';
import { 
  createChart, 
  IChartApi,
  ColorType,
  CrosshairMode,
  LogicalRangeChangeEventHandler,
  UTCTimestamp
} from 'lightweight-charts';
import { useTheme } from '../layouts/ThemeProvider';
import { createChartOptions, handleChartResize, cleanupChart } from '../../utils/charts';
import { ChartConfig } from '../../types/charts';

import './ChartContainer.css';

export interface ChartContainerProps {
  /** Width of the chart (will use container width if not specified) */
  width?: number;
  /** Height of the chart */
  height?: number;
  /** Class name for additional styling */
  className?: string;
  /** Whether to resize the chart when window resizes */
  autoResize?: boolean;
  /** Custom chart options */
  chartOptions?: Partial<ChartConfig>;
  /** Callback for when crosshair moves */
  onCrosshairMove?: (param: any) => void;
  /** Callback for when time scale changes */
  onVisibleTimeRangeChange?: LogicalRangeChangeEventHandler;
  /** Callback when chart is created */
  onChartReady?: (chart: IChartApi) => void;
  /** Children to render */
  children?: React.ReactNode;
}

/**
 * ChartContainer component
 * 
 * A responsive container for TradingView Lightweight Charts
 * with theme synchronization and automatic resizing
 */
export const ChartContainer: React.FC<ChartContainerProps> = ({
  width,
  height = 400,
  className = '',
  autoResize = true,
  chartOptions = {},
  onCrosshairMove,
  onVisibleTimeRangeChange,
  onChartReady,
  children
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);
  const { theme } = useTheme();

  // Function to handle window resize events
  const handleResize = useCallback(() => {
    if (chart && chartContainerRef.current && autoResize) {
      const { width, height } = chartContainerRef.current.getBoundingClientRect();
      chart.resize(width, height);
    }
  }, [chart, autoResize]);

  // Initialize chart on mount
  useEffect(() => {
    if (chartContainerRef.current) {
      // Determine dimensions
      const containerWidth = width || chartContainerRef.current.clientWidth;
      const containerHeight = height || 400;

      // Create chart options
      const options = createChartOptions({
        width: containerWidth,
        height: containerHeight,
        theme,
        autoResize,
        ...chartOptions
      });

      // Create the chart
      const newChart = createChart(chartContainerRef.current, options);

      // Set crosshair mode
      newChart.applyOptions({
        crosshair: {
          mode: CrosshairMode.Normal,
        }
      });

      // Subscribe to events
      if (onCrosshairMove) {
        newChart.subscribeCrosshairMove(onCrosshairMove);
      }

      if (onVisibleTimeRangeChange) {
        newChart.timeScale().subscribeVisibleTimeRangeChange(onVisibleTimeRangeChange);
      }

      // Store chart instance
      setChart(newChart);

      // Notify when chart is ready
      if (onChartReady) {
        onChartReady(newChart);
      }

      // Set up resize observer for responsive sizing
      if (autoResize) {
        const observer = new ResizeObserver(() => {
          handleResize();
        });
        
        observer.observe(chartContainerRef.current);
        resizeObserverRef.current = observer;

        // Also listen to window resize for older browsers without ResizeObserver
        window.addEventListener('resize', handleResize);
      }

      // Cleanup on unmount
      return () => {
        if (onCrosshairMove && newChart) {
          newChart.unsubscribeCrosshairMove(onCrosshairMove);
        }

        if (onVisibleTimeRangeChange && newChart) {
          newChart.timeScale().unsubscribeVisibleTimeRangeChange(onVisibleTimeRangeChange);
        }

        if (resizeObserverRef.current && chartContainerRef.current) {
          resizeObserverRef.current.unobserve(chartContainerRef.current);
          resizeObserverRef.current.disconnect();
        }

        window.removeEventListener('resize', handleResize);
        cleanupChart(newChart);
      };
    }
  }, []);

  // Update chart when theme changes
  useEffect(() => {
    if (chart) {
      const options = createChartOptions({
        theme,
        ...chartOptions
      });

      chart.applyOptions(options);
    }
  }, [theme, chart, chartOptions]);

  return (
    <div 
      className={`chart-container ${className}`}
      ref={chartContainerRef}
      style={{ width: width || '100%', height: height || 400 }}
    >
      {children}
    </div>
  );
};

export default ChartContainer;