import React, { useEffect, useRef } from 'react';
// Direct import from the package
import { createChart } from 'lightweight-charts';

const MinimalChart: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    
    // Simple data
    const data = [
      { time: '2019-01-01', value: 32 },
      { time: '2019-01-02', value: 35 },
      { time: '2019-01-03', value: 37 },
      { time: '2019-01-04', value: 34 },
      { time: '2019-01-05', value: 38 },
      { time: '2019-01-06', value: 40 },
      { time: '2019-01-07', value: 39 },
      { time: '2019-01-08', value: 42 },
      { time: '2019-01-09', value: 41 },
      { time: '2019-01-10', value: 44 },
    ];

    // Create chart with minimal options
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth, 
      height: 300,
    });
    
    console.log('MinimalChart - Chart object:', chart);
    
    // Get available methods on chart
    console.log('MinimalChart - Chart methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(chart)));
    
    // Test if we can access the internal API
    if (chart['_internal_ChartApi'] && chart['_internal_ChartApi'].createSeries) {
      console.log('MinimalChart - Found internal API for creating series');
    }
    
    // Try to create series using any available method
    if (chart.addLineSeries) {
      // V4 API
      const series = chart.addLineSeries();
      series.setData(data);
      console.log('MinimalChart - Added series with V4 API');
    } else if (chart.createLine) { 
      // V5 API - new method
      const series = chart.createLine();
      series.setData(data);
      console.log('MinimalChart - Added series with V5 API (createLine)');
    } else {
      // No method found
      console.log('MinimalChart - No method found to create series');
      
      // Create a fallback visual element
      const container = containerRef.current;
      const overlay = document.createElement('div');
      overlay.style.position = 'absolute';
      overlay.style.top = '0';
      overlay.style.left = '0';
      overlay.style.right = '0';
      overlay.style.bottom = '0';
      overlay.style.background = 'white';
      overlay.style.display = 'flex';
      overlay.style.alignItems = 'center';
      overlay.style.justifyContent = 'center';
      overlay.style.color = 'red';
      overlay.textContent = 'Chart API methods not available';
      container.style.position = 'relative';
      container.appendChild(overlay);
    }
    
    return () => {
      chart.remove();
    };
  }, []);

  return (
    <div>
      <div ref={containerRef} style={{ width: '100%', height: '300px' }} />
    </div>
  );
};

export default MinimalChart;