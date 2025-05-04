import React, { useRef, useEffect, useState } from 'react';
import { useTheme } from '../layouts/ThemeProvider';
import { OHLCVData } from '../../types/data';
import { Button } from '../common/Button';

import './ChartContainer.css';

interface CandlestickTradingViewProps {
  /** The OHLCV data to display */
  data?: OHLCVData;
  /** Chart width (defaults to container width) */
  width?: number;
  /** Chart height */
  height?: number;
  /** Whether to show volume */
  showVolume?: boolean;
  /** Title to display above the chart */
  title?: string;
  /** CSS class name for additional styling */
  className?: string;
  /** Whether to fit the chart content initially */
  fitContent?: boolean;
  /** Whether to automatically resize when window changes */
  autoResize?: boolean;
}

/**
 * CandlestickTradingView component
 * 
 * A candlestick chart using TradingView Lightweight Charts v4.1.1
 */
const CandlestickTradingView: React.FC<CandlestickTradingViewProps> = ({
  data,
  width,
  height = 400,
  showVolume = true,
  title = 'Candlestick Chart',
  className = '',
  fitContent = true,
  autoResize = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  // Add dimensions ref outside of the hook
  const dimensionsRef = useRef<{
    originalWidth: number;
    originalHeight: number;
    lastWidth: number;
    lastHeight: number;
  }>({
    originalWidth: 0,
    originalHeight: 0,
    lastWidth: 0,
    lastHeight: 0
  });
  const { theme } = useTheme();
  const [chartInstance, setChartInstance] = useState<any>(null);
  const [volumeVisible, setVolumeVisible] = useState<boolean>(showVolume);
  const [volumeSeries, setVolumeSeries] = useState<any>(null);
  const [candlestickSeries, setCandlestickSeries] = useState<any>(null);
  const [isLibraryLoaded, setIsLibraryLoaded] = useState<boolean>(false);

  // Create sample data if none provided
  const chartData = data || {
    dates: [],
    ohlcv: [],
    metadata: {
      symbol: 'SAMPLE',
      timeframe: '1D',
      start: '',
      end: '',
      points: 0
    }
  };

  // Function to format data for TradingView
  const formatCandlestickData = (data: OHLCVData) => {
    if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
      return [];
    }

    return data.dates.map((date, index) => {
      const [open, high, low, close, _volume] = data.ohlcv[index];
      
      return {
        time: typeof date === 'string' ? date : new Date(date).toISOString().split('T')[0],
        open,
        high,
        low,
        close,
      };
    });
  };

  // Function to format volume data for TradingView
  const formatVolumeData = (data: OHLCVData) => {
    if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
      return [];
    }

    return data.dates.map((date, index) => {
      const [open, _high, _low, close, volume] = data.ohlcv[index];
      
      return {
        time: typeof date === 'string' ? date : new Date(date).toISOString().split('T')[0],
        value: volume,
        color: close >= open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      };
    });
  };

  // Load the library if not already loaded
  useEffect(() => {
    if (typeof window.LightweightCharts !== 'undefined') {
      setIsLibraryLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
    script.async = true;
    script.onload = () => {
      console.log('Lightweight Charts v4.1.1 library loaded!');
      setIsLibraryLoaded(true);
    };
    script.onerror = (error) => {
      console.error('Error loading Lightweight Charts library:', error);
    };
    document.head.appendChild(script);

    return () => {
      // Remove script when component unmounts if it was added
      if (document.head.contains(script)) {
        document.head.removeChild(script);
      }
    };
  }, []);

  // Initialize chart when library is loaded and container is ready 
  useEffect(() => {
    if (!isLibraryLoaded || !containerRef.current) {
      return;
    }

    console.log('CandlestickTradingView initializing chart with props:', {
      width: width || 'container width',
      height: height,
      autoResize
    });

    // Use explicit dimensions - either from props or container
    const containerWidth = containerRef.current.clientWidth;
    const usedWidth = width || containerWidth;
    const usedHeight = height;
    
    console.log('Using exact dimensions:', usedWidth, 'x', usedHeight);
    
    // Store initial dimensions
    dimensionsRef.current = {
      originalWidth: usedWidth,
      originalHeight: usedHeight,
      lastWidth: usedWidth,
      lastHeight: usedHeight
    };

    // Initialize the chart with fixed dimensions
    const createdChart = initializeChart(usedWidth, usedHeight);
    
    // If autoResize is explicitly disabled or we're using a fixed width, skip resize handling
    if (!autoResize || width) {
      console.log('Auto-resize disabled, skipping resize handler setup');
      return () => {
        // Clean up chart instance on unmount
        if (chartInstance) {
          try {
            chartInstance.remove();
          } catch (e) {
            console.error('Error removing chart:', e);
          }
        }
      };
    }
    
    // Otherwise set up resize handling with debounce
    let resizeTimeout: NodeJS.Timeout | null = null;
    
    const handleResize = () => {
      // Skip if no container or chart
      if (!chartInstance || !containerRef.current) return;
      
      // Clear any pending resize
      if (resizeTimeout) {
        clearTimeout(resizeTimeout);
      }
      
      // Debounce resize
      resizeTimeout = setTimeout(() => {
        if (!containerRef.current || !chartInstance) return;
        
        const newWidth = containerRef.current.clientWidth;
        
        // Only resize if width changed significantly
        if (Math.abs(newWidth - dimensionsRef.current.lastWidth) > 5) { // Increased threshold
          console.log(`Resizing chart: ${dimensionsRef.current.lastWidth}px -> ${newWidth}px`);
          
          try {
            // Resize in one operation without applying options
            chartInstance.resize(newWidth, usedHeight);
            dimensionsRef.current.lastWidth = newWidth;
          } catch (e) {
            console.error('Error during resize:', e);
          }
        }
      }, 250); // Longer debounce period
    };
    
    // Add resize listener
    window.addEventListener('resize', handleResize);
    
    // Return cleanup function
    return () => {
      // Remove resize listener
      window.removeEventListener('resize', handleResize);
      
      // Clear timeout if any
      if (resizeTimeout) {
        clearTimeout(resizeTimeout);
      }
      
      // Remove chart instance
      if (chartInstance) {
        try {
          chartInstance.remove();
        } catch (e) {
          console.error('Error removing chart:', e);
        }
      }
    };
  }, [isLibraryLoaded, width, height, autoResize]);

  // Update chart data when data or series change
  useEffect(() => {
    if (!candlestickSeries || !data) return;

    const candleData = formatCandlestickData(data);
    candlestickSeries.setData(candleData);

    if (showVolume && volumeSeries) {
      const volumeData = formatVolumeData(data);
      volumeSeries.setData(volumeData);
    }

    if (fitContent && chartInstance) {
      chartInstance.timeScale().fitContent();
    }
  }, [data, candlestickSeries, volumeSeries, chartInstance, showVolume, fitContent]);

  // Update theme when it changes
  useEffect(() => {
    if (!chartInstance) return;

    const colors = theme === 'dark' 
      ? {
          background: '#151924',
          text: '#d1d4dc',
          grid: '#2a2e39',
        }
      : {
          background: '#ffffff',
          text: '#333333',
          grid: '#e6e6e6',
        };

    try {
      // Only update color-related options to avoid resize loops
      chartInstance.applyOptions({
        layout: { 
          background: { color: colors.background }, 
          textColor: colors.text 
        },
        grid: { 
          vertLines: { color: colors.grid }, 
          horzLines: { color: colors.grid } 
        },
        rightPriceScale: { borderColor: colors.grid },
        timeScale: { borderColor: colors.grid }
      });
      
      console.log('Theme updated to:', theme);
    } catch (e) {
      console.error('Error applying theme:', e);
    }
  }, [theme, chartInstance]);

  // Toggle volume visibility
  useEffect(() => {
    if (!chartInstance || !candlestickSeries) return;

    if (volumeVisible && !volumeSeries) {
      // Create volume series
      const volSeries = chartInstance.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });

      // Configure the price scale
      chartInstance.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });

      // Set data if available
      if (data) {
        const volumeData = formatVolumeData(data);
        volSeries.setData(volumeData);
      }

      setVolumeSeries(volSeries);
    } else if (!volumeVisible && volumeSeries) {
      // Remove volume series
      chartInstance.removeSeries(volumeSeries);
      setVolumeSeries(null);
    }
  }, [volumeVisible, chartInstance, volumeSeries, candlestickSeries, data]);

  const initializeChart = (chartWidth: number, chartHeight: number) => {
    if (!containerRef.current || !window.LightweightCharts) return null;

    try {
      // Ensure the container is empty
      containerRef.current.innerHTML = '';

      console.log(`Creating chart with fixed dimensions: ${chartWidth}px x ${chartHeight}px`);
      
      // Set up colors based on theme
      const colors = theme === 'dark' 
        ? {
            background: '#151924',
            text: '#d1d4dc',
            grid: '#2a2e39',
          }
        : {
            background: '#ffffff',
            text: '#333333',
            grid: '#e6e6e6',
          };

      // IMPORTANT: Create chart with FIXED width and height - don't use percentages or auto
      const chart = window.LightweightCharts.createChart(containerRef.current, {
        width: chartWidth,
        height: chartHeight,
        layout: {
          background: { color: colors.background },
          textColor: colors.text
        },
        grid: {
          vertLines: { color: colors.grid },
          horzLines: { color: colors.grid }
        },
        rightPriceScale: {
          borderColor: colors.grid,
        },
        timeScale: {
          borderColor: colors.grid,
          timeVisible: true,
        },
      });

      // Add candlestick series
      const candleSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        borderVisible: false,
      });
      setCandlestickSeries(candleSeries);

      // Set data if available
      if (data) {
        const candleData = formatCandlestickData(data);
        candleSeries.setData(candleData);
      }

      // Add volume series if enabled
      if (volumeVisible) {
        const volSeries = chart.addHistogramSeries({
          color: '#26a69a',
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'volume',
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
        });

        // Configure the price scale
        chart.priceScale('volume').applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
          borderVisible: false,
        });

        // Set data if available
        if (data) {
          const volumeData = formatVolumeData(data);
          volSeries.setData(volumeData);
        }

        setVolumeSeries(volSeries);
      }

      // Fit content if enabled - do this only once during initialization
      if (fitContent) {
        chart.timeScale().fitContent();
      }

      // Save chart instance
      setChartInstance(chart);
      console.log('Chart created successfully');
      
      return chart;
    } catch (error) {
      console.error('Error initializing chart:', error);
      return null;
    }
  };

  // Handle volume toggle
  const handleVolumeToggle = () => {
    setVolumeVisible(!volumeVisible);
  };

  // Handle fit content button
  const handleFitContent = () => {
    if (chartInstance) {
      chartInstance.timeScale().fitContent();
    }
  };

  return (
    <div className={`chart-wrapper ${className}`}>
      <div className="chart-header">
        <div className="chart-title">{title}</div>
        <div className="chart-symbol">
          {data?.metadata?.symbol} - {data?.metadata?.timeframe}
        </div>
        <div className="chart-toolbar" ref={toolbarRef}>
          <Button 
            variant="outline" 
            size="small" 
            onClick={handleVolumeToggle}
          >
            {volumeVisible ? 'Hide Volume' : 'Show Volume'}
          </Button>
          <Button 
            variant="outline" 
            size="small" 
            onClick={handleFitContent}
          >
            Fit All
          </Button>
        </div>
      </div>
      
      <div className="chart-legend" ref={legendRef}></div>
      
      <div 
        ref={containerRef} 
        className="chart-container-inner"
        style={{ 
          width: width ? `${width}px` : '100%', 
          height: `${height}px`,
          position: 'relative',
          overflow: 'hidden', // Prevent potential overflows
          boxSizing: 'border-box' // Ensure padding/borders don't affect dimensions
        }} 
      />
      
      {!isLibraryLoaded && (
        <div className="chart-loading">
          Loading chart library...
        </div>
      )}
      
      {!data?.dates?.length && (
        <div className="chart-no-data">
          No data available
        </div>
      )}
    </div>
  );
};

// Add the LightweightCharts type to the Window interface
declare global {
  interface Window {
    LightweightCharts: any;
  }
}

export default CandlestickTradingView;