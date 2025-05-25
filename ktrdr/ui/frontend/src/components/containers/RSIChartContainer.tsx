import React, { FC, useState, useEffect, useCallback, useRef } from 'react';
import { IChartApi, LineData, UTCTimestamp } from 'lightweight-charts';
import RSIChart, { RSIData, RSIIndicatorSeries } from '../presentation/charts/RSIChart';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { IndicatorInfo } from '../../store/indicatorRegistry';

/**
 * Container component for the RSI oscillator chart
 * 
 * This component handles all data loading, API calls, RSI calculations,
 * and state management, while delegating the chart rendering to the 
 * RSIChart presentation component.
 */

interface RSIChartContainerProps {
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
  
  // Synchronization with main chart
  timeRange?: { start: string; end: string } | null;
  
  // Callbacks
  onDataLoaded?: (data: RSIData) => void;
  onError?: (error: string) => void;
}

const RSIChartContainer: FC<RSIChartContainerProps> = ({
  width = 800,
  height = 200,
  symbol,
  timeframe,
  indicators = [],
  chartSynchronizer,
  chartId = 'rsi-chart',
  timeRange,
  onDataLoaded,
  onError
}) => {
  // Internal state
  const [rsiData, setRsiData] = useState<RSIData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Chart reference for synchronization
  const chartRef = useRef<IChartApi | null>(null);
  
  // Track current symbol/timeframe to detect changes
  const currentSymbolRef = useRef<string>('');
  const currentTimeframeRef = useRef<string>('');
  
  // Track price data for RSI calculations
  const priceDataRef = useRef<any[]>([]);

  // Load price data for RSI calculations
  const loadPriceData = useCallback(async (symbol: string, timeframe: string) => {
    console.log('[RSIChartContainer] Loading price data for RSI calculations:', { symbol, timeframe });

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
      console.log('[RSIChartContainer] Price data loaded for RSI:', result);

      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to load data');
      }

      // Store price data for RSI calculations
      priceDataRef.current = result.data.ohlcv;
      console.log('[RSIChartContainer] Price data cached for RSI calculations:', priceDataRef.current.length, 'points');

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      console.error('[RSIChartContainer] Error loading price data for RSI:', errorMessage);
      setError(errorMessage);
      if (onError) {
        onError(errorMessage);
      }
    }
  }, [onError]);

  // Calculate RSI indicator data
  const calculateRSIData = useCallback(async (indicator: IndicatorInfo): Promise<LineData[]> => {
    console.log('[RSIChartContainer] Calculating RSI:', indicator.name, indicator.parameters);

    if (!priceDataRef.current.length) {
      console.warn('[RSIChartContainer] No price data available for RSI calculation');
      return [];
    }

    try {
      const response = await fetch('/api/v1/indicators/calculate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          data: {
            symbol,
            timeframe,
            ohlcv: priceDataRef.current
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
        throw new Error(result.error?.message || 'Failed to calculate RSI');
      }

      // Transform RSI results to LineData format
      const rsiValues = result.data.results[indicator.name] || [];
      const lineData: LineData[] = rsiValues
        .map((value: number | null, index: number) => {
          if (value === null || value === undefined) return null;
          const timestamp = priceDataRef.current[index]?.timestamp;
          if (!timestamp) return null;
          return {
            time: new Date(timestamp).getTime() / 1000 as UTCTimestamp,
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];

      console.log('[RSIChartContainer] RSI calculated:', indicator.name, lineData.length, 'points');
      return lineData;

    } catch (error) {
      console.error('[RSIChartContainer] Error calculating RSI:', error);
      return [];
    }
  }, [symbol, timeframe]);

  // Update RSI data when indicators change
  useEffect(() => {
    if (!priceDataRef.current.length) {
      console.log('[RSIChartContainer] No price data available, skipping RSI update');
      return;
    }

    const updateRSIIndicators = async () => {
      console.log('[RSIChartContainer] Updating RSI indicators:', indicators.length);
      
      // Filter for RSI indicators only
      const rsiIndicators = indicators.filter(ind => ind.name === 'rsi');
      
      if (rsiIndicators.length === 0) {
        setRsiData(null);
        return;
      }

      setIsLoading(true);
      setError(null);
      
      try {
        const rsiSeries: RSIIndicatorSeries[] = [];
        
        for (const indicator of rsiIndicators) {
          if (!indicator.visible) {
            // Include invisible indicators but mark them as not visible
            rsiSeries.push({
              id: indicator.id,
              name: indicator.displayName,
              data: [],
              color: indicator.parameters.color || '#FF5722',
              visible: false
            });
            continue;
          }

          const rsiData = await calculateRSIData(indicator);
          
          rsiSeries.push({
            id: indicator.id,
            name: `${indicator.displayName}(${indicator.parameters.period})`,
            data: rsiData,
            color: indicator.parameters.color || '#FF5722',
            visible: indicator.visible
          });
        }

        // Update RSI data
        const newRsiData: RSIData = {
          indicators: rsiSeries
        };

        setRsiData(newRsiData);
        
        if (onDataLoaded) {
          onDataLoaded(newRsiData);
        }

      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        console.error('[RSIChartContainer] Error updating RSI indicators:', errorMessage);
        setError(errorMessage);
        if (onError) {
          onError(errorMessage);
        }
      } finally {
        setIsLoading(false);
      }
    };

    updateRSIIndicators();
  }, [indicators, calculateRSIData, onDataLoaded, onError]);

  // Load price data when symbol or timeframe changes
  useEffect(() => {
    if (symbol && timeframe && 
        (symbol !== currentSymbolRef.current || timeframe !== currentTimeframeRef.current)) {
      console.log('[RSIChartContainer] Symbol or timeframe changed, reloading price data');
      currentSymbolRef.current = symbol;
      currentTimeframeRef.current = timeframe;
      
      // Clear existing data
      setRsiData(null);
      setError(null);
      
      // Load new price data
      loadPriceData(symbol, timeframe);
    }
  }, [symbol, timeframe, loadPriceData]);

  // Handle chart creation for synchronization
  const handleChartCreated = useCallback((chart: IChartApi) => {
    console.log('[RSIChartContainer] RSI chart created, registering for synchronization');
    chartRef.current = chart;
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.registerChart(chartId, chart, `RSI Chart (${symbol})`);
    }
  }, [chartSynchronizer, chartId, symbol]);

  // Handle chart destruction
  const handleChartDestroyed = useCallback(() => {
    console.log('[RSIChartContainer] RSI chart destroyed, unregistering from synchronization');
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.unregisterChart(chartId);
    }
    
    chartRef.current = null;
  }, [chartSynchronizer, chartId]);

  return (
    <RSIChart
      width={width}
      height={height}
      rsiData={rsiData}
      isLoading={isLoading}
      error={error}
      onChartCreated={handleChartCreated}
      onChartDestroyed={handleChartDestroyed}
      showLoadingOverlay={true}
      showErrorOverlay={true}
      showOverboughtOversold={true}
    />
  );
};

export default RSIChartContainer;