import React, { useEffect, useRef } from 'react';
import * as LightweightCharts from 'lightweight-charts';

const BasicChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Sample data
  const sampleData = [
    { time: '2018-12-22', value: 32.51 },
    { time: '2018-12-23', value: 31.11 },
    { time: '2018-12-24', value: 27.02 },
    { time: '2018-12-25', value: 27.32 },
    { time: '2018-12-26', value: 25.17 },
    { time: '2018-12-27', value: 28.89 },
    { time: '2018-12-28', value: 25.46 },
    { time: '2018-12-29', value: 23.92 },
    { time: '2018-12-30', value: 22.68 },
    { time: '2018-12-31', value: 22.67 },
  ];

  useEffect(() => {
    if (chartContainerRef.current) {
      // Clear any existing chart
      chartContainerRef.current.innerHTML = '';

      try {
        // Importing directly via namespace
        console.log('LightweightCharts available methods:', Object.keys(LightweightCharts));
        
        // Create chart using namespace
        const chart = LightweightCharts.createChart(chartContainerRef.current, {
          width: chartContainerRef.current.clientWidth,
          height: 300,
        });
        
        console.log('Chart created with API:', chart);
        
        // Create a line series
        try {
          // Version 5 API uses createLine method
          if (typeof LightweightCharts.createLine === 'function') {
            console.log('Using createLine method');
            // Using the V5 API
            const lineSeries = chart.createLine();
            lineSeries.setData(sampleData);
          } else if (typeof chart.addLineSeries === 'function') {
            console.log('Using addLineSeries method');
            // Using the pre-V5 API
            const lineSeries = chart.addLineSeries();
            lineSeries.setData(sampleData);
          } else {
            console.error('No valid series creation method found');
            console.log('Available chart methods:', Object.keys(chart));
          }
          
          // Fit content
          chart.timeScale().fitContent();
          
          console.log('Chart created successfully');
        } catch (seriesError) {
          console.error('Error creating series:', seriesError);
        }
        
        // Clean up on unmount
        return () => {
          chart.remove();
        };
      } catch (error) {
        console.error('Error creating chart:', error);
      }
    }
  }, []);

  return (
    <div>
      <h3>Basic Line Chart</h3>
      <div ref={chartContainerRef} style={{ width: '100%', height: '300px' }} />
    </div>
  );
};

export default BasicChart;