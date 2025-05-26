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
  onChartReady?: () => void;
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
  onError,
  onChartReady
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

  // Load price data for RSI calculations - use same strategy as BasicChartContainer
  const loadPriceData = useCallback(async (symbol: string, timeframe: string) => {

    try {
      // Calculate date range to get approximately 500 trading points (same as BasicChartContainer)
      const targetPoints = 500;
      const now = new Date();
      let weeksNeeded;
      
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
      console.log('[RSIChartContainer] Price data loaded for RSI:', result);

      if (!result.success) {
        throw new Error(result.error?.message || 'Failed to load data');
      }

      // Store price data for RSI calculations  
      // Handle both legacy (dates + ohlcv arrays) and new (ohlcv objects) formats
      const dates = result.data.dates || [];
      const ohlcv = result.data.ohlcv || [];
      
      if (dates.length > 0 && ohlcv.length > 0) {
        // Legacy format: convert to objects
        priceDataRef.current = dates.map((dateStr: string, index: number) => ({
          timestamp: dateStr,
          open: ohlcv[index][0],
          high: ohlcv[index][1], 
          low: ohlcv[index][2],
          close: ohlcv[index][3],
          volume: ohlcv[index][4] || 1000
        }));
      } else {
        // New format: use as-is
        priceDataRef.current = result.data.ohlcv;
      }
      console.log('[RSIChartContainer] Price data cached for RSI calculations:', priceDataRef.current.length, 'points');
      setPriceDataLoaded(true);

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
          symbol: symbol,
          timeframe: timeframe,
          start_date: new Date(priceDataRef.current[0]?.timestamp || Date.now()).toISOString().split('T')[0],
          end_date: new Date(priceDataRef.current[priceDataRef.current.length - 1]?.timestamp || Date.now()).toISOString().split('T')[0],
          indicators: [
            {
              id: 'RSIIndicator',  // Use backend ID format
              parameters: {
                period: indicator.parameters.period,
                source: 'close'
              },
              output_name: `RSI_${indicator.parameters.period}`
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

      // Transform RSI results to LineData format - match BasicChartContainer format
      const outputName = `RSI_${indicator.parameters.period}`;
      const rsiValues = result.indicators?.[outputName] || 
                       result.indicators?.[outputName.toLowerCase()] || 
                       [];
      const lineData: LineData[] = rsiValues
        .map((value: number | null, index: number) => {
          if (value === null || value === undefined) return null;
          const timestamp = priceDataRef.current[index]?.timestamp;
          if (!timestamp) return null;
          
          let time: number;
          if (typeof timestamp === 'string') {
            time = new Date(timestamp).getTime() / 1000;
          } else if (typeof timestamp === 'number') {
            time = timestamp > 1e10 ? timestamp / 1000 : timestamp;
          } else {
            console.error('[RSIChartContainer] Invalid timestamp:', timestamp);
            return null;
          }
          
          if (isNaN(time) || !isFinite(time)) {
            console.error('[RSIChartContainer] Invalid time conversion:', timestamp, '->', time);
            return null;
          }
          
          return {
            time: time as UTCTimestamp,
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];

      return lineData;

    } catch (error) {
      console.error('[RSIChartContainer] Error calculating RSI:', error);
      return [];
    }
  }, [symbol, timeframe]);

  // Track when price data is loaded to trigger indicator updates
  const [priceDataLoaded, setPriceDataLoaded] = useState(false);

  // Update RSI data when indicators change OR when price data becomes available
  useEffect(() => {
    if (!priceDataRef.current.length) {
      return;
    }

    const updateRSIIndicators = async () => {
      
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
  }, [indicators, priceDataLoaded, calculateRSIData]);

  // Load price data when symbol or timeframe changes
  useEffect(() => {
    if (symbol && timeframe && 
        (symbol !== currentSymbolRef.current || timeframe !== currentTimeframeRef.current)) {
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
    chartRef.current = chart;
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.registerChart(chartId, chart, `RSI Chart (${symbol})`);
    }
    
    // Notify parent that chart is ready for synchronization
    if (onChartReady) {
      onChartReady();
    }
  }, [chartSynchronizer, chartId, symbol, onChartReady]);

  // Handle chart destruction
  const handleChartDestroyed = useCallback(() => {
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
      preserveTimeScale={!!chartSynchronizer}
    />
  );
};

export default RSIChartContainer;