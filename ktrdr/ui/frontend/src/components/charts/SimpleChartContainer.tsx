import React, { useRef, useEffect, useState } from 'react';
import { createChart } from 'lightweight-charts';
import { useTheme } from '../layouts/ThemeProvider';

interface SimpleChartContainerProps {
  width?: number;
  height?: number;
  className?: string;
}

const SimpleChartContainer: React.FC<SimpleChartContainerProps> = ({
  width,
  height = 400,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const [isChartCreated, setIsChartCreated] = useState(false);

  // Sample data
  const data = [
    { time: '2018-12-22', open: 75.16, high: 82.84, low: 36.16, close: 45.72 },
    { time: '2018-12-23', open: 45.12, high: 53.90, low: 45.12, close: 48.09 },
    { time: '2018-12-24', open: 60.71, high: 60.71, low: 53.39, close: 59.29 },
    { time: '2018-12-25', open: 68.26, high: 68.26, low: 59.04, close: 60.50 },
    { time: '2018-12-26', open: 67.71, high: 105.85, low: 66.67, close: 91.04 },
    { time: '2018-12-27', open: 91.04, high: 121.40, low: 82.70, close: 111.40 },
    { time: '2018-12-28', open: 111.51, high: 142.83, low: 103.34, close: 131.25 },
    { time: '2018-12-29', open: 131.33, high: 151.17, low: 77.68, close: 96.43 },
    { time: '2018-12-30', open: 106.33, high: 110.20, low: 90.39, close: 98.10 },
    { time: '2018-12-31', open: 109.87, high: 114.69, low: 85.66, close: 111.26 },
  ];

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear any existing content
    containerRef.current.innerHTML = '';

    // Get the container dimensions
    const containerWidth = width || containerRef.current.clientWidth;
    const containerHeight = height;

    try {
      console.log('Creating chart...');
      
      // Create new chart with v5 API
      const chart = createChart(containerRef.current, {
        width: containerWidth,
        height: containerHeight,
        layout: {
          background: { 
            type: 'solid', 
            color: theme === 'dark' ? '#1E1E1E' : '#FFFFFF' 
          },
          textColor: theme === 'dark' ? '#D9D9D9' : '#191919',
        },
        grid: {
          vertLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
          horzLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        },
      });

      console.log('Chart methods:', Object.keys(chart));
      
      // Add series with v5 API
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: theme === 'dark' ? '#26a69a' : '#26a69a',
        downColor: theme === 'dark' ? '#ef5350' : '#ef5350',
        wickUpColor: theme === 'dark' ? '#26a69a' : '#26a69a',
        wickDownColor: theme === 'dark' ? '#ef5350' : '#ef5350',
      });
      
      // Set data
      candlestickSeries.setData(data);
      
      // Add volume series with v5 API (in a separate pane)
      const volumeSeries = chart.addHistogramSeries({
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
      
      // Sample volume data
      const volumeData = data.map(item => ({
        time: item.time,
        value: Math.random() * 200 + 100,
        color: item.close >= item.open ? '#26a69a' : '#ef5350',
      }));
      
      volumeSeries.setData(volumeData);
      
      // Configure the price scale
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });
      
      // Fit content
      chart.timeScale().fitContent();
      
      // Set up resize handler
      const handleResize = () => {
        if (containerRef.current) {
          const { width } = containerRef.current.getBoundingClientRect();
          chart.applyOptions({ width });
        }
      };
      
      // Add resize listener
      window.addEventListener('resize', handleResize);
      
      setIsChartCreated(true);
      console.log('Chart created successfully');
      
      // Cleanup
      return () => {
        window.removeEventListener('resize', handleResize);
        chart.remove();
      };
    } catch (error) {
      console.error('Error creating chart:', error);
    }
  }, [width, height, theme]);

  return (
    <div className={`simple-chart-container ${className}`}>
      <div 
        ref={containerRef} 
        style={{ width: width || '100%', height }}
      />
      {!isChartCreated && (
        <div className="chart-loading">Loading chart...</div>
      )}
    </div>
  );
};

export default SimpleChartContainer;