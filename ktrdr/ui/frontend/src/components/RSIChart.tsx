import { useEffect, useRef, useState, FC } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, UTCTimestamp } from 'lightweight-charts';

export interface RSIData {
  id: string;
  period: number;
  data: LineData[];
  color: string;
  visible: boolean;
}

interface RSIChartProps {
  width?: number;
  height?: number;
  symbol: string;
  timeframe: string;
  rsiToAdd?: number | null;
  onRSIAdded?: () => void;
  rsiToRemove?: string | null;
  onRSIRemoved?: () => void;
  rsiToToggle?: string | null;
  onRSIToggled?: () => void;
  onRSIListChange?: (rsiList: RSIData[]) => void;
  dateRange?: {start: string, end: string} | null;
}

const RSIChart: FC<RSIChartProps> = ({
  width = 800,
  height = 200,
  symbol,
  timeframe,
  rsiToAdd,
  onRSIAdded,
  rsiToRemove,
  onRSIRemoved,
  rsiToToggle,
  onRSIToggled,
  onRSIListChange,
  dateRange
}) => {
  console.log('[RSIChart] Props received:', { symbol, timeframe, width, height, rsiToAdd, rsiToRemove, rsiToToggle });
  
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const rsiSeriesRef = useRef<Map<string, ISeriesApi<'Line'>>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rsiList, setRsiList] = useState<RSIData[]>([]);
  const [chartInitialized, setChartInitialized] = useState(false);

  // Handle RSI addition requests
  useEffect(() => {
    console.log('[RSIChart] RSI addition effect triggered:', { rsiToAdd, hasDateRange: !!dateRange, chartInitialized });
    if (rsiToAdd) {
      if (!rsiList.some(rsi => rsi.period === rsiToAdd) && dateRange && chartInitialized) {
        console.log('[RSIChart] All conditions met, loading RSI data...');
        loadRSIData(rsiToAdd).then(() => {
          if (onRSIAdded) {
            onRSIAdded();
          }
        });
      } else if (rsiList.some(rsi => rsi.period === rsiToAdd)) {
        // Indicator already exists, just reset the loading state
        console.log(`[RSIChart] RSI(${rsiToAdd}) already exists, skipping`);
        if (onRSIAdded) {
          onRSIAdded();
        }
      } else {
        // Chart not ready or no date range, will retry when conditions are met
        console.log('[RSIChart] Conditions not met yet, will retry when ready');
      }
    }
  }, [rsiToAdd, dateRange, chartInitialized]);

  // Handle RSI removal requests
  useEffect(() => {
    if (rsiToRemove) {
      removeRSIData(rsiToRemove);
      if (onRSIRemoved) {
        onRSIRemoved();
      }
    }
  }, [rsiToRemove]);

  // Handle RSI visibility toggle requests
  useEffect(() => {
    if (rsiToToggle) {
      toggleRSIVisibility(rsiToToggle);
      if (onRSIToggled) {
        onRSIToggled();
      }
    }
  }, [rsiToToggle]);

  // Notify parent when RSI list changes
  useEffect(() => {
    if (onRSIListChange) {
      onRSIListChange(rsiList);
    }
  }, [rsiList, onRSIListChange]);

  // Initialize chart when component mounts
  useEffect(() => {
    if (!chartContainerRef.current || chartInitialized) return;

    console.log('[RSIChart] Initializing RSI chart...');

    // Create the RSI chart
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
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
        entireTextOnly: true,
      },
      // Fix RSI scale to 0-100 range
      priceScale: {
        mode: 0, // Normal price scale mode
      }
    });

    // Set fixed price range for RSI (0-100)
    chart.priceScale('right').applyOptions({
      autoScale: false,
      invertScale: false,
      scaleMargins: {
        top: 0.1,
        bottom: 0.1,
      },
    });

    // Note: Reference lines will be added later once RSI data display is working

    chartRef.current = chart;
    setChartInitialized(true);

    console.log('[RSIChart] RSI chart initialized - ready to accept data');

    // Cleanup function
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        rsiSeriesRef.current.clear();
        setChartInitialized(false);
      }
    };
  }, [width, height]);

  // Update chart size when props change
  useEffect(() => {
    if (chartRef.current && chartInitialized) {
      chartRef.current.applyOptions({ width, height });
    }
  }, [width, height, chartInitialized]);

  // Reset RSI list when symbol/timeframe changes
  useEffect(() => {
    console.log('[RSIChart] Symbol/timeframe changed, clearing RSI list');
    setRsiList([]);
    setError(null);
    if (chartRef.current) {
      // Clear all RSI series
      rsiSeriesRef.current.forEach((series) => {
        (chartRef.current as any).removeSeries(series);
      });
      rsiSeriesRef.current.clear();
    }
  }, [symbol, timeframe]);

  // Synchronize time range with main chart
  useEffect(() => {
    if (chartRef.current && chartInitialized && dateRange) {
      try {
        const startTime = (new Date(dateRange.start).getTime() / 1000);
        const endTime = (new Date(dateRange.end).getTime() / 1000);
        console.log('[RSIChart] Synchronizing time range:', { startTime, endTime });
        chartRef.current.timeScale().setVisibleRange({ from: startTime, to: endTime });
      } catch (e) {
        console.log('[RSIChart] Could not synchronize time range:', e);
      }
    }
  }, [dateRange, chartInitialized]);

  const loadRSIData = async (period: number) => {
    if (!dateRange) {
      console.error('[RSIChart] No date range available for RSI calculation');
      return;
    }

    try {
      console.log('[RSIChart] Loading RSI data for period:', period);
      setLoading(true);
      
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
              id: 'RSIIndicator',
              parameters: {
                period: period,
                source: 'close'
              },
              output_name: `RSI_${period}`
            }
          ]
        })
      });

      const responseData = await response.json();
      console.log('[RSIChart] RSI API response:', responseData);

      if (!responseData.success || !responseData.indicators) {
        throw new Error(`Failed to calculate RSI(${period})`);
      }

      console.log('[RSIChart] Chart initialized?', chartInitialized);
      console.log('[RSIChart] Chart ref?', !!chartRef.current);

      // Transform RSI data to TradingView format
      const rsiValues = responseData.indicators[`RSI_${period}`] || responseData.indicators[`rsi_${period}`];
      if (!rsiValues) {
        throw new Error(`RSI_${period} data not found in response`);
      }

      const rsiData: LineData[] = [];
      responseData.dates.forEach((dateStr: string, index: number) => {
        const rsiValue = rsiValues[index];
        if (rsiValue !== null && rsiValue !== undefined) {
          rsiData.push({
            time: (new Date(dateStr).getTime() / 1000) as UTCTimestamp,
            value: rsiValue
          });
        }
      });

      console.log('[RSIChart] RSI data sample:', rsiData.slice(0, 5));
      console.log('[RSIChart] RSI value range:', {
        min: Math.min(...rsiData.map(d => d.value)),
        max: Math.max(...rsiData.map(d => d.value))
      });

      // Generate a color for this RSI (cycle through colors)
      const colors = ['#9C27B0', '#E91E63', '#FF9800', '#2196F3', '#4CAF50', '#00BCD4'];
      const color = colors[rsiList.length % colors.length];

      // Add RSI line series to chart
      if (chartRef.current && chartInitialized) {
        const rsiSeries = (chartRef.current as any).addLineSeries({
          color: color,
          lineWidth: 2,
          title: `RSI(${period})`,
        });

        console.log('[RSIChart] Setting data on RSI series...', rsiData.length, 'points');
        rsiSeries.setData(rsiData);
        console.log('[RSIChart] Data set successfully on RSI series');
        
        // Generate unique ID for this RSI
        const rsiId = `RSI_${period}_${Date.now()}`;
        
        // Store series reference
        rsiSeriesRef.current.set(rsiId, rsiSeries);

        // Update RSI list
        setRsiList(prev => [...prev, {
          id: rsiId,
          period,
          data: rsiData,
          color,
          visible: true
        }]);

        // Enable auto-scaling to show RSI data properly
        chartRef.current.priceScale('right').applyOptions({
          autoScale: true,
          scaleMargins: {
            top: 0.2,
            bottom: 0.2,
          },
        });
        
        // Fit content to show the data
        chartRef.current.timeScale().fitContent();

        console.log('[RSIChart] Added RSI overlay:', { period, color, dataPoints: rsiData.length });
      }

      setLoading(false);
    } catch (err) {
      console.error('[RSIChart] Error loading RSI data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load RSI data');
      setLoading(false);
    }
  };

  const removeRSIData = (rsiId: string) => {
    console.log('[RSIChart] Removing RSI:', rsiId);
    
    // Remove series from chart
    const series = rsiSeriesRef.current.get(rsiId);
    if (series && chartRef.current) {
      (chartRef.current as any).removeSeries(series);
      rsiSeriesRef.current.delete(rsiId);
    }
    
    // Remove from RSI list
    setRsiList(prev => prev.filter(rsi => rsi.id !== rsiId));
    
    console.log('[RSIChart] RSI removed:', rsiId);
  };

  const toggleRSIVisibility = (rsiId: string) => {
    console.log('[RSIChart] Toggling RSI visibility:', rsiId);
    
    const series = rsiSeriesRef.current.get(rsiId);
    if (series) {
      // Update RSI list visibility
      setRsiList(prev => prev.map(rsi => {
        if (rsi.id === rsiId) {
          const newVisible = !rsi.visible;
          // Hide/show series by updating its visibility
          (series as any).applyOptions({ visible: newVisible });
          return { ...rsi, visible: newVisible };
        }
        return rsi;
      }));
    }
    
    console.log('[RSIChart] RSI visibility toggled:', rsiId);
  };

  return (
    <div style={{ marginTop: '1rem' }}>
      <h4 style={{ margin: '0 0 0.5rem 0', color: '#333', fontSize: '0.95rem' }}>
        RSI Oscillator
        {rsiList.filter(rsi => rsi.visible).length > 0 && (
          <span style={{ fontSize: '0.8em', marginLeft: '0.5rem' }}>
            {rsiList.filter(rsi => rsi.visible).map((rsi) => (
              <span key={rsi.id} style={{ color: rsi.color, marginRight: '0.75rem' }}>
                RSI({rsi.period})
              </span>
            ))}
          </span>
        )}
        {loading && (
          <span style={{ fontSize: '0.8em', color: '#666', marginLeft: '0.5rem' }}>
            Loading...
          </span>
        )}
      </h4>
      
      {error && (
        <div style={{ 
          color: '#f44336', 
          fontSize: '0.8rem', 
          marginBottom: '0.5rem',
          padding: '0.5rem',
          backgroundColor: '#ffebee',
          borderRadius: '4px'
        }}>
          {error}
        </div>
      )}
      
      <div 
        ref={chartContainerRef} 
        style={{ 
          width: `${width}px`, 
          height: `${height}px`,
          border: '1px solid #e0e0e0',
          borderRadius: '4px',
          backgroundColor: '#fff',
          position: 'relative'
        }}
      >
        {rsiList.length === 0 && !loading && !error && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#fafafa',
            border: '1px dashed #ccc',
            borderRadius: '4px',
            color: '#666',
            fontSize: '0.9rem',
            zIndex: 1
          }}>
            Add RSI indicator from the sidebar to see oscillator panel
          </div>
        )}
      </div>
    </div>
  );
};

export default RSIChart;