import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { useTheme } from '../../app/ThemeProvider';
import { CrosshairContainer, CrosshairData } from './CrosshairInfo';
import { ChartToolbar, ChartOptions, ChartCustomizableOptions } from './ChartControls';
import { LegendContainer, LegendItemData } from './ChartLegend';
import { OHLCVData } from '../../../types/data';
import './CandlestickChart.css';

export interface CandlestickChartProps {
  /** OHLCV data for the chart */
  data: OHLCVData;
  /** Height of the chart in pixels */
  height?: number;
  /** Width of the chart in pixels, defaults to container width */
  width?: number;
  /** Chart title */
  title?: string;
  /** Whether to show volume */
  showVolume?: boolean;
  /** Whether to fit content on load and data change */
  fitContent?: boolean;
  /** Whether to resize the chart when container size changes */
  autoResize?: boolean;
  /** Initial chart options */
  initialOptions?: ChartCustomizableOptions;
  /** Callback when crosshair position changes */
  onCrosshairMove?: (data: CrosshairData | null) => void;
  /** Callback when the chart is initialized */
  onChartInit?: (chart: any) => void;
  /** CSS class name for additional styling */
  className?: string;
  /** Additional padding at the bottom of the chart (in pixels) */
  bottomPadding?: number;
}

/**
 * CandlestickChart component
 * 
 * Advanced chart component for displaying OHLCV data with interactive features
 */
