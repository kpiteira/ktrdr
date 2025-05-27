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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [priceData, setPriceData] = useState<CandlestickData[]>([]);
  
  // Chart reference for synchronization
  const chartRef = useRef<IChartApi | null>(null);

  // Load price data
  const loadPriceData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Calculate dates for last 3 months
      const endDate = new Date();
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 3);
      
      const response = await fetch('/api/v1/data/load', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol,
          timeframe,
          start_date: startDate.toISOString().split('T')[0],
          end_date: endDate.toISOString().split('T')[0]
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (!result.success || !result.data || !result.data.dates || !result.data.ohlcv) {
        throw new Error('Invalid response format from data API');
      }
      
      const data = result.data;
      const transformedData: CandlestickData[] = data.dates.map((dateStr: string, index: number) => {
        const ohlcv = data.ohlcv[index];
        if (!ohlcv || ohlcv.length < 4) {
          throw new Error(`Invalid OHLCV data at index ${index}`);
        }
        
        return {
          time: (new Date(dateStr).getTime() / 1000) as UTCTimestamp,
          open: ohlcv[0],
          high: ohlcv[1],
          low: ohlcv[2],
          close: ohlcv[3]
        };
      });
      
      setPriceData(transformedData);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setIsLoading(false);
    }
  }, [symbol, timeframe]);

  // Calculate indicator data
  const calculateIndicatorData = useCallback(async (
    baseData: CandlestickData[], 
    indicator: IndicatorInfo
  ): Promise<LineData[]> => {
    try {
      const indicatorId = indicator.name === 'sma' ? 'SimpleMovingAverage' : 
                         indicator.name === 'rsi' ? 'RSIIndicator' :
                         indicator.name === 'ema' ? 'ExponentialMovingAverage' : 
                         indicator.name;

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
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to calculate indicator');
      }

      const outputName = indicator.name === 'sma' ? `SMA_${indicator.parameters.period}` :
                         indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                         indicator.name === 'ema' ? `EMA_${indicator.parameters.period}` :
                         `${indicator.name.toUpperCase()}_${indicator.parameters.period}`;
                         
      const indicatorValues = result.indicators?.[outputName] || 
                             result.indicators?.[outputName.toLowerCase()] || 
                             [];
      
      const indicatorCount = indicatorValues.length;
      const candlestickCount = baseData.length;
      const startIndex = candlestickCount - indicatorCount;
      
      const lineData: LineData[] = indicatorValues
        .map((value: number | null, index: number) => {
          const candlestickIndex = startIndex + index;
          if (value === null || value === undefined || !baseData[candlestickIndex]) return null;
          return {
            time: baseData[candlestickIndex].time as UTCTimestamp,
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];
        
      return lineData;

    } catch (error) {
      console.error('Error calculating indicator:', error);
      return [];
    }
  }, [symbol, timeframe]);

  // Load price data when symbol/timeframe changes
  useEffect(() => {
    if (symbol && timeframe) {
      loadPriceData();
    }
  }, [symbol, timeframe, loadPriceData]);

  // Update chart data when price data or indicators change
  useEffect(() => {
    if (!priceData.length) {
      setChartData(null);
      setChartInfo(null);
      return;
    }

    const updateChartData = async () => {
      const newChartData: ChartData = {
        candlestick: [...priceData],
        indicators: []
      };

      const newChartInfo: ChartInfo = {
        startDate: new Date(priceData[0].time * 1000).toISOString().split('T')[0],
        endDate: new Date(priceData[priceData.length - 1].time * 1000).toISOString().split('T')[0],
        pointCount: priceData.length
      };
      
      // Calculate indicators in parallel for better performance
      const indicatorPromises = indicators.map(async (indicator) => {
        const indicatorData = await calculateIndicatorData(priceData, indicator);
        
        return {
          id: indicator.id,
          name: `${indicator.displayName}(${indicator.parameters.period})`,
          data: indicatorData,
          color: indicator.parameters.color || '#2196F3',
          visible: indicator.visible
        };
      });
      
      const indicatorSeries = await Promise.all(indicatorPromises);

      newChartData.indicators = indicatorSeries;
      
      setChartData(newChartData);
      setChartInfo(newChartInfo);
      
      if (onDataLoaded) {
        onDataLoaded(newChartData);
      }
    };

    updateChartData();
  }, [priceData, indicators, calculateIndicatorData, onDataLoaded]);

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