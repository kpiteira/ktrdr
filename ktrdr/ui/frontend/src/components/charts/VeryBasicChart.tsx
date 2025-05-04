import React, { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';

const VeryBasicChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // This is a diagnostic function to check the library
    const showLibInfo = () => {
      try {
        console.log("Lightweight Charts imported:", typeof createChart);
        
        // If this works, createChart is available
        if (typeof createChart === 'function') {
          console.log("createChart is a function");
        } else {
          console.log("createChart is not a function:", createChart);
        }
      } catch (e) {
        console.error("Error checking library:", e);
      }
    };

    // Run the diagnostic
    showLibInfo();

    if (chartContainerRef.current) {
      try {
        // Generate sample data
        const lineData = [];
        const startDate = new Date(2018, 0, 1);
        for (let i = 0; i < 50; i++) {
          const date = new Date(startDate);
          date.setDate(startDate.getDate() + i);
          lineData.push({
            time: date.toISOString().split('T')[0],
            value: Math.random() * 100 + 50
          });
        }

        // Try to render a basic line chart
        const container = chartContainerRef.current;
        container.innerHTML = ''; // Clear previous content

        // Try to create chart
        console.log("Creating chart...");
        const chart = createChart(container, {
          width: container.clientWidth,
          height: 300,
          layout: {
            background: { color: '#ffffff' },
            textColor: '#333333',
          }
        });
        console.log("Chart created:", chart);

        // Try different API approaches (v3, v4, v5)
        try {
          // Try V3/V4 addLineSeries API
          if (typeof chart.addLineSeries === 'function') {
            console.log("Using V3/V4 API: addLineSeries");
            const series = chart.addLineSeries();
            series.setData(lineData);
          } 
          // Try createLine from chart
          else if (typeof chart.createLine === 'function') {
            console.log("Using V5 API: chart.createLine");
            const series = chart.createLine();
            series.setData(lineData);
          }
          // Try importing createLine directly
          else if (typeof window['createLine'] === 'function') {
            console.log("Using V5 API: global createLine");
            const series = window['createLine'](chart);
            series.setData(lineData);
          }
          // Fallback to rendering a message
          else {
            console.log("No suitable API methods found on chart:", Object.keys(chart));
            container.innerHTML = `
              <div style="color: red; padding: 20px;">
                <p>Chart API methods not found.</p>
                <p>Available methods: ${Object.keys(chart).join(', ')}</p>
              </div>
            `;
          }

          chart.timeScale().fitContent();
        } catch (seriesError) {
          console.error("Error creating series:", seriesError);
          container.innerHTML = `
            <div style="color: red; padding: 20px;">
              <p>Error creating chart series: ${seriesError.message}</p>
            </div>
          `;
        }

        return () => {
          chart.remove();
        };
      } catch (error) {
        console.error("Error in chart component:", error);
        
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = `
            <div style="color: red; padding: 20px;">
              <p>Error rendering chart: ${error.message}</p>
            </div>
          `;
        }
      }
    }
  }, []);

  return (
    <div className="very-basic-chart">
      <div ref={chartContainerRef} style={{ width: '100%', height: '300px', border: '1px solid #ddd' }} />
    </div>
  );
};

export default VeryBasicChart;