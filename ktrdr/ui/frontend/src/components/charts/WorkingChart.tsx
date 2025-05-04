import React, { useRef, useEffect, useState } from 'react';
import { useTheme } from '../layouts/ThemeProvider';

const WorkingChart: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const [chartInstance, setChartInstance] = useState<any>(null);

  // Sample data for demonstration
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
    // Ensure the container exists and the library is loaded
    if (!containerRef.current || typeof window.LightweightCharts === 'undefined') {
      console.log('Library or container not ready');

      // Create a script tag to load the library if it's not loaded
      if (typeof window.LightweightCharts === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
        script.async = true;
        script.onload = () => {
          console.log('Lightweight Charts library loaded!');
          initializeChart();
        };
        document.head.appendChild(script);
      }
      return;
    }

    initializeChart();

    return () => {
      if (chartInstance) {
        try {
          chartInstance.remove();
        } catch (e) {
          console.error('Error removing chart:', e);
        }
      }
    };
  }, []);

  // Update chart theme when theme changes
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
  }, [theme, chartInstance]);

  const initializeChart = () => {
    if (!containerRef.current || !window.LightweightCharts) return;

    try {
      console.log('Initializing chart with LightweightCharts v4');

      // Clear previous chart if any
      containerRef.current.innerHTML = '';

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

      // Create chart with version 4 API
      const chart = window.LightweightCharts.createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: 400,
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
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        borderVisible: false,
      });

      // Set data
      candlestickSeries.setData(data);

      // Add volume series
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

      // Add resize handler with proper logic for both expanding and shrinking
      const handleResize = () => {
        if (containerRef.current) {
          const containerWidth = containerRef.current.clientWidth;
          // Both methods are needed for proper resizing
          chart.resize(containerWidth, 400);
          chart.applyOptions({
            width: containerWidth,
          });
        }
      };

      // Use ResizeObserver for more accurate sizing
      const resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      
      if (containerRef.current) {
        resizeObserver.observe(containerRef.current);
      }
      
      // Also add window resize listener as fallback
      window.addEventListener('resize', handleResize);
      
      // Make sure to clean up both event listeners
      return () => {
        resizeObserver.disconnect();
        window.removeEventListener('resize', handleResize);
        chart.remove();
      };

      // Save chart instance
      setChartInstance(chart);
      console.log('Chart created successfully');
    } catch (error) {
      console.error('Error initializing chart:', error);
    }
  };

  return (
    <div className="working-chart">
      {/* Load the library script directly in the component */}
      <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js" />
      
      <div 
        ref={containerRef} 
        style={{ 
          width: '100%', 
          height: '400px', 
          position: 'relative'
        }} 
      />
    </div>
  );
};

// Add the LightweightCharts type to the Window interface
declare global {
  interface Window {
    LightweightCharts: any;
  }
}

export default WorkingChart;