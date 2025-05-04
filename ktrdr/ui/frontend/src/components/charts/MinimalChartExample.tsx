import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

/**
 * Minimal chart example using Lightweight Charts v4.1.1
 * This component is designed as a minimal test to verify the correct API usage
 */
const MinimalChartExample: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Clean up function to remove chart on unmount
    let cleanup = () => {};
    
    try {
      // Create chart with basic options
      const chart = createChart(containerRef.current, {
        width: 600,
        height: 300,
        layout: {
          background: { color: '#ffffff' },
          textColor: '#333333',
        },
        grid: {
          vertLines: { color: '#f0f0f0' },
          horzLines: { color: '#f0f0f0' },
        },
        timeScale: {
          timeVisible: true,
          secondsVisible: false,
        }
      });
      
      // Sample data
      const candleData = [
        { time: '2020-01-01', open: 100, high: 110, low: 90, close: 105 },
        { time: '2020-01-02', open: 105, high: 115, low: 100, close: 110 },
        { time: '2020-01-03', open: 110, high: 120, low: 105, close: 115 },
        { time: '2020-01-04', open: 115, high: 125, low: 110, close: 120 },
        { time: '2020-01-05', open: 120, high: 130, low: 115, close: 125 },
      ];
      
      // Create series - using correct v4.1.1 syntax
      const mainSeries = chart.addBarSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
      });
      
      // Set data
      mainSeries.setData(candleData);
      
      // Fit content to view
      chart.timeScale().fitContent();
      
      // Set up cleanup
      cleanup = () => {
        chart.remove();
      };
    } catch (error) {
      console.error('Error creating minimal chart:', error);
    }
    
    return cleanup;
  }, []);
  
  return (
    <div>
      <h3>Minimal Chart Example (v4.1.1)</h3>
      <div ref={containerRef}></div>
    </div>
  );
};

export default MinimalChartExample;