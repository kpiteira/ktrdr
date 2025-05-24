import { useEffect, useRef, useState, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, UTCTimestamp } from 'lightweight-charts';
import { loadData } from '../api/endpoints/data';

interface BasicChartProps {
  width?: number;
  height?: number;
}

const BasicChart: FC<BasicChartProps> = ({ 
  width = 800, 
  height = 400 
}) => {
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Add a small delay to ensure the DOM element is mounted
    const timer = setTimeout(() => {
      if (!chartContainerRef.current) {
        return;
      }

    // Create the chart
    const chart = createChart(chartContainerRef.current, {
      width,
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        borderColor: '#cccccc',
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
    });

    // Add candlestick series using legacy API (v4 compatibility)
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

      // Load data
      loadChartData();
    }, 100); // 100ms delay

    // Cleanup function
    return () => {
      clearTimeout(timer);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, [width, height]);

  const loadChartData = async () => {
    try {
      setLoading(true);
      setError(null);
      // Load MSFT 1h data for 2025 only
      const endDate = new Date('2025-12-31');
      const startDate = new Date('2025-01-01');
      const response = await fetch('/api/v1/data/load', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: 'MSFT',
          timeframe: '1h',
          start_date: startDate.toISOString().split('T')[0],
          end_date: endDate.toISOString().split('T')[0]
        })
      });
      
      const responseData = await response.json();

      if (!responseData.success || !responseData.data || !responseData.data.dates || !responseData.data.ohlcv || responseData.data.dates.length === 0) {
        throw new Error('No data received from API');
      }

      const data = responseData.data;

      // Transform data to TradingView format
      const candlestickData: CandlestickData[] = data.dates.map((dateStr: string, index: number) => {
        const ohlcv = data.ohlcv[index];
        if (!ohlcv || ohlcv.length < 4) {
          throw new Error(`Invalid OHLCV data at index ${index}`);
        }

        return {
          time: (new Date(dateStr).getTime() / 1000) as UTCTimestamp,
          open: ohlcv[0],
          high: ohlcv[1],
          low: ohlcv[2],
          close: ohlcv[3],
        };
      });


      // Set data to chart
      if (seriesRef.current) {
        seriesRef.current.setData(candlestickData);
        
        // Fit chart to content
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
        }
      }

      setLoading(false);
    } catch (err) {
      console.error('[BasicChart] Error loading data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load chart data');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="chart-container">
        <div className="loading">Loading MSFT chart data...</div>
        <div 
          ref={chartContainerRef} 
          style={{ 
            width: `${width}px`, 
            height: `${height}px`,
            margin: '0 auto',
            display: 'none' // Hidden but still mounted for ref
          }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="chart-container">
        <div className="error">
          Error loading chart: {error}
          <br />
          <button 
            onClick={loadChartData}
            style={{ 
              marginTop: '1rem', 
              padding: '0.5rem 1rem',
              backgroundColor: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chart-container">
      <h3 style={{ margin: '0 0 1rem 0', color: '#333' }}>
        MSFT Hourly Chart (2025 Data)
      </h3>
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: `${width}px`, 
          height: `${height}px`,
          margin: '0 auto'
        }}
      />
    </div>
  );
};

export default BasicChart;