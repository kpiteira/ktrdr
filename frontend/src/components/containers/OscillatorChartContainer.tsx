import { FC, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { IChartApi, LineData, UTCTimestamp, CandlestickData } from 'lightweight-charts';
import OscillatorChart, { OscillatorData, OscillatorIndicatorSeries } from '../presentation/charts/OscillatorChart';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { IndicatorInfo, getIndicatorConfig } from '../../store/indicatorRegistry';
import { createLogger } from '../../utils/logger';

/**
 * Generic container component for oscillator charts
 * 
 * This component handles all data loading, API calls, oscillator calculations,
 * and state management for oscillator-type indicators (RSI, MACD, Stochastic, etc.),
 * while delegating the chart rendering to the OscillatorChart presentation component.
 */

const logger = createLogger('OscillatorChartContainer');

interface OscillatorChartContainerProps {
  // Chart configuration
  width?: number;
  height?: number;
  
  // Data props
  symbol: string;
  timeframe: string;
  
  // Indicator data from parent - filtered to only oscillator types
  indicators?: IndicatorInfo[];
  
  // Chart synchronization
  chartSynchronizer?: ReturnType<typeof useChartSynchronizer>;
  chartId?: string;
  
  // Synchronization with main chart
  timeRange?: { start: string; end: string } | null;
  
  // Callbacks
  onDataLoaded?: (data: OscillatorData) => void;
  onError?: (error: string) => void;
  onChartReady?: () => void;
  
  // Oscillator-specific configuration
  oscillatorType?: 'rsi' | 'macd' | 'stochastic' | 'williams'; // Default configs for common types
}

const OscillatorChartContainer: FC<OscillatorChartContainerProps> = ({
  width = 800,
  height = 200,
  symbol,
  timeframe,
  indicators = [],
  chartSynchronizer,
  chartId = 'oscillator-chart',
  timeRange, // Currently unused but kept for future time-based filtering
  onDataLoaded,
  onError,
  onChartReady,
  oscillatorType = 'rsi' // Default to RSI for backward compatibility
}) => {
  // Internal state
  const [oscillatorData, setOscillatorData] = useState<OscillatorData | null>(null);
  
  // Chart reference for synchronization
  const chartRef = useRef<IChartApi | null>(null);
  
  // Get oscillator configuration based on the indicators we have
  const getOscillatorConfig = useCallback(() => {
    // If we have RSI indicators, use RSI config
    const hasRSI = indicators.some(ind => ind.name === 'rsi');
    if (hasRSI) {
      return {
        title: 'RSI Oscillator',
        yAxisRange: { min: 0, max: 100 },
        referenceLines: [
          { value: 30, color: '#888888', label: 'Oversold' },
          { value: 70, color: '#888888', label: 'Overbought' }
        ]
      };
    }
    
    // Default oscillator config
    return {
      title: 'Oscillator',
      yAxisRange: { min: 0, max: 100 },
      referenceLines: []
    };
  }, [indicators]);

  // Filter indicators to only oscillator types (chartType: 'separate')
  const oscillatorIndicators = useMemo(() => {
    return indicators.filter(ind => {
      const config = getIndicatorConfig(ind.name);
      return config?.chartType === 'separate';
    });
  }, [indicators]);

  // Internal state
  const [priceData, setPriceData] = useState<CandlestickData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load price data
  const loadPriceData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Calculate dates for last 3 months
      const endDate = new Date();
      const startDate = new Date();
      startDate.setMonth(startDate.getMonth() - 3);
      
      // Build query parameters for date filtering
      const params = new URLSearchParams({
        start_date: startDate.toISOString().split('T')[0],
        end_date: endDate.toISOString().split('T')[0]
      });
      
      const response = await fetch(`/api/v1/data/${symbol}/${timeframe}?${params.toString()}`);

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

  // Calculate oscillator data for a given indicator
  const calculateOscillatorData = useCallback(async (indicator: IndicatorInfo, baseData: CandlestickData[]) => {
    try {
      const indicatorId = indicator.name === 'rsi' ? 'RSIIndicator' : 
                         indicator.name === 'macd' ? 'MACDIndicator' :
                         indicator.name === 'stochastic' ? 'StochasticIndicator' :
                         indicator.name;

      // Use ISO timestamps without timezone suffix (API expects this format)
      const startDate = new Date(baseData[0].time * 1000).toISOString().replace(/\.\d{3}Z$/, '');
      const endDate = new Date(baseData[baseData.length - 1].time * 1000).toISOString().replace(/\.\d{3}Z$/, '');

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
            output_name: indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                        indicator.name === 'macd' ? `MACD_${indicator.parameters.period}` :
                        `${indicator.name.toUpperCase()}_${indicator.parameters.period}`
          }
        ]
      };
      
      const response = await fetch('/api/v1/indicators/calculate?page_size=10000', {
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
        throw new Error(result.error?.message || 'Failed to calculate oscillator');
      }

      const outputName = indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                        indicator.name === 'macd' ? `MACD_${indicator.parameters.period}` :
                        `${indicator.name.toUpperCase()}_${indicator.parameters.period}`;
                         
      const oscillatorValues = result.indicators?.[outputName] || 
                              result.indicators?.[outputName.toLowerCase()] || 
                              [];

      const dates = result.dates || [];
      
      // Map oscillator values to line data using the dates from the response
      const lineData: LineData[] = oscillatorValues
        .map((value: number | null, index: number) => {
          if (value === null || value === undefined || !dates[index]) return null;
          
          const timestamp = new Date(dates[index]).getTime() / 1000;
          
          return {
            time: timestamp as UTCTimestamp,
            value
          };
        })
        .filter((point: any) => point !== null) as LineData[];
        
      return lineData;

    } catch (error) {
      return [];
    }
  }, [symbol, timeframe]);

  // Main effect to calculate and update oscillator data
  useEffect(() => {
    if (oscillatorIndicators.length === 0) {
      setOscillatorData({ indicators: [] });
      return;
    }

    if (!priceData.length) {
      return;
    }

    const updateOscillatorData = async () => {
      try {
        // Calculate data for each oscillator indicator in parallel
        const oscillatorPromises = oscillatorIndicators.map(async (indicator) => {
          const indicatorData = await calculateOscillatorData(indicator, priceData);
          
          return {
            id: indicator.id,
            name: indicator.displayName,
            data: indicatorData,
            color: indicator.parameters.color || '#FF5722',
            visible: indicator.visible
          };
        });
        
        const oscillatorSeries = await Promise.all(oscillatorPromises);

        const newOscillatorData: OscillatorData = {
          indicators: oscillatorSeries
        };

        setOscillatorData(newOscillatorData);
        
        if (onDataLoaded) {
          onDataLoaded(newOscillatorData);
        }

      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to update oscillator data';
        if (onError) {
          onError(errorMessage);
        }
      }
    };

    updateOscillatorData();
  }, [oscillatorIndicators, priceData, calculateOscillatorData, onDataLoaded, onError]);

  // Load price data when symbol/timeframe changes
  useEffect(() => {
    if (symbol && timeframe) {
      loadPriceData();
    }
  }, [symbol, timeframe, loadPriceData]);

  // Chart synchronization integration
  const handleChartCreated = useCallback((chart: IChartApi) => {
    chartRef.current = chart;
    
    if (chartSynchronizer && chartId) {
      chartSynchronizer.registerChart(chartId, chart);
    }
    
    if (onChartReady) {
      onChartReady();
    }
  }, [chartSynchronizer, chartId, onChartReady]);

  const handleChartDestroyed = useCallback(() => {
    if (chartSynchronizer && chartId) {
      chartSynchronizer.unregisterChart(chartId);
    }
    chartRef.current = null;
  }, [chartSynchronizer, chartId]);

  // Handle crosshair synchronization
  const handleCrosshairMove = useCallback((params: any) => {
    if (chartSynchronizer && chartId) {
      chartSynchronizer.synchronizeCrosshair(chartId, params);
    }
  }, [chartSynchronizer, chartId]);

  // Calculate preserve time scale based on synchronization
  const preserveTimeScale = !!chartSynchronizer;

  // Only render if we have oscillator indicators
  if (oscillatorIndicators.length === 0) {
    return null;
  }

  return (
    <OscillatorChart
      width={width}
      height={height}
      oscillatorData={oscillatorData}
      isLoading={isLoading}
      error={error}
      onChartCreated={handleChartCreated}
      onChartDestroyed={handleChartDestroyed}
      onCrosshairMove={handleCrosshairMove}
      preserveTimeScale={preserveTimeScale}
      oscillatorConfig={getOscillatorConfig()}
    />
  );
};

export default OscillatorChartContainer;