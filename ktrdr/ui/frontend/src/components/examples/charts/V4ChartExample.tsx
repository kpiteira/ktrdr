import React, { useEffect, useRef, useState } from 'react';
import { createChart } from 'lightweight-charts';
import { useTheme } from '../../layouts/ThemeProvider';
import { Card } from '../../common/Card';
import { Button } from '../../common/Button';
import { OHLCVData } from '../../../types/data';

/**
 * This component is specifically designed to work with Lightweight Charts v4.1.1
 */
const V4ChartExample: React.FC = () => {
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const candleSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);

  // Generate sample data
  const generateData = () => {
    const data: OHLCVData = {
      dates: [],
      ohlcv: [],
      metadata: {
        symbol: 'EXAMPLE',
        timeframe: '1d',
        start: '',
        end: '',
        points: 50
      }
    };

    const startTime = new Date(Date.now() - 50 * 24 * 60 * 60 * 1000);
    let currentPrice = 100;
    
    for (let i = 0; i < 50; i++) {
      const time = new Date(startTime.getTime() + i * 24 * 60 * 60 * 1000);
      const timeStr = time.toISOString().split('T')[0]; // YYYY-MM-DD format
      
      // Generate random price movement
      const change = (Math.random() - 0.5) * 10;
      const open = currentPrice;
      const close = currentPrice + change;
      const high = Math.max(open, close) + Math.random() * 5;
      const low = Math.min(open, close) - Math.random() * 5;
      const volume = Math.floor(Math.random() * 1000) + 100;
      
      data.dates.push(timeStr);
      data.ohlcv.push([open, high, low, close, volume]);
      
      currentPrice = close;
    }
    
    data.metadata.start = data.dates[0];
    data.metadata.end = data.dates[data.dates.length - 1];
    return data;
  };

  const [data, setData] = useState<OHLCVData>(generateData());

  // Format data for chart
  const formatCandleData = (data: OHLCVData) => {
    return data.dates.map((date, index) => {
      const [open, high, low, close] = data.ohlcv[index];
      return {
        time: date,
        open, high, low, close
      };
    });
  };

  const formatVolumeData = (data: OHLCVData) => {
    return data.dates.map((date, index) => {
      const [open, , , close, volume] = data.ohlcv[index];
      return {
        time: date,
        value: volume,
        color: close >= open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
      };
    });
  };

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Clear existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    }
    
    try {
      // Create chart
      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: 400,
        layout: {
          background: { type: 'solid', color: theme === 'dark' ? '#1E1E1E' : '#FFFFFF' },
          textColor: theme === 'dark' ? '#D9D9D9' : '#191919',
        },
        grid: {
          vertLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
          horzLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
          borderColor: theme === 'dark' ? '#2B2B43' : '#E6E6E6',
        },
        rightPriceScale: {
          borderColor: theme === 'dark' ? '#2B2B43' : '#E6E6E6',
        },
        crosshair: {
          mode: 1, // CrosshairMode.Normal
        },
      });
      
      // Save chart reference
      chartRef.current = chart;
      
      // Create series (THIS IS THE CORRECT WAY FOR v4.1.1)
      const candleSeries = chart.addLineSeries({
        priceScaleId: 'right',
        title: 'Candles',
        color: '#2196F3', 
        lineWidth: 2,
      });
      candleSeriesRef.current = candleSeries;
      
      const volumeSeries = chart.addHistogramSeries({
        priceScaleId: 'volume',
        title: 'Volume',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
      volumeSeriesRef.current = volumeSeries;
      
      // Configure volume scale
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });
      
      // Set data
      if (candleSeries && volumeSeries) {
        try {
          candleSeries.setData(formatCandleData(data));
          volumeSeries.setData(formatVolumeData(data));
          
          // Fit chart to content
          chart.timeScale().fitContent();
        } catch (error) {
          console.error('Error setting data:', error);
        }
      }
      
      // Handle window resize
      const handleResize = () => {
        if (containerRef.current && chart) {
          chart.resize(
            containerRef.current.clientWidth,
            containerRef.current.clientHeight
          );
        }
      };
      
      window.addEventListener('resize', handleResize);
      
      // Cleanup
      return () => {
        window.removeEventListener('resize', handleResize);
        if (chart) {
          chart.remove();
        }
      };
    } catch (error) {
      console.error('Failed to create chart:', error);
    }
  }, [theme, data]);
  
  // Generate new data
  const handleRegenerateData = () => {
    setData(generateData());
  };
  
  return (
    <Card title="Lightweight Charts v4.1.1 Example">
      <p style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem' }}>
        This example is specifically designed to work with v4.1.1
      </p>
      
      <div style={{ marginBottom: '1rem' }}>
        <Button onClick={handleRegenerateData}>
          Regenerate Data
        </Button>
      </div>
      
      <div 
        ref={containerRef} 
        style={{ 
          height: '400px', 
          width: '100%' 
        }}
      />
      
      <div style={{ marginTop: '1rem' }}>
        <h4>Data Summary:</h4>
        <p>
          Symbol: {data.metadata.symbol}, 
          Timeframe: {data.metadata.timeframe}, 
          Points: {data.ohlcv.length}
        </p>
        <p>
          Date Range: {data.metadata.start} to {data.metadata.end}
        </p>
      </div>
    </Card>
  );
};

export default V4ChartExample;