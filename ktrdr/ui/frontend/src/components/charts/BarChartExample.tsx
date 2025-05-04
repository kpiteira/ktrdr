import React, { useEffect, useRef } from 'react';

// Import the full library with ES Module syntax
import * as LightweightCharts from 'lightweight-charts';

const BarChartExample: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Sample data
  const data = [
    { time: '2018-10-19', open: 54.62, high: 55.50, low: 54.52, close: 54.90 },
    { time: '2018-10-22', open: 55.08, high: 55.27, low: 54.61, close: 54.98 },
    { time: '2018-10-23', open: 56.09, high: 57.47, low: 56.09, close: 57.21 },
    { time: '2018-10-24', open: 57.00, high: 58.44, low: 56.41, close: 57.42 },
    { time: '2018-10-25', open: 57.46, high: 57.63, low: 56.17, close: 56.43 },
    { time: '2018-10-26', open: 56.26, high: 56.62, low: 55.19, close: 55.51 },
    { time: '2018-10-29', open: 55.81, high: 57.15, low: 55.72, close: 56.48 },
    { time: '2018-10-30', open: 56.92, high: 58.80, low: 56.92, close: 58.18 },
    { time: '2018-10-31', open: 58.32, high: 58.32, low: 56.76, close: 57.09 },
    { time: '2018-11-01', open: 56.98, high: 57.28, low: 55.55, close: 56.05 },
    { time: '2018-11-02', open: 56.34, high: 57.08, low: 55.92, close: 56.63 },
  ];

  useEffect(() => {
    if (!chartContainerRef.current) return;
    
    // Clear any existing chart
    chartContainerRef.current.innerHTML = '';
    
    try {
      console.log('LightweightCharts library:', LightweightCharts);
      
      // Try direct method access
      if (typeof LightweightCharts === 'object' && typeof LightweightCharts.createChart === 'function') {
        console.log('Using LightweightCharts.createChart method');
        
        // Create the chart
        const chart = LightweightCharts.createChart(chartContainerRef.current, {
          width: chartContainerRef.current.clientWidth,
          height: 300,
          layout: {
            background: { color: '#ffffff' },
            textColor: '#333333',
          },
          timeScale: {
            timeVisible: true,
            borderColor: '#D1D4DC',
          }
        });
        
        // Log chart API
        console.log('Chart created:', chart);
        console.log('Chart methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(chart)));
        
        // Add a bar series
        try {
          // Try different potential APIs (depending on the library version)
          if (typeof chart.addBarSeries === 'function') {
            console.log('Using chart.addBarSeries method');
            const barSeries = chart.addBarSeries({
              upColor: '#26a69a',
              downColor: '#ef5350',
            });
            barSeries.setData(data);
          } else if (typeof chart.createBar === 'function') {
            console.log('Using chart.createBar method');
            const barSeries = chart.createBar();
            barSeries.setData(data);
          } else {
            console.log('No suitable method found for bar series');
            console.log('Available chart methods:', Object.keys(chart));
            
            // Try the line series as a fallback
            if (typeof chart.addLineSeries === 'function') {
              console.log('Falling back to line series');
              const lineSeries = chart.addLineSeries();
              const lineData = data.map(item => ({
                time: item.time,
                value: item.close
              }));
              lineSeries.setData(lineData);
            }
          }
          
          // Fit content
          chart.timeScale().fitContent();
        } catch (seriesError) {
          console.error('Error creating series:', seriesError);
        }
        
        // Resize handler
        const handleResize = () => {
          if (chartContainerRef.current) {
            chart.applyOptions({
              width: chartContainerRef.current.clientWidth
            });
          }
        };
        
        window.addEventListener('resize', handleResize);
        
        // Cleanup
        return () => {
          window.removeEventListener('resize', handleResize);
          chart.remove();
        };
      } else {
        console.error('LightweightCharts.createChart is not a function', LightweightCharts);
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = `
            <div style="color: red; padding: 20px;">
              <p>Chart library not properly loaded</p>
              <p>Available methods: ${LightweightCharts ? Object.keys(LightweightCharts).join(', ') : 'none'}</p>
            </div>
          `;
        }
      }
    } catch (error) {
      console.error('Error creating chart:', error);
      if (chartContainerRef.current) {
        chartContainerRef.current.innerHTML = `
          <div style="color: red; padding: 20px;">
            <p>Error rendering chart: ${error.message}</p>
          </div>
        `;
      }
    }
  }, []);

  return (
    <div>
      <h3>Bar Chart Example</h3>
      <div ref={chartContainerRef} style={{ width: '100%', height: '300px' }} />
    </div>
  );
};

export default BarChartExample;