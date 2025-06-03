import { FC, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { IChartApi, LineData, UTCTimestamp, CandlestickData } from 'lightweight-charts';
import OscillatorChart, { OscillatorData, OscillatorIndicatorSeries } from '../presentation/charts/OscillatorChart';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { IndicatorInfo, getIndicatorConfig, getIndicatorFuzzyScaling } from '../../store/indicatorRegistry';
import { useFuzzyOverlay, ScalingConfig } from '../../hooks/useFuzzyOverlay';
import { createLogger } from '../../utils/logger';

/**
 * Generic container component for oscillator charts
 * 
 * This component handles all data loading, API calls, oscillator calculations,
 * and state management for oscillator-type indicators (RSI, MACD, Stochastic, etc.),
 * while delegating the chart rendering to the OscillatorChart presentation component.
 */

const logger = createLogger('OscillatorChartContainer');

/**
 * Container data interface - what the container provides to its children
 */
interface OscillatorContainerData {
  oscillatorData: OscillatorData | null;
  isLoading: boolean;
  error: string | null;
  fuzzyData: any;
  fuzzyVisible: boolean;
  fuzzyOpacity: number;
  fuzzyColorScheme: string;
}

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
  
  // Render prop for panel integration
  render?: (data: OscillatorContainerData) => React.ReactNode;
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
  oscillatorType = 'rsi', // Default to RSI for backward compatibility
  render
}) => {
  // Internal state
  const [oscillatorData, setOscillatorData] = useState<OscillatorData | null>(null);
  
  // Chart reference for synchronization
  const chartRef = useRef<IChartApi | null>(null);
  
  // Filter indicators to only oscillator types (chartType: 'separate')
  const oscillatorIndicators = useMemo(() => {
    return indicators.filter(ind => {
      const config = getIndicatorConfig(ind.name);
      return config?.chartType === 'separate';
    });
  }, [indicators]);

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
    
    // If we have MACD indicators, use MACD config
    const hasMACD = indicators.some(ind => ind.name === 'macd');
    if (hasMACD) {
      return {
        title: 'MACD Oscillator',
        yAxisRange: { min: undefined, max: undefined }, // Auto-scale for MACD
        referenceLines: [
          { value: 0, color: '#888888', label: 'Zero Line' }
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

  // Calculate date range for fuzzy data (same as price data)
  const dateRange = useMemo(() => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 3);
    return {
      start: startDate.toISOString().split('T')[0],
      end: endDate.toISOString().split('T')[0]
    };
  }, []);

  // Generate scaling configurations for all oscillator indicators dynamically
  const fuzzyScalingConfigs = useMemo(() => {
    const configs: Record<string, ScalingConfig> = {};
    
    oscillatorIndicators.forEach(indicator => {
      const scalingConfig = getIndicatorFuzzyScaling(
        indicator.name,
        oscillatorData || undefined,
        indicator.id
      );
      
      if (scalingConfig) {
        configs[indicator.id] = scalingConfig;
      }
    });
    
    return configs;
  }, [oscillatorIndicators, oscillatorData]);

  // Get the primary indicator for this container (assumes single indicator type per container)
  const primaryIndicator = oscillatorIndicators[0];
  
  // GENERIC fuzzy overlay hook - only for the primary indicator in this container
  const fuzzyOverlay = useFuzzyOverlay(
    primaryIndicator?.id || 'no-indicator',
    symbol,
    timeframe,
    dateRange,
    primaryIndicator?.fuzzyVisible,
    primaryIndicator ? fuzzyScalingConfigs[primaryIndicator.id] : undefined
  );

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
            parameters: indicator.name === 'macd' ? {
              fast_period: indicator.parameters.fast_period,
              slow_period: indicator.parameters.slow_period,
              signal_period: indicator.parameters.signal_period,
              source: 'close'
            } : {
              period: indicator.parameters.period,
              source: 'close'
            },
            output_name: indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                        indicator.name === 'macd' ? `MACD_${indicator.parameters.fast_period}_${indicator.parameters.slow_period}` :
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

      const dates = result.dates || [];
      
      // Handle MACD multi-series (MACD line, Signal line, Histogram)
      if (indicator.name === 'macd') {
        const macdLineKey = `MACD_${indicator.parameters.fast_period}_${indicator.parameters.slow_period}`;
        const signalLineKey = `MACD_signal_${indicator.parameters.fast_period}_${indicator.parameters.slow_period}_${indicator.parameters.signal_period}`;
        const histogramKey = `MACD_hist_${indicator.parameters.fast_period}_${indicator.parameters.slow_period}_${indicator.parameters.signal_period}`;
        
        const macdValues = result.indicators?.[macdLineKey] || [];
        const signalValues = result.indicators?.[signalLineKey] || [];
        const histogramValues = result.indicators?.[histogramKey] || [];
        
        // Transform to line data format
        const transformToLineData = (values: number[]) => 
          values
            .map((value: number | null, index: number) => {
              if (value === null || value === undefined || !dates[index]) return null;
              
              const timestamp = new Date(dates[index]).getTime() / 1000;
              
              return {
                time: timestamp as UTCTimestamp,
                value
              };
            })
            .filter((point: any) => point !== null) as LineData[];
        
        // Return multi-series data for MACD
        return {
          macd: transformToLineData(macdValues),
          signal: transformToLineData(signalValues),
          histogram: transformToLineData(histogramValues)
        };
      }
      
      // Handle single-series indicators (RSI, etc.)
      const outputName = indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                        `${indicator.name.toUpperCase()}_${indicator.parameters.period}`;
                         
      const oscillatorValues = result.indicators?.[outputName] || 
                              result.indicators?.[outputName.toLowerCase()] || 
                              [];
      
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
      console.warn(`[OscillatorChartContainer] Failed to calculate ${indicator.name}:`, error);
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
          try {
            const indicatorData = await calculateOscillatorData(indicator, priceData);
            
            // Handle MACD multi-series data
            if (indicator.name === 'macd' && indicatorData && typeof indicatorData === 'object' && 'macd' in indicatorData) {
              const macdData = indicatorData as { macd: LineData[]; signal: LineData[]; histogram: LineData[] };
              
              return [
                {
                  id: `${indicator.id}-macd`,
                  name: `${indicator.displayName} Line`,
                  data: macdData.macd,
                  color: '#2196F3', // Bright blue for better visibility
                  visible: indicator.visible,
                  type: 'line' as const
                },
                {
                  id: `${indicator.id}-signal`,
                  name: `${indicator.displayName} Signal`,
                  data: macdData.signal,
                  color: '#FF5722', // Orange-red for signal line
                  visible: indicator.visible,
                  type: 'line' as const
                },
                {
                  id: `${indicator.id}-histogram`,
                  name: `${indicator.displayName} Histogram`,
                  data: macdData.histogram,
                  color: '#9E9E9E', // Light gray for less intrusive histogram
                  visible: indicator.visible,
                  type: 'histogram' as const
                }
              ];
            }
            
            // Handle single-series indicators (RSI, etc.)
            return [{
              id: indicator.id,
              name: indicator.displayName,
              data: indicatorData as LineData[],
              color: indicator.parameters.color || '#FF5722',
              visible: indicator.visible,
              type: 'line' as const
            }];
          } catch (error) {
            console.warn(`[OscillatorChartContainer] Skipping failed indicator ${indicator.name}:`, error);
            // Return indicator with empty data instead of failing completely
            return [{
              id: indicator.id,
              name: indicator.displayName,
              data: [],
              color: indicator.parameters.color || '#FF5722',
              visible: indicator.visible,
              type: 'line' as const
            }];
          }
        });
        
        const oscillatorSeriesArrays = await Promise.all(oscillatorPromises);
        // Flatten the arrays since each indicator can return multiple series (especially MACD)
        const oscillatorSeries = oscillatorSeriesArrays.flat();

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
  }, [oscillatorIndicators, priceData, symbol, timeframe]);

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
  
  // console.log(`🔄 [OscillatorChartContainer] Synchronization state:`, {
  //   chartSynchronizer: !!chartSynchronizer,
  //   preserveTimeScale,
  //   chartId,
  //   symbol,
  //   timeframe
  // });

  // Only render if we have oscillator indicators
  if (oscillatorIndicators.length === 0) {
    return null;
  }


  // GENERIC fuzzy overlay data - let the hook control visibility, don't double-check
  const activeFuzzyData = fuzzyOverlay.isVisible ? fuzzyOverlay.fuzzyData : null;
  const activeFuzzyVisible = fuzzyOverlay.isVisible;
  const activeFuzzyOpacity = primaryIndicator?.fuzzyOpacity || fuzzyOverlay.opacity;
  const activeFuzzyColorScheme = primaryIndicator?.fuzzyColorScheme || fuzzyOverlay.colorScheme;


  // Prepare container data for render prop or direct rendering
  const containerData: OscillatorContainerData = {
    oscillatorData,
    isLoading,
    error,
    fuzzyData: activeFuzzyData,
    fuzzyVisible: activeFuzzyVisible,
    fuzzyOpacity: activeFuzzyOpacity,
    fuzzyColorScheme: activeFuzzyColorScheme
  };

  // Use render prop if provided, otherwise render OscillatorChart directly
  if (render) {
    return <>{render(containerData)}</>;
  }

  return (
    <OscillatorChart
      width={width}
      height={height}
      oscillatorData={oscillatorData}
      isLoading={isLoading}
      error={error}
      fuzzyData={activeFuzzyData}
      fuzzyVisible={activeFuzzyVisible}
      fuzzyOpacity={activeFuzzyOpacity}
      fuzzyColorScheme={activeFuzzyColorScheme}
      onChartCreated={handleChartCreated}
      onChartDestroyed={handleChartDestroyed}
      onCrosshairMove={handleCrosshairMove}
      preserveTimeScale={preserveTimeScale}
      oscillatorConfig={getOscillatorConfig()}
    />
  );
};

export default OscillatorChartContainer;
export type { OscillatorContainerData };