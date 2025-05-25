import { useEffect, useRef, useState, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, UTCTimestamp, LineData } from 'lightweight-charts';

export interface SMAData {
  id: string;
  period: number;
  data: LineData[];
  color: string;
  visible: boolean;
}

interface BasicChartProps {
  width?: number;
  height?: number;
  symbol: string;
  timeframe: string;
  smaToAdd?: number | null;
  onSMAAdded?: () => void;
  smaToRemove?: string | null;
  onSMARemoved?: () => void;
  smaToToggle?: string | null;
  onSMAToggled?: () => void;
  onSMAListChange?: (smaList: SMAData[]) => void;
  onDateRangeChange?: (dateRange: {start: string, end: string} | null) => void;
  smaList?: SMAData[];
}

const BasicChart: FC<BasicChartProps> = ({ 
  width = 800, 
  height = 400,
  symbol,
  timeframe,
  smaToAdd,
  onSMAAdded,
  smaToRemove,
  onSMARemoved,
  smaToToggle,
  onSMAToggled,
  onSMAListChange,
  onDateRangeChange,
  smaList: propsSmaList
}) => {
  console.log('[BasicChart] Props received:', { symbol, timeframe, width, height, smaToAdd, smaToRemove, smaToToggle });
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const smaSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const previousSmaListRef = useRef<SMAData[]>([]);
  const updatingFromPropsRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dataInfo, setDataInfo] = useState<{startDate: string, endDate: string, pointCount: number} | null>(null);
  const [smaList, setSmaList] = useState<SMAData[]>([]);
  const [dateRange, setDateRange] = useState<{start: string, end: string} | null>(null);

  // Handle SMA addition requests
  useEffect(() => {
    if (smaToAdd) {
      if (!smaList.some(sma => sma.period === smaToAdd)) {
        loadSMAData(smaToAdd).then(() => {
          if (onSMAAdded) {
            onSMAAdded();
          }
        });
      } else {
        // Indicator already exists, just reset the loading state
        console.log(`[BasicChart] SMA(${smaToAdd}) already exists, skipping`);
        if (onSMAAdded) {
          onSMAAdded();
        }
      }
    }
  }, [smaToAdd]);

  // Handle SMA removal requests
  useEffect(() => {
    if (smaToRemove) {
      removeSMAData(smaToRemove);
      if (onSMARemoved) {
        onSMARemoved();
      }
    }
  }, [smaToRemove]);

  // Handle SMA visibility toggle requests
  useEffect(() => {
    if (smaToToggle) {
      toggleSMAVisibility(smaToToggle);
      if (onSMAToggled) {
        onSMAToggled();
      }
    }
  }, [smaToToggle]);

  // Notify parent when SMA list changes (but not during prop updates)
  useEffect(() => {
    if (onSMAListChange && !updatingFromPropsRef.current) {
      console.log('[BasicChart] Notifying parent of SMA list change:', smaList.length, 'indicators');
      onSMAListChange(smaList);
    } else if (updatingFromPropsRef.current) {
      console.log('[BasicChart] Skipping parent notification during prop update');
    }
  }, [smaList, onSMAListChange]);

  // Handle real-time SMA parameter updates from props
  useEffect(() => {
    if (!propsSmaList) return;
    
    const previousList = previousSmaListRef.current;
    console.log('[BasicChart] SMA list changed, checking for parameter updates:', propsSmaList);
    
    // Set flag to prevent circular updates
    updatingFromPropsRef.current = true;
    
    propsSmaList.forEach(sma => {
      const series = smaSeriesRef.current.get(sma.id);
      const previousSma = previousList.find(s => s.id === sma.id);
      
      if (series && chartRef.current && previousSma) {
        // Check if color or visibility changed
        if (sma.color !== previousSma.color || sma.visible !== previousSma.visible) {
          console.log(`[BasicChart] Updating color/visibility for ${sma.id}`, {
            oldColor: previousSma.color,
            newColor: sma.color,
            oldVisible: previousSma.visible,
            newVisible: sma.visible
          });
          try {
            (series as any).applyOptions({
              color: sma.color,
              visible: sma.visible
            });
            console.log(`[BasicChart] Color/visibility update applied successfully for ${sma.id}`);
          } catch (err) {
            console.error(`[BasicChart] Error applying color/visibility update for ${sma.id}:`, err);
          }
        }
        
        // Check if period changed - if so, need to reload data
        if (sma.period !== previousSma.period) {
          console.log(`[BasicChart] Period changed for ${sma.id} from ${previousSma.period} to ${sma.period}, reloading...`);
          // Remove old series and reload with new period
          (chartRef.current as any).removeSeries(series);
          smaSeriesRef.current.delete(sma.id);
          
          // Reload SMA with new period
          loadSMADataForUpdate(sma.id, sma.period, sma.color);
        }
      }
    });
    
    // Sync internal state with props
    setSmaList([...propsSmaList]);
    
    // Update previous list reference
    previousSmaListRef.current = [...propsSmaList];
    
    // Reset flag immediately after processing
    setTimeout(() => {
      updatingFromPropsRef.current = false;
      console.log('[BasicChart] Reset updating flag, can notify parent again');
    }, 10);
  }, [propsSmaList]);

  useEffect(() => {
    console.log('[BasicChart] useEffect triggered with:', { symbol, timeframe, width, height });
    
    // Reset states when props change
    setLoading(true);
    setError(null);
    setSmaList([]);
    setDateRange(null);
    smaSeriesRef.current.clear();
    
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

      // Add candlestick series using v4 API (still works in v5)
      const candlestickSeries = (chart as any).addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderDownColor: '#ef5350',
        borderUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        wickUpColor: '#26a69a',
      });

      chartRef.current = chart;
      seriesRef.current = candlestickSeries;

      // Add time scale event listener for chart synchronization
      chart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
        if (timeRange && onDateRangeChange) {
          // Convert timestamp range back to date strings
          const startDate = new Date(timeRange.from * 1000).toISOString().split('T')[0];
          const endDate = new Date(timeRange.to * 1000).toISOString().split('T')[0];
          console.log('[BasicChart] Time range changed:', { startDate, endDate });
          onDateRangeChange({ start: startDate, end: endDate });
        }
      });

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
      
      // Step 2: Request enough calendar time to get 200+ trading data points
      // For hourly data: ~6.5 hours/day * 5 days/week = ~32.5 points/week
      // To get 200 points: 200/32.5 = ~6 weeks, use 8 weeks to be safe
      const targetPoints = 200;
      let requestStartDate: string;
      let requestEndDate: string = end_date;
      
      if (point_count <= targetPoints) {
        // Use all available data
        requestStartDate = start_date;
        console.log('[BasicChart] Using all available data points:', point_count);
      } else {
        // Go back enough calendar days to get sufficient trading data
        const endDateTime = new Date(end_date);
        const weeksNeeded = timeframe === '1h' ? 8 : 
                          timeframe === '1d' ? 40 : // 200 trading days ~ 40 weeks
                          12; // Default to 12 weeks for other timeframes
        const requestStartDateTime = new Date(endDateTime.getTime() - (weeksNeeded * 7 * 24 * 60 * 60 * 1000));
        requestStartDate = requestStartDateTime.toISOString().split('T')[0];
        console.log(`[BasicChart] Requesting ${weeksNeeded} weeks of data from:`, requestStartDate);
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
      
      // Store date range for SMA calculations
      if (data.dates.length > 0) {
        const newDateRange = {
          start: data.dates[0],
          end: data.dates[data.dates.length - 1]
        };
        setDateRange(newDateRange);
        
        // Notify parent about date range change for RSI chart sync
        if (onDateRangeChange) {
          onDateRangeChange(newDateRange);
        }
      }
    } catch (err) {
      console.error('[BasicChart] Error loading data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load chart data');
      setLoading(false);
    }
  };

  const loadSMAData = async (period: number) => {
    if (!dateRange) {
      console.error('[BasicChart] No date range available for SMA calculation');
      return;
    }

    try {
      console.log('[BasicChart] Loading SMA data for period:', period);
      
      const actualTimeframe = (timeframe && timeframe !== 'undefined') ? timeframe : '1h';
      
      const response = await fetch('/api/v1/indicators/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol,
          timeframe: actualTimeframe,
          start_date: dateRange.start,
          end_date: dateRange.end,
          indicators: [
            {
              id: 'SimpleMovingAverage',
              parameters: {
                period: period,
                source: 'close'
              },
              output_name: `SMA_${period}`
            }
          ]
        })
      });

      const responseData = await response.json();
      console.log('[BasicChart] SMA API response:', responseData);

      if (!responseData.success || !responseData.indicators) {
        throw new Error(`Failed to calculate SMA(${period})`);
      }

      // Transform SMA data to TradingView format
      const smaValues = responseData.indicators[`SMA_${period}`] || responseData.indicators[`sma_${period}`];
      if (!smaValues) {
        throw new Error(`SMA_${period} data not found in response`);
      }

      const smaData: LineData[] = [];
      responseData.dates.forEach((dateStr: string, index: number) => {
        const smaValue = smaValues[index];
        if (smaValue !== null && smaValue !== undefined) {
          smaData.push({
            time: (new Date(dateStr).getTime() / 1000) as UTCTimestamp,
            value: smaValue
          });
        }
      });

      // Generate a color for this SMA (cycle through colors)
      const colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4'];
      const color = colors[smaList.length % colors.length];

      // Add SMA line series to chart
      if (chartRef.current) {
        const smaSeries = (chartRef.current as any).addLineSeries({
          color: color,
          lineWidth: 2,
          title: `SMA(${period})`
        });

        smaSeries.setData(smaData);
        
        // Generate unique ID for this SMA
        const smaId = `SMA_${period}_${Date.now()}`;
        
        // Store series reference
        smaSeriesRef.current.set(smaId, smaSeries);

        // Update SMA list
        setSmaList(prev => [...prev, {
          id: smaId,
          period,
          data: smaData,
          color,
          visible: true
        }]);

        console.log('[BasicChart] Added SMA overlay:', { period, color, dataPoints: smaData.length });
      }

    } catch (err) {
      console.error('[BasicChart] Error loading SMA data:', err);
      // Don't show error to user for SMA failures, just log it
    }
  };

  const loadSMADataForUpdate = async (smaId: string, period: number, color: string) => {
    if (!dateRange) {
      console.error('[BasicChart] No date range available for SMA calculation');
      return;
    }

    try {
      console.log('[BasicChart] Loading updated SMA data for period:', period);
      
      const actualTimeframe = (timeframe && timeframe !== 'undefined') ? timeframe : '1h';
      
      const response = await fetch('/api/v1/indicators/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: symbol,
          timeframe: actualTimeframe,
          start_date: dateRange.start,
          end_date: dateRange.end,
          indicators: [
            {
              id: 'SimpleMovingAverage',
              parameters: {
                period: period,
                source: 'close'
              },
              output_name: `SMA_${period}`
            }
          ]
        })
      });

      const responseData = await response.json();
      console.log('[BasicChart] Updated SMA API response:', responseData);

      if (!responseData.success || !responseData.indicators) {
        throw new Error(`Failed to calculate updated SMA(${period})`);
      }

      // Transform SMA data to TradingView format
      const smaValues = responseData.indicators[`SMA_${period}`] || responseData.indicators[`sma_${period}`];
      if (!smaValues) {
        throw new Error(`SMA_${period} data not found in response`);
      }

      const smaData: LineData[] = [];
      responseData.dates.forEach((dateStr: string, index: number) => {
        const smaValue = smaValues[index];
        if (smaValue !== null && smaValue !== undefined) {
          smaData.push({
            time: (new Date(dateStr).getTime() / 1000) as UTCTimestamp,
            value: smaValue
          });
        }
      });

      // Add SMA line series to chart with updated parameters
      if (chartRef.current) {
        const smaSeries = (chartRef.current as any).addLineSeries({
          color: color,
          lineWidth: 2,
          title: `SMA(${period})`,
        });

        smaSeries.setData(smaData);
        
        // Store series reference with existing ID
        smaSeriesRef.current.set(smaId, smaSeries);

        // Update SMA list with new data but keep existing ID
        setSmaList(prev => prev.map(sma => 
          sma.id === smaId 
            ? { ...sma, period, data: smaData, color }
            : sma
        ));

        console.log('[BasicChart] Updated SMA overlay:', { smaId, period, color, dataPoints: smaData.length });
      }

    } catch (err) {
      console.error('[BasicChart] Error loading updated SMA data:', err);
    }
  };

  const removeSMAData = (smaId: string) => {
    console.log('[BasicChart] Removing SMA:', smaId);
    
    // Remove series from chart
    const series = smaSeriesRef.current.get(smaId);
    if (series && chartRef.current) {
      (chartRef.current as any).removeSeries(series);
      smaSeriesRef.current.delete(smaId);
    }
    
    // Remove from SMA list
    setSmaList(prev => prev.filter(sma => sma.id !== smaId));
    
    console.log('[BasicChart] SMA removed:', smaId);
  };

  const toggleSMAVisibility = (smaId: string) => {
    console.log('[BasicChart] Toggling SMA visibility:', smaId);
    
    const series = smaSeriesRef.current.get(smaId);
    if (series) {
      // Update SMA list visibility
      setSmaList(prev => prev.map(sma => {
        if (sma.id === smaId) {
          const newVisible = !sma.visible;
          // Hide/show series by updating its visibility
          (series as any).applyOptions({ visible: newVisible });
          return { ...sma, visible: newVisible };
        }
        return sma;
      }));
    }
    
    console.log('[BasicChart] SMA visibility toggled:', smaId);
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
        {smaList.filter(sma => sma.visible).length > 0 && (
          <div style={{ fontSize: '0.75em', marginTop: '0.25rem' }}>
            <span style={{ color: '#666' }}>Overlays: </span>
            {smaList.filter(sma => sma.visible).map((sma) => (
              <span key={sma.id} style={{ color: sma.color, marginRight: '0.75rem' }}>
                SMA({sma.period})
              </span>
            ))}
          </div>
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