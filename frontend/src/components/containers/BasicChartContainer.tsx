import React, { FC, useState, useEffect, useCallback, useRef } from 'react';
import { IChartApi, CandlestickData, LineData, UTCTimestamp } from 'lightweight-charts';
import BasicChart, { ChartData, IndicatorSeries, ChartInfo } from '../presentation/charts/BasicChart';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { IndicatorInfo } from '../../store/indicatorRegistry';
import { createLogger } from '../../utils/logger';

/**
 * Container component for the basic price chart
 * 
 * This component handles all data loading, API calls, indicator calculations,
 * and state management, while delegating the chart rendering to the 
 * BasicChart presentation component.
 */

const logger = createLogger('BasicChartContainer');

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
  
  // Time range preservation
  initialTimeRange?: { start: string; end: string } | null;
  
  // Callbacks
  onDataLoaded?: (data: ChartData) => void;
  onChartCreated?: (chart: IChartApi) => void;
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
  initialTimeRange,
  onDataLoaded,
  onChartCreated,
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
      // Load data for last 3 months to match oscillator and fuzzy charts
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

  // Calculate indicator data
  const calculateIndicatorData = useCallback(async (
    baseData: CandlestickData[], 
    indicator: IndicatorInfo
  ): Promise<LineData[]> => {
    try {
      const indicatorId = indicator.name === 'sma' ? 'SimpleMovingAverage' : 
                         indicator.name === 'rsi' ? 'RSIIndicator' :
                         indicator.name === 'ema' ? 'ExponentialMovingAverage' : 
                         indicator.name === 'macd' ? 'MACDIndicator' :
                         indicator.name === 'zigzag' ? 'ZigZagIndicator' :
                         indicator.name;

      // Use ISO timestamps without timezone suffix (API expects this format)
      const startDate = new Date(baseData[0].time * 1000).toISOString().replace(/\.\d{3}Z$/, '');
      const endDate = new Date(baseData[baseData.length - 1].time * 1000).toISOString().replace(/\.\d{3}Z$/, '');

      // Build parameters based on indicator type
      let parameters: any = { source: 'close' };
      let outputName = '';
      
      if (indicator.name === 'zigzag') {
        parameters.threshold = indicator.parameters.threshold;
        outputName = `ZigZag_${(indicator.parameters.threshold * 100).toFixed(0)}`;
      } else {
        parameters.period = indicator.parameters.period;
        outputName = indicator.name === 'sma' ? `SMA_${indicator.parameters.period}` :
                    indicator.name === 'rsi' ? `RSI_${indicator.parameters.period}` :
                    indicator.name === 'ema' ? `EMA_${indicator.parameters.period}` :
                    indicator.name === 'macd' ? `MACD_${indicator.parameters.fast_period}_${indicator.parameters.slow_period}_${indicator.parameters.signal_period}` :
                    `${indicator.name.toUpperCase()}_${indicator.parameters.period}`;
      }
      
      // Handle MACD special case
      if (indicator.name === 'macd') {
        parameters = {
          fast_period: indicator.parameters.fast_period,
          slow_period: indicator.parameters.slow_period,
          signal_period: indicator.parameters.signal_period,
          source: 'close'
        };
      }

      const requestPayload = {
        symbol: symbol,
        timeframe: timeframe,
        start_date: startDate,
        end_date: endDate,
        indicators: [
          {
            id: indicatorId,
            parameters: parameters,
            output_name: outputName
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
        throw new Error(result.error?.message || 'Failed to calculate indicator');
      }

      const indicatorValues = result.indicators?.[outputName] || 
                             result.indicators?.[outputName.toLowerCase()] || 
                             [];

      const dates = result.dates || [];
      
      // Special handling for ZigZag: interpolate between extremes to create continuous lines
      if (indicator.name === 'zigzag') {
        // First, collect all the extreme points (non-null values)
        const extremes: { time: UTCTimestamp; value: number; index: number }[] = [];
        
        indicatorValues.forEach((value: number | null, index: number) => {
          if (value !== null && value !== undefined && dates[index] && 
              typeof value === 'number' && isFinite(value) && !isNaN(value)) {
            const timestamp = new Date(dates[index]).getTime() / 1000;
            if (isFinite(timestamp) && !isNaN(timestamp)) {
              extremes.push({
                time: timestamp as UTCTimestamp,
                value,
                index
              });
            }
          }
        });

        logger.debug('ZigZag extremes found', { count: extremes.length });

        if (extremes.length < 2) {
          // Not enough extremes to interpolate - return sparse data
          return indicatorValues
            .map((value: number | null, index: number) => {
              if (value === null || value === undefined || !dates[index]) return null;
              const timestamp = new Date(dates[index]).getTime() / 1000;
              return {
                time: timestamp as UTCTimestamp,
                value
              };
            })
            .filter((point: any) => point !== null) as LineData[];
        }

        // Interpolate between extremes to create continuous ZigZag lines
        const interpolatedData: LineData[] = [];
        
        for (let i = 0; i < extremes.length - 1; i++) {
          const startExtreme = extremes[i];
          const endExtreme = extremes[i + 1];
          
          // Add the start extreme
          interpolatedData.push({
            time: startExtreme.time,
            value: startExtreme.value
          });
          
          // Interpolate between start and end
          const startIndex = startExtreme.index;
          const endIndex = endExtreme.index;
          const valueDiff = endExtreme.value - startExtreme.value;
          const indexDiff = endIndex - startIndex;
          
          for (let j = startIndex + 1; j < endIndex; j++) {
            if (dates[j]) {
              const progress = (j - startIndex) / indexDiff;
              const interpolatedValue = startExtreme.value + (valueDiff * progress);
              const timestamp = new Date(dates[j]).getTime() / 1000;
              
              if (isFinite(timestamp) && !isNaN(timestamp)) {
                interpolatedData.push({
                  time: timestamp as UTCTimestamp,
                  value: interpolatedValue
                });
              }
            }
          }
        }
        
        // Add the final extreme
        const lastExtreme = extremes[extremes.length - 1];
        interpolatedData.push({
          time: lastExtreme.time,
          value: lastExtreme.value
        });

        logger.debug('ZigZag interpolated', { 
          extremes: extremes.length, 
          continuousPoints: interpolatedData.length 
        });
        return interpolatedData;
      }

      // Regular indicator processing for non-ZigZag indicators
      const lineData: LineData[] = indicatorValues
        .map((value: number | null, index: number) => {
          if (value === null || value === undefined || !dates[index] || 
              typeof value !== 'number' || !isFinite(value) || isNaN(value)) {
            return null;
          }
          
          const timestamp = new Date(dates[index]).getTime() / 1000;
          if (!isFinite(timestamp) || isNaN(timestamp)) {
            return null;
          }
          
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
        
        // Generate display name based on indicator type
        let displayName = '';
        if (indicator.name === 'zigzag') {
          displayName = `${indicator.displayName}(${(indicator.parameters.threshold * 100).toFixed(1)}%)`;
        } else if (indicator.name === 'macd') {
          displayName = `${indicator.displayName}(${indicator.parameters.fast_period},${indicator.parameters.slow_period},${indicator.parameters.signal_period})`;
        } else {
          displayName = `${indicator.displayName}(${indicator.parameters.period})`;
        }
        
        return {
          id: indicator.id,
          name: displayName,
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
    
    // Notify parent component
    if (onChartCreated) {
      onChartCreated(chart);
    }
  }, [chartSynchronizer, chartId, symbol, onChartCreated]);

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

  // Handle crosshair synchronization
  const handleCrosshairMove = useCallback((params: any) => {
    if (chartSynchronizer && chartId) {
      chartSynchronizer.synchronizeCrosshair(chartId, params);
    }
  }, [chartSynchronizer, chartId]);

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
      onCrosshairMove={handleCrosshairMove}
      showLoadingOverlay={true}
      showErrorOverlay={true}
      preserveTimeScale={!!chartSynchronizer}
      initialTimeRange={initialTimeRange}
    />
  );
};

export default BasicChartContainer;