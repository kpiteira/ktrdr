// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/features/charting/ChartPanel.tsx
import React, { useState, useRef, useEffect } from 'react';
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';
import { OHLCVData } from '../../api/types';
import { useTheme } from '../../components/layouts/ThemeProvider';

// Chart panel props interface
interface ChartPanelProps {
  data: OHLCVData;
  symbol: string;
  timeframe: string;
  height?: number;
  width?: number;
}

/**
 * ChartPanel component renders an OHLCV chart using Lightweight Charts
 * This component is responsible for rendering the chart and handling user interactions
 */
const ChartPanel: React.FC<ChartPanelProps> = ({
  data,
  symbol,
  timeframe,
  height = 500,
  width = 800,
}) => {
  // Use theme for chart styling
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // Chart references
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  
  // Create chart on mount
  useEffect(() => {
    if (!chartContainerRef.current) return;
    
    // Clear any existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRef.current = null;
    }
    
    // Create chart with theme-specific options
    const chart = createChart(chartContainerRef.current, {
      width: width,
      height: height,
      layout: {
        background: { type: 'solid', color: isDarkTheme ? '#1E1E1E' : '#FFFFFF' },
        textColor: isDarkTheme ? '#D9D9D9' : '#191919',
      },
      grid: {
        vertLines: { color: isDarkTheme ? '#2B2B43' : '#E6E6E6' },
        horzLines: { color: isDarkTheme ? '#2B2B43' : '#E6E6E6' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: timeframe.includes('m') || timeframe.includes('s'),
        borderColor: isDarkTheme ? '#2B2B43' : '#E6E6E6',
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
      },
    });
    
    // Create candlestick series
    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    });
    
    // Store refs
    chartRef.current = chart;
    seriesRef.current = series;
    
    // Handle resize
    const handleResize = () => {
      if (chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current?.clientWidth || width,
        });
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    // Cleanup on unmount
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, [isDarkTheme, height, width, timeframe]);
  
  // Update chart data when data changes
  useEffect(() => {
    if (!seriesRef.current || !data || !data.dates || !data.ohlcv || data.dates.length === 0) {
      return;
    }
    
    // Format data for chart
    const formattedData = data.dates.map((date, index) => {
      const [open, high, low, close] = data.ohlcv[index];
      
      // Convert date to timestamp if it's a string
      const time = typeof date === 'string' 
        ? new Date(date).getTime() / 1000 
        : date;
        
      return {
        time: time as number,
        open,
        high,
        low,
        close,
      };
    });
    
    // Set data and fit to content
    seriesRef.current.setData(formattedData);
    
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data]);
  
  return (
    <div className="chart-panel">
      <div 
        ref={chartContainerRef} 
        className="chart-container"
        style={{ height: `${height}px`, width: '100%' }}
      />
      <div className="chart-info mt-2 p-2 text-sm">
        <div className="flex justify-between">
          <span>{symbol} - {timeframe}</span>
          <span>{data?.dates?.length || 0} data points</span>
        </div>
      </div>
    </div>
  );
};

export default ChartPanel;