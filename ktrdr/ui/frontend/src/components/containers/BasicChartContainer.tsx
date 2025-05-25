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
    console.log('[BasicChartContainer] Loading price data:', { symbol, timeframe });
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/data/load', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol,
          timeframe,
          source: 'auto'
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('[BasicChartContainer] API response received:', result);

      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to load data');
      }

      // Transform OHLCV data to TradingView format
      const candlestickData: CandlestickData[] = result.data.ohlcv.map((point: any) => ({
        time: new Date(point.timestamp).getTime() / 1000 as UTCTimestamp,
        open: point.open,
        high: point.high,
        low: point.low,
        close: point.close,
      }));

      // Create chart data structure
      const newChartData: ChartData = {
        candlestick: candlestickData,
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

      console.log('[BasicChartContainer] Price data loaded successfully:', candlestickData.length, 'points');

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
  }, [onDataLoaded, onError]);

  // Calculate indicator data
  const calculateIndicatorData = useCallback(async (
    baseData: CandlestickData[], 
    indicator: IndicatorInfo
  ): Promise<LineData[]> => {
    console.log('[BasicChartContainer] Calculating indicator:', indicator.name, indicator.parameters);

    try {
      // Transform candlestick data back to OHLCV format for API
      const ohlcvData = baseData.map(point => ({
        timestamp: new Date(point.time * 1000).toISOString(),
        open: point.open,
        high: point.high,
        low: point.low,
        close: point.close,
        volume: 1000 // Default volume for now
      }));

      const response = await fetch('/api/v1/indicators/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          data: {
            symbol,
            timeframe,
            ohlcv: ohlcvData
          },
          indicators: [
            {
              name: indicator.name,
              parameters: indicator.parameters
            }
          ]
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to calculate indicator');
      }

      // Transform indicator results to LineData format
      const indicatorValues = result.data.results[indicator.name] || [];
      const lineData: LineData[] = indicatorValues
        .map((value: number | null, index: number) => {
          if (value === null || value === undefined) return null;
          return {
            time: baseData[index]?.time,
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];

      console.log('[BasicChartContainer] Indicator calculated:', indicator.name, lineData.length, 'points');
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
      console.log('[BasicChartContainer] Updating indicators:', indicators.length);
      
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
      setChartData(prev => prev ? {
        ...prev,
        indicators: indicatorSeries
      } : null);
    };

    updateIndicators();
  }, [indicators, chartData?.candlestick, calculateIndicatorData]);

  // Load data when symbol or timeframe changes
  useEffect(() => {
    if (symbol && timeframe && 
        (symbol !== currentSymbolRef.current || timeframe !== currentTimeframeRef.current)) {
      console.log('[BasicChartContainer] Symbol or timeframe changed, reloading data');
      currentSymbolRef.current = symbol;
      currentTimeframeRef.current = timeframe;
      loadPriceData(symbol, timeframe);
    }
  }, [symbol, timeframe, loadPriceData]);

  // Handle chart creation for synchronization
  const handleChartCreated = useCallback((chart: IChartApi) => {
    console.log('[BasicChartContainer] Chart created, registering for synchronization');
    chartRef.current = chart;
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.registerChart(chartId, chart, `Price Chart (${symbol})`);
    }
  }, [chartSynchronizer, chartId, symbol]);

  // Handle chart destruction
  const handleChartDestroyed = useCallback(() => {
    console.log('[BasicChartContainer] Chart destroyed, unregistering from synchronization');
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.unregisterChart(chartId);
    }
    
    chartRef.current = null;
  }, [chartSynchronizer, chartId]);

  // Handle time range changes
  const handleTimeRangeChange = useCallback((range: { start: string; end: string }) => {
    console.log('[BasicChartContainer] Time range changed:', range);
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
    />
  );
};

export default BasicChartContainer;