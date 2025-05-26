import React, { FC, useState, useEffect, useCallback, useRef } from 'react';
import { IChartApi, CandlestickData, LineData, UTCTimestamp } from 'lightweight-charts';
import BasicChart, { ChartData, IndicatorSeries, ChartInfo } from '../presentation/charts/BasicChart';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { IndicatorInfo } from '../../store/indicatorRegistry';

/**
 * Container component for the basic price chart
 * 
 * This component handles all data loading, API calls, indicator calculations,
 * and state management, while delegating the chart rendering to the 
 * BasicChart presentation component.
 */

interface BasicChartContainerProps {
  // Chart configuration
  width?: number;
  height?: number;
  
  // Data props
  symbol: string;
  timeframe: string;
  
  // Indicator data from parent
  indicators?: IndicatorInfo[];
  
  // Chart synchronization
  chartSynchronizer?: ReturnType<typeof useChartSynchronizer>;
  chartId?: string;
  
  // Callbacks
  onDataLoaded?: (data: ChartData) => void;
  onTimeRangeChange?: (range: { start: string; end: string }) => void;
  onError?: (error: string) => void;
}

const BasicChartContainer: FC<BasicChartContainerProps> = ({
  width = 800,
  height = 400,
  symbol,
  timeframe,
  indicators = [],
  chartSynchronizer,
  chartId = 'basic-chart',
  onDataLoaded,
  onTimeRangeChange,
  onError
}) => {
  // Internal state
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [chartInfo, setChartInfo] = useState<ChartInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Chart reference for synchronization
  const chartRef = useRef<IChartApi | null>(null);
  
  // Track current symbol/timeframe to detect changes
  const currentSymbolRef = useRef<string>('');
  const currentTimeframeRef = useRef<string>('');

  // Load price data from API
  const loadPriceData = useCallback(async (symbol: string, timeframe: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Calculate date range to get approximately 500 trading points
      const targetPoints = 500;
      const now = new Date();
      let weeksNeeded;
      
      // For hourly data: ~6.5 hours/day * 5 days/week = ~32.5 points/week  
      // For daily data: ~5 trading days/week
      if (timeframe === '1h') {
        weeksNeeded = Math.ceil(targetPoints / 32.5); // ~15 weeks for 500 points
      } else if (timeframe === '1d') {
        weeksNeeded = Math.ceil(targetPoints / 5); // ~100 weeks for 500 points  
      } else {
        weeksNeeded = 20; // Default fallback
      }
      
      const startDate = new Date(now);
      startDate.setDate(startDate.getDate() - (weeksNeeded * 7));
      
      const response = await fetch('/api/v1/data/load', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol,
          timeframe,
          source: 'auto',
          start_date: startDate.toISOString().split('T')[0],
          end_date: now.toISOString().split('T')[0]
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to load data');
      }

      // Transform OHLCV data to TradingView format
      console.log('[BasicChartContainer] Starting data transformation...');
      console.log('[BasicChartContainer] CHECKPOINT 1: About to access result.data');
      
      // Use exact same transformation logic as working BasicChart.tsx
      const data = result.data;
      
      console.log('[BasicChartContainer] Using working transformation logic');
      console.log('[BasicChartContainer] Data keys:', Object.keys(data));
      
      if (!data.dates || !data.ohlcv || data.dates.length === 0) {
        throw new Error(`No data available for ${symbol} (${timeframe} timeframe)`);
      }

      // Transform data to TradingView format - exact copy from working code
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
      
      console.log('[BasicChartContainer] Transformation complete - got', candlestickData.length, 'points');
      const validData = candlestickData;

      // Create chart data structure
      const newChartData: ChartData = {
        candlestick: validData,
        indicators: [] // Will be populated by indicator calculations
      };

      // Create chart info
      const newChartInfo: ChartInfo = {
        startDate: result.data.start_date,
        endDate: result.data.end_date,
        pointCount: result.data.points
      };

      setChartData(newChartData);
      setChartInfo(newChartInfo);
      
      if (onDataLoaded) {
        onDataLoaded(newChartData);
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      console.error('[BasicChartContainer] Error loading price data:', errorMessage);
      setError(errorMessage);
      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Calculate indicator data
  const calculateIndicatorData = useCallback(async (
    baseData: CandlestickData[], 
    indicator: IndicatorInfo
  ): Promise<LineData[]> => {

    try {
      // Use the exact API format from the working original code
      const indicatorId = indicator.name === 'sma' ? 'SimpleMovingAverage' : 
                         indicator.name === 'rsi' ? 'RSIIndicator' :
                         indicator.name === 'ema' ? 'ExponentialMovingAverage' : 
                         indicator.name;

      // Use the actual date range from the loaded candlestick data
      const startDate = new Date(baseData[0].time * 1000).toISOString().split('T')[0];
      const endDate = new Date(baseData[baseData.length - 1].time * 1000).toISOString().split('T')[0];

      const requestPayload = {
        symbol: symbol,
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        indicators: [
          {
            id: indicatorId,
            parameters: {
              period: indicator.parameters.period,
              source: 'close'
            },
            output_name: indicator.name === 'sma' ? `SMA_${indicator.parameters.period}` :
                        indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                        indicator.name === 'ema' ? `EMA_${indicator.parameters.period}` :
                        `${indicator.name.toUpperCase()}_${indicator.parameters.period}`
          }
        ]
      };
      
      const response = await fetch('/api/v1/indicators/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestPayload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[BasicChartContainer] API error response:', {
          status: response.status,
          statusText: response.statusText,
          body: errorText
        });
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to calculate indicator');
      }

      // Transform indicator results to LineData format - match working original code
      const outputName = indicator.name === 'sma' ? `SMA_${indicator.parameters.period}` :
                         indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                         indicator.name === 'ema' ? `EMA_${indicator.parameters.period}` :
                         `${indicator.name.toUpperCase()}_${indicator.parameters.period}`;
                         
      const indicatorValues = result.indicators?.[outputName] || 
                             result.indicators?.[outputName.toLowerCase()] || 
                             [];
      // Since both datasets are now similar sizes (238 vs 235), map the last N indicator 
      // values to the last N candlestick timestamps to ensure alignment
      const indicatorCount = indicatorValues.length;
      const candlestickCount = baseData.length;
      const startIndex = candlestickCount - indicatorCount; // Start from the end and work backwards
      
      const lineData: LineData[] = indicatorValues
        .map((value: number | null, index: number) => {
          const candlestickIndex = startIndex + index;
          if (value === null || value === undefined || !baseData[candlestickIndex]) return null;
          return {
            time: baseData[candlestickIndex].time, // Use exact same timestamp as candlestick data
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];
        
      return lineData;

    } catch (error) {
      console.error('[BasicChartContainer] Error calculating indicator:', error);
      return [];
    }
  }, [symbol, timeframe]);

  // Update chart data when indicators change
  useEffect(() => {
    if (!chartData || !chartData.candlestick.length) {
      return;
    }

    const updateIndicators = async () => {
      // console.log('[BasicChartContainer] Updating indicators:', indicators.length);
      
      const indicatorSeries: IndicatorSeries[] = [];
      
      for (const indicator of indicators) {
        if (!indicator.visible) {
          // Include invisible indicators but mark them as not visible
          indicatorSeries.push({
            id: indicator.id,
            name: indicator.displayName,
            data: [],
            color: indicator.parameters.color || '#2196F3',
            visible: false
          });
          continue;
        }

        const indicatorData = await calculateIndicatorData(chartData.candlestick, indicator);
        
        indicatorSeries.push({
          id: indicator.id,
          name: `${indicator.displayName}(${indicator.parameters.period})`,
          data: indicatorData,
          color: indicator.parameters.color || '#2196F3',
          visible: indicator.visible
        });
      }

      // Update chart data with new indicators
      setChartData(prev => {
        if (!prev) return null;
        const newChartData = {
          candlestick: [...prev.candlestick], // Create new array reference
          indicators: [...indicatorSeries]    // Create new array reference
        };
        // console.log('[BasicChartContainer] ✅ Updated chartData with', indicatorSeries.length, 'indicators');
        return newChartData;
      });
    };

    updateIndicators();
  }, [indicators, calculateIndicatorData]);

  // Load data when symbol or timeframe changes
  useEffect(() => {
    if (symbol && timeframe && 
        (symbol !== currentSymbolRef.current || timeframe !== currentTimeframeRef.current)) {
      currentSymbolRef.current = symbol;
      currentTimeframeRef.current = timeframe;
      loadPriceData(symbol, timeframe);
    }
  }, [symbol, timeframe, loadPriceData]);

  // Handle chart creation for synchronization
  const handleChartCreated = useCallback((chart: IChartApi) => {
    chartRef.current = chart;
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.registerChart(chartId, chart, `Price Chart (${symbol})`);
    }
  }, [chartSynchronizer, chartId, symbol]);

  // Handle chart destruction
  const handleChartDestroyed = useCallback(() => {
    if (chartSynchronizer && chartId) {
      chartSynchronizer.unregisterChart(chartId);
    }
    
    chartRef.current = null;
  }, [chartSynchronizer, chartId]);

  // Handle time range changes
  const handleTimeRangeChange = useCallback((range: { start: string; end: string }) => {
    if (onTimeRangeChange) {
      onTimeRangeChange(range);
    }
  }, [onTimeRangeChange]);


  return (
    <BasicChart
      width={width}
      height={height}
      chartData={chartData}
      chartInfo={chartInfo}
      isLoading={isLoading}
      error={error}
      onChartCreated={handleChartCreated}
      onChartDestroyed={handleChartDestroyed}
      onTimeRangeChange={handleTimeRangeChange}
      showLoadingOverlay={true}
      showErrorOverlay={true}
      preserveTimeScale={!!chartSynchronizer}
    />
  );
};

export default BasicChartContainer;