const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  height = 400,
  width,
  title,
  showVolume = true,
  fitContent = true,
  autoResize = true,
  initialOptions,
  onCrosshairMove,
  onChartInit,
  className = '',
  bottomPadding = 150 // Increased default bottom padding
}) => {
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const chartInstanceRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  
  // Calculate the actual chart height (leaving space for other elements)
  const chartHeight = height;
  // Calculate the total container height with padding
  const totalHeight = height + bottomPadding;
  
  // State
  const [crosshairData, setCrosshairData] = useState<CrosshairData | null>(null);
  const [isCrosshairVisible, setIsCrosshairVisible] = useState<boolean>(false);
  const [legendItems, setLegendItems] = useState<LegendItemData[]>([]);
  const [isOptionsVisible, setIsOptionsVisible] = useState<boolean>(false);
  const [chartOptions, setChartOptions] = useState<ChartCustomizableOptions>(initialOptions || {
    showGrid: true,
    showVolume: showVolume,
    upColor: isDarkTheme ? '#26a69a' : '#26a69a',
    downColor: isDarkTheme ? '#ef5350' : '#ef5350',
    wickUpColor: isDarkTheme ? '#26a69a' : '#26a69a',
    wickDownColor: isDarkTheme ? '#ef5350' : '#ef5350',
  });
  
  // Memoize the library loading state to avoid re-renders
  const [isLightweightChartsLoaded, setIsLightweightChartsLoaded] = useState<boolean>(
    typeof window !== 'undefined' && typeof window.LightweightCharts !== 'undefined'
  );
  
  // Format OHLCV data for chart (memoized)
  const formatCandlestickData = useCallback((ohlcvData: OHLCVData) => {
    if (!ohlcvData || !ohlcvData.dates || !ohlcvData.ohlcv || ohlcvData.dates.length !== ohlcvData.ohlcv.length) {
      console.error('Invalid OHLCV data');
      return [];
    }
    
    return ohlcvData.dates.map((date, index) => {
      const [open, high, low, close, volume] = ohlcvData.ohlcv[index];
      return {
        time: typeof date === 'string' ? date : new Date(date).toISOString().split('T')[0],
        open,
        high, 
        low,
        close
      };
    });
  }, []);
  
  // Format volume data for chart (memoized)
  const formatVolumeData = useCallback((ohlcvData: OHLCVData) => {
    if (!ohlcvData || !ohlcvData.dates || !ohlcvData.ohlcv || ohlcvData.dates.length !== ohlcvData.ohlcv.length) {
      console.error('Invalid OHLCV data');
      return [];
    }
    
    return ohlcvData.dates.map((date, index) => {
      const [open, high, low, close, volume] = ohlcvData.ohlcv[index];
      const isUp = close >= open;
      return {
        time: typeof date === 'string' ? date : new Date(date).toISOString().split('T')[0],
        value: volume,
        color: isUp ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
      };
    });
  }, []);
  
  // Handle chart resize with debouncing
  const handleResize = useCallback(() => {
    if (!chartInstanceRef.current || !chartContainerRef.current) return;
    
    if (resizeTimeoutRef.current) {
      clearTimeout(resizeTimeoutRef.current);
    }
    
    resizeTimeoutRef.current = setTimeout(() => {
      try {
        const containerWidth = chartContainerRef.current?.clientWidth || 0;
        const newWidth = width || containerWidth;
        
        if (chartInstanceRef.current) {
          chartInstanceRef.current.resize(newWidth, height);
        }
      } catch (error) {
        console.error('Error resizing chart:', error);
      }
    }, 100);
  }, [height, width]);
  
  // Memoized crosshair handler to prevent recreation on every render
  const handleCrosshairMove = useCallback((param: any) => {
    if (!param || !param.point || param.point.x === undefined || param.point.y === undefined) {
      setIsCrosshairVisible(false);
      setCrosshairData(null);
      
      if (onCrosshairMove) {
        onCrosshairMove(null);
      }
      
      // Reset legend values - using a callback to avoid stale state
      setLegendItems(prevItems => 
        prevItems.map(item => ({
          ...item,
          value: '-'
        }))
      );
      
      return;
    }
    
    setIsCrosshairVisible(true);
    
    if (!param.time) {
      return;
    }
    
    try {
      // Find data point at crosshair
      const seriesData: any = {};
      const prices: any = {};
      
      if (candlestickSeriesRef.current) {
        const candleData = param.seriesData.get(candlestickSeriesRef.current);
        if (candleData) {
          seriesData.candle = candleData;
          prices.candle = {
            value: candleData.close,
            color: chartOptions.upColor || '#26a69a',
            seriesName: 'Price'
          };
        }
      }
      
      if (volumeSeriesRef.current) {
        const volData = param.seriesData.get(volumeSeriesRef.current);
        if (volData) {
          seriesData.volume = volData;
          prices.volume = {
            value: volData.value,
            color: 'rgba(150, 150, 150, 0.8)',
            seriesName: 'Volume'
          };
        }
      }
      
      // Create crosshair data object
      const newCrosshairData: CrosshairData = {
        time: param.time,
        prices,
        additionalData: seriesData
      };
      
      setCrosshairData(newCrosshairData);
      
      if (onCrosshairMove) {
        onCrosshairMove(newCrosshairData);
      }
      
      // Only update legend items if we actually have candle data and it differs from current
      if (seriesData.candle) {
        const { open, high, low, close } = seriesData.candle;
        
        // Create new legend items without triggering unnecessary re-renders
        const newLegendItems = [
          {
            id: 'o',
            label: 'Open',
            value: open,
            color: chartOptions.upColor || '#26a69a',
            isActive: true
          },
          {
            id: 'h',
            label: 'High',
            value: high,
            color: chartOptions.upColor || '#26a69a',
            isActive: true
          },
          {
            id: 'l',
            label: 'Low',
            value: low,
            color: chartOptions.downColor || '#ef5350',
            isActive: true
          },
          {
            id: 'c',
            label: 'Close',
            value: close,
            color: close >= open ? (chartOptions.upColor || '#26a69a') : (chartOptions.downColor || '#ef5350'),
            isActive: true
          }
        ];
        
        // Add volume if it exists
        if (seriesData.volume) {
          newLegendItems.push({
            id: 'v',
            label: 'Volume',
            value: seriesData.volume.value.toLocaleString(),
            color: 'rgba(150, 150, 150, 0.8)',
            isActive: true
          });
        }
        
        // Use a reference comparison to determine if we need to update state
        setLegendItems(prev => {
          // Simple check if the data has changed
          const hasChanged = prev.some((item, idx) => 
            idx < newLegendItems.length && 
            (item.value !== newLegendItems[idx].value || 
             item.color !== newLegendItems[idx].color)
          );
          
          return hasChanged ? newLegendItems : prev;
        });
      }
    } catch (error) {
      console.error('Error in crosshair handler:', error);
    }
  }, [chartOptions.upColor, chartOptions.downColor, onCrosshairMove]);
  
  // Load Lightweight Charts library if not already loaded
  useEffect(() => {
    // Skip if already loaded
    if (typeof window !== 'undefined' && typeof window.LightweightCharts !== 'undefined') {
      setIsLightweightChartsLoaded(true);
      return;
    }
    
    console.log('Loading Lightweight Charts library');
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
    script.async = true;
    script.onload = () => {
      console.log('Lightweight Charts loaded successfully');
      setIsLightweightChartsLoaded(true);
    };
    document.head.appendChild(script);
    
    return () => {
      // We don't remove the script on unmount as it may be used by other components
    };
  }, []);
  
  // Create or recreate chart when theme/options/dimensions change
  useEffect(() => {
    if (!isLightweightChartsLoaded || !chartContainerRef.current) {
      return;
    }
    
    // Prevent chart recreation if one already exists to avoid update cycles
    // Only recreate if critical properties have changed
    const shouldRecreateChart = !chartInstanceRef.current || 
      // These are the conditions that require a complete chart recreation
      isDarkTheme !== (chartContainerRef.current?.className || '').includes('dark-theme');
    
    if (!shouldRecreateChart) {
      // Just update chart options without full recreation
      try {
        if (chartInstanceRef.current) {
          // Update candlestick series colors
          if (candlestickSeriesRef.current) {
            candlestickSeriesRef.current.applyOptions({
              upColor: chartOptions.upColor || '#26a69a',
              downColor: chartOptions.downColor || '#ef5350',
              wickUpColor: chartOptions.wickUpColor || '#26a69a',
              wickDownColor: chartOptions.wickDownColor || '#ef5350',
            });
          }
          
          // Update grid visibility
          chartInstanceRef.current.applyOptions({
            grid: {
              vertLines: { visible: chartOptions.showGrid !== false },
              horzLines: { visible: chartOptions.showGrid !== false },
            },
          });
          
          // Update dimensions if needed
          const containerWidth = chartContainerRef.current.clientWidth;
          const chartWidth = width || containerWidth;
          chartInstanceRef.current.resize(chartWidth, height);
          
          return; // Skip the rest of the recreation logic
        }
      } catch (error) {
        console.error('Error updating chart options:', error);
        // If updating fails, we'll fall through to recreate the chart
      }
    }
    
    try {
      // Clean up previous chart if it exists
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.unsubscribeCrosshairMove(handleCrosshairMove);
          chartInstanceRef.current.remove();
          chartInstanceRef.current = null;
          candlestickSeriesRef.current = null;
          volumeSeriesRef.current = null;
        } catch (error) {
          console.error('Error removing previous chart:', error);
        }
      }
      
      // Calculate width
      const containerWidth = chartContainerRef.current.clientWidth;
      const chartWidth = width || containerWidth;
      
      // Set up colors based on theme
      const colors = isDarkTheme
        ? {
            background: '#1E1E1E',
            text: '#D9D9D9',
            grid: '#2B2B43',
          }
        : {
            background: '#FFFFFF',
            text: '#191919',
            grid: '#E6E6E6',
          };
      
      // Create chart
      const newChart = window.LightweightCharts.createChart(chartContainerRef.current, {
        width: chartWidth,
        height: height,
        layout: {
          background: { type: 'solid', color: colors.background },
          textColor: colors.text,
        },
        grid: {
          vertLines: { color: colors.grid, visible: chartOptions.showGrid !== false },
          horzLines: { color: colors.grid, visible: chartOptions.showGrid !== false },
        },
        crosshair: {
          mode: window.LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
          borderColor: colors.grid,
        },
        timeScale: {
          borderColor: colors.grid,
          timeVisible: true,
          secondsVisible: false,
        },
      });
      
      // Store chart instance in ref
      chartInstanceRef.current = newChart;
      
      // Subscribe to crosshair move
      newChart.subscribeCrosshairMove(handleCrosshairMove);
      
      // Add candlestick series
      const newCandlestickSeries = newChart.addCandlestickSeries({
        upColor: chartOptions.upColor || '#26a69a',
        downColor: chartOptions.downColor || '#ef5350',
        wickUpColor: chartOptions.wickUpColor || '#26a69a',
        wickDownColor: chartOptions.wickDownColor || '#ef5350',
        borderVisible: false,
      });
      
      // Store series in ref
      candlestickSeriesRef.current = newCandlestickSeries;
      
      // Format and set candlestick data
      const formattedData = formatCandlestickData(data);
      newCandlestickSeries.setData(formattedData);
      
      // Add volume series if needed
      if (showVolume) {
        const newVolumeSeries = newChart.addHistogramSeries({
          color: 'rgba(38, 166, 154, 0.5)',
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'volume',
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
        });
        
        // Store volume series in ref
        volumeSeriesRef.current = newVolumeSeries;
        
        // Format and set volume data
        const volumeData = formatVolumeData(data);
        newVolumeSeries.setData(volumeData);
        
        // Configure the price scale
        newChart.priceScale('volume').applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
          borderVisible: false,
        });
      }
      
      // Initial legend setup
      setLegendItems([
        {
          id: 'o',
          label: 'Open',
          value: '-',
          color: chartOptions.upColor || '#26a69a',
          isActive: true
        },
        {
          id: 'h',
          label: 'High',
          value: '-',
          color: chartOptions.upColor || '#26a69a',
          isActive: true
        },
        {
          id: 'l',
          label: 'Low',
          value: '-',
          color: chartOptions.downColor || '#ef5350',
          isActive: true
        },
        {
          id: 'c',
          label: 'Close',
          value: '-',
          color: chartOptions.upColor || '#26a69a',
          isActive: true
        },
        ...(showVolume ? [{
          id: 'v',
          label: 'Volume',
          value: '-',
          color: 'rgba(150, 150, 150, 0.8)',
          isActive: true
        }] : [])
      ]);
      
      // Fit content if required
      if (fitContent) {
        newChart.timeScale().fitContent();
      }
      
      // Notify parent component
      if (onChartInit) {
        onChartInit(newChart);
      }
      
      // Set up resize observer if auto resize is enabled
      if (autoResize) {
        if (resizeObserverRef.current) {
          resizeObserverRef.current.disconnect();
        }
        
        resizeObserverRef.current = new ResizeObserver(handleResize);
        resizeObserverRef.current.observe(chartContainerRef.current);
      }
    } catch (error) {
      console.error('Error initializing chart:', error);
    }
  }, [
    isLightweightChartsLoaded,
    isDarkTheme,
    height,
    width,
    showVolume,
    chartOptions.showGrid,
    chartOptions.upColor,
    chartOptions.downColor,
    chartOptions.wickUpColor,
    chartOptions.wickDownColor,
    handleCrosshairMove,
    handleResize,
    fitContent,
    autoResize,
    onChartInit,
    formatCandlestickData,
    formatVolumeData,
    data, // It's okay to include data here since we'll only recreate on critical changes
  ]);
  
  // Update data when it changes - using a separate effect for data updates only
  useEffect(() => {
    if (!chartInstanceRef.current) return;
    
    try {
      // Update candlestick data
      if (candlestickSeriesRef.current) {
        const formattedData = formatCandlestickData(data);
        candlestickSeriesRef.current.setData(formattedData);
      }
      
      // Update volume data if it exists
      if (volumeSeriesRef.current) {
        const volumeData = formatVolumeData(data);
        volumeSeriesRef.current.setData(volumeData);
      }
      
      // Fit content if required
      if (fitContent && chartInstanceRef.current) {
        chartInstanceRef.current.timeScale().fitContent();
      }
    } catch (error) {
      console.error('Error updating chart data:', error);
    }
  }, [data, formatCandlestickData, formatVolumeData, fitContent]);
  
  // Handle options change
  const handleOptionsChange = useCallback((newOptions: ChartCustomizableOptions) => {
    setChartOptions(newOptions);
  }, []);
  
  // Handle legend item click
  const handleLegendItemClick = useCallback((itemId: string) => {
    // Toggle item active state using a functional update
    setLegendItems(prevItems =>
      prevItems.map(item => 
        item.id === itemId
          ? { ...item, isActive: !item.isActive }
          : item
      )
    );
  }, []);
  
  return (
    <div 
      className={`candlestick-chart-container ${isDarkTheme ? 'dark-theme' : 'light-theme'} ${className}`}
      style={{ 
        height: `${totalHeight}px`, 
        marginBottom: '30px', 
        position: 'relative',
        overflow: 'visible', // Allow content to overflow for crosshair display
        paddingBottom: `${bottomPadding}px`,
        boxSizing: 'content-box' // Ensure padding is added to the specified height
      }}
    >
      {title && <div className="chart-title">{title}</div>}
      
      <div className="chart-controls">
        <ChartToolbar
          chart={chartInstanceRef.current}
          showOptionsButton={true}
          onOptionsClick={() => setIsOptionsVisible(!isOptionsVisible)}
        />
      </div>
      
      <div className="chart-content" style={{ 
        position: 'relative', 
        height: `${chartHeight}px`,
        marginBottom: '20px' // Add space between chart and legend
      }}>
        <div 
          className="chart-wrapper" 
          ref={chartContainerRef}
          style={{ 
            height: '100%',
            width: '100%', 
            position: 'relative'
          }}
        >
          {isCrosshairVisible && crosshairData && (
            <CrosshairContainer
              data={crosshairData}
              visible={isCrosshairVisible}
              formatTime={(time) => {
                if (typeof time === 'string') {
                  return time;
                }
                return new Date(time).toLocaleDateString();
              }}
            />
          )}
        </div>
      </div>
      
      <div style={{ position: 'absolute', bottom: '10px', left: '0', right: '0' }}>
        <LegendContainer
          items={legendItems}
          position="top"
          onItemClick={handleLegendItemClick}
        />
      </div>
      
      <ChartOptions
        chart={chartInstanceRef.current}
        isVisible={isOptionsVisible}
        onVisibilityChange={setIsOptionsVisible}
        defaultOptions={chartOptions}
        onOptionsChange={handleOptionsChange}
      />
    </div>
  );
};

// Add a TypeScript interface for the LightweightCharts global
declare global {
  interface Window {
    LightweightCharts: any;
  }
}

export default CandlestickChart;