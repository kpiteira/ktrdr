import { useEffect, useRef, useState, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, UTCTimestamp } from 'lightweight-charts';
import { loadData } from '../api/endpoints/data';

interface BasicChartProps {
  width?: number;
  height?: number;
  symbol: string;
  timeframe: string;
}

const BasicChart: FC<BasicChartProps> = ({ 
  width = 800, 
  height = 400,
  symbol,
  timeframe
}) => {
  console.log('[BasicChart] Props received:', { symbol, timeframe, width, height });
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataInfo, setDataInfo] = useState<{startDate: string, endDate: string, pointCount: number} | null>(null);

  useEffect(() => {
    console.log('[BasicChart] useEffect triggered with:', { symbol, timeframe, width, height });
    
    // Reset states when props change
    setLoading(true);
    setError(null);
    
    // Add a small delay to ensure the DOM element is mounted
    const timer = setTimeout(() => {
      if (!chartContainerRef.current) {
        console.log('[BasicChart] Container ref not available, skipping initialization');
        return;
      }

      console.log('[BasicChart] Initializing chart...');

      // Clean up any existing chart first
      if (chartRef.current) {
        console.log('[BasicChart] Cleaning up existing chart');
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
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

      console.log('[BasicChart] Chart created, loading data...');
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
  }, [width, height, symbol, timeframe]);

  const loadChartData = async () => {
    console.log('[BasicChart] loadChartData called for:', { symbol, timeframe });
    try {
      setLoading(true);
      setError(null);
      
      const actualTimeframe = (timeframe && timeframe !== 'undefined') ? timeframe : '1h';
      
      // Step 1: Get available data range for this symbol/timeframe
      console.log('[BasicChart] Getting data range for:', { symbol, timeframe: actualTimeframe });
      
      const rangeResponse = await fetch('/api/v1/data/range', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol,
          timeframe: actualTimeframe
        })
      });
      
      const rangeData = await rangeResponse.json();
      console.log('[BasicChart] Range response:', rangeData);
      
      if (!rangeData.success || !rangeData.data) {
        throw new Error(`No data range available for ${symbol} (${actualTimeframe})`);
      }
      
      const { start_date, end_date, point_count } = rangeData.data;
      console.log('[BasicChart] Available data:', { start_date, end_date, point_count });
      
      // Step 2: Calculate date range for last 100 points (or all if less than 100)
      const maxPoints = 100;
      let requestStartDate: string;
      let requestEndDate: string = end_date;
      
      if (point_count <= maxPoints) {
        // Use all available data
        requestStartDate = start_date;
        console.log('[BasicChart] Using all available data points:', point_count);
      } else {
        // Calculate approximate start date for last 100 points
        // This is a simple approach - for more accuracy we could calculate based on timeframe
        const endDateTime = new Date(end_date);
        const startDateTime = new Date(start_date);
        const totalDuration = endDateTime.getTime() - startDateTime.getTime();
        const pointDuration = totalDuration / point_count;
        const last100Duration = pointDuration * maxPoints;
        const requestStartDateTime = new Date(endDateTime.getTime() - last100Duration);
        requestStartDate = requestStartDateTime.toISOString().split('T')[0];
        console.log('[BasicChart] Using last ~100 points from:', requestStartDate);
      }
      
      // Step 3: Load the actual data
      console.log('[BasicChart] Making data request with:', { 
        symbol, 
        timeframe: actualTimeframe, 
        start_date: requestStartDate, 
        end_date: requestEndDate 
      });
      
      const response = await fetch('/api/v1/data/load', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol,
          timeframe: actualTimeframe,
          start_date: requestStartDate,
          end_date: requestEndDate
        })
      });
      
      const responseData = await response.json();
      console.log('[BasicChart] API response:', { 
        success: responseData.success, 
        hasData: !!responseData.data,
        dataKeys: responseData.data ? Object.keys(responseData.data) : 'none'
      });

      if (!responseData.success || !responseData.data || !responseData.data.dates || !responseData.data.ohlcv || responseData.data.dates.length === 0) {
        console.log('[BasicChart] Data validation failed:', responseData);
        throw new Error(`No data available for ${symbol} (${actualTimeframe} timeframe)`);
      }

      const data = responseData.data;
      console.log('[BasicChart] Data loaded successfully:', { 
        datesLength: data.dates.length, 
        ohlcvLength: data.ohlcv.length 
      });
      
      // Store data info for display
      if (data.dates.length > 0) {
        setDataInfo({
          startDate: data.dates[0],
          endDate: data.dates[data.dates.length - 1],
          pointCount: data.dates.length
        });
      }

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
        console.log('[BasicChart] Setting data to chart, candlestick points:', candlestickData.length);
        seriesRef.current.setData(candlestickData);
        
        // Fit chart to content
        if (chartRef.current) {
          chartRef.current.timeScale().fitContent();
          console.log('[BasicChart] Chart fitted to content');
        }
      } else {
        console.error('[BasicChart] No series reference available to set data');
      }

      console.log('[BasicChart] Loading complete, setting loading to false');
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
        <div className="loading">Loading {symbol} chart data...</div>
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
        {symbol} {timeframe?.toUpperCase() || 'Unknown'} Chart
        {dataInfo && (
          <span style={{ fontSize: '0.8em', color: '#666', fontWeight: 'normal' }}>
            {' '}({dataInfo.pointCount} points: {dataInfo.startDate} to {dataInfo.endDate})
          </span>
        )}
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