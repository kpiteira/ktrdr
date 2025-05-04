import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  IChartApi, 
  CandlestickData, 
  LogicalRangeChangeEventHandler,
  CandlestickSeriesOptions,
  HistogramSeriesOptions,
  SeriesType,
  ColorType
} from 'lightweight-charts';
import { useTheme } from '../layouts/ThemeProvider';
import { ChartContainer } from './ChartContainer';
import { ChartControls } from './ChartControls';
import { OHLCVData } from '../../types/data';
import { 
  formatCandlestickData, 
  formatVolumeData,
  createCandlestickOptions,
  downsampleOHLCVData,
  shouldDownsample,
  throttle,
  incrementalDataLoader
} from '../../utils/charts';

export interface CandlestickChartProps {
  /** OHLCV data to display */
  data: OHLCVData;
  /** Chart width (default: 100%) */
  width?: number;
  /** Chart height (default: 400px) */
  height?: number;
  /** Whether to show volume (default: true) */
  showVolume?: boolean;
  /** Ratio for volume panel height (default: 0.2) */
  volumeRatio?: number;
  /** Whether to fit content on init (default: true) */
  fitContent?: boolean;
  /** Whether to show grid lines (default: true) */
  showGrid?: boolean;
  /** Whether to use performance optimizations (default: true) */
  optimizePerformance?: boolean;
  /** Target number of points to display for performance (default: 500) */
  targetPoints?: number;
  /** Whether to load data incrementally for large datasets (default: true) */
  incrementalLoading?: boolean;
  /** Show chart controls (default: true) */
  showControls?: boolean;
  /** Callback when crosshair moves */
  onCrosshairMove?: (param: any) => void;
  /** Custom class name */
  className?: string;
}

/**
 * CandlestickChart component
 * 
 * Renders a candlestick chart with optional volume display
 */
export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  width,
  height = 400,
  showVolume = true,
  volumeRatio = 0.2,
  fitContent = true,
  showGrid = true,
  optimizePerformance = true,
  targetPoints = 500,
  incrementalLoading = true,
  showControls = true,
  onCrosshairMove,
  className = '',
}) => {
  const { theme } = useTheme();
  const [chart, setChart] = useState<IChartApi | null>(null);
  const [candlestickSeries, setCandlestickSeries] = useState<ReturnType<typeof IChartApi.prototype.addCandlestickSeries> | null>(null);
  const [volumeSeries, setVolumeSeries] = useState<ReturnType<typeof IChartApi.prototype.addHistogramSeries> | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [displayData, setDisplayData] = useState<OHLCVData | null>(null);
  const [visibleRange, setVisibleRange] = useState<{ from: number; to: number } | null>(null);
  const [volumeVisible, setVolumeVisible] = useState<boolean>(showVolume);
  
  const mainPriceScaleRef = useRef<string | null>(null);
  const volumePriceScaleRef = useRef<string | null>(null);
  const isInitializedRef = useRef<boolean>(false);

  // Handle visible range changes for data optimization
  const handleVisibleRangeChange = useCallback<LogicalRangeChangeEventHandler>((range) => {
    if (range && optimizePerformance) {
      setVisibleRange(range);
    }
  }, [optimizePerformance]);

  // Throttle the range change handler to avoid excessive updates
  const throttledRangeChangeHandler = useCallback(
    throttle(handleVisibleRangeChange, 300),
    [handleVisibleRangeChange]
  );

  // Process data with optimizations when needed
  useEffect(() => {
    if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
      setDisplayData(null);
      return;
    }

    setIsLoading(true);

    if (incrementalLoading && data.dates.length > 1000 && !isInitializedRef.current) {
      // Use incremental loading for large datasets on initial load
      incrementalDataLoader(
        data,
        300, // Initial points
        200, // Batch size
        (batchData) => {
          setDisplayData(batchData);
        },
        () => {
          setIsLoading(false);
          isInitializedRef.current = true;
        }
      );
    } else if (optimizePerformance && shouldDownsample(visibleRange, data.dates.length)) {
      // Downsample data for better performance if needed
      const optimizedData = downsampleOHLCVData(data, targetPoints);
      setDisplayData(optimizedData);
      setIsLoading(false);
    } else {
      // Use full data
      setDisplayData(data);
      setIsLoading(false);
    }
  }, [data, optimizePerformance, incrementalLoading, visibleRange, targetPoints]);

  // Toggle volume visibility
  const handleVolumeToggle = useCallback(() => {
    setVolumeVisible((prev) => !prev);
  }, []);

  // Handle chart initialization
  const handleChartReady = useCallback((chartInstance: IChartApi) => {
    setChart(chartInstance);

    try {
      // Add candlestick series with v5 API
      const newCandlestickSeries = chartInstance.addCandlestickSeries(
        createCandlestickOptions(theme)
      );
      setCandlestickSeries(newCandlestickSeries);
      mainPriceScaleRef.current = newCandlestickSeries.priceScale().id();

      // Register for time range changes (for optimization)
      chartInstance.timeScale().subscribeVisibleTimeRangeChange(throttledRangeChangeHandler);

      // Set volume series if needed
      if (volumeVisible) {
        // Create separate pane for volume with specific height ratio
        const newVolumeSeries = chartInstance.addHistogramSeries({
          color: '#26a69a' as ColorType,
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'volume',
          scaleMargins: {
            top: 0.8, // Start at 80% from the top
            bottom: 0,
          },
        });

        setVolumeSeries(newVolumeSeries);
        volumePriceScaleRef.current = newVolumeSeries.priceScale().id();

        // Configure the price scale
        chartInstance.priceScale('volume').applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
          borderVisible: false,
        });
      }
    } catch (err) {
      console.error('Error initializing chart:', err);
    }
  }, [theme, volumeVisible, throttledRangeChangeHandler]);

  // Update data when displayData changes
  useEffect(() => {
    if (!candlestickSeries || !displayData) return;

    const candleData = formatCandlestickData(displayData);
    candlestickSeries.setData(candleData);

    if (volumeVisible && volumeSeries) {
      const volumeData = formatVolumeData(displayData);
      volumeSeries.setData(volumeData);
    }

    if (fitContent && chart && displayData.dates.length > 0) {
      chart.timeScale().fitContent();
    }
  }, [displayData, candlestickSeries, volumeSeries, chart, volumeVisible, fitContent]);

  // Update theme
  useEffect(() => {
    if (candlestickSeries) {
      candlestickSeries.applyOptions(createCandlestickOptions(theme));
    }
  }, [theme, candlestickSeries]);

  // Update volume visibility
  useEffect(() => {
    if (!chart || !candlestickSeries || !displayData) return;

    if (volumeVisible && !volumeSeries) {
      try {
        // Add volume series if it doesn't exist
        const newVolumeSeries = chart.addHistogramSeries({
          color: '#26a69a' as ColorType,
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'volume',
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
        });

        setVolumeSeries(newVolumeSeries);
        volumePriceScaleRef.current = newVolumeSeries.priceScale().id();

        // Configure the price scale
        chart.priceScale('volume').applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
          borderVisible: false,
        });

        // Set data if available
        const volumeData = formatVolumeData(displayData);
        newVolumeSeries.setData(volumeData);
      } catch (err) {
        console.error('Error adding volume series:', err);
      }
    } else if (!volumeVisible && volumeSeries) {
      // Remove volume series if it exists but shouldn't
      try {
        chart.removeSeries(volumeSeries);
        setVolumeSeries(null);
      } catch (err) {
        console.error('Error removing volume series:', err);
      }
    }
  }, [volumeVisible, chart, volumeSeries, candlestickSeries, displayData]);

  return (
    <div className={`candlestick-chart-wrapper ${className}`} style={{ position: 'relative' }}>
      <ChartContainer
        width={width}
        height={height}
        className={`candlestick-chart ${isLoading ? 'loading' : ''}`}
        onChartReady={handleChartReady}
        onCrosshairMove={onCrosshairMove}
        onVisibleTimeRangeChange={throttledRangeChangeHandler}
        chartOptions={{
          timeVisible: true,
          fitContentOnInit: fitContent,
        }}
      />
      
      {showControls && chart && (
        <ChartControls
          chart={chart}
          showVolumeToggle={true}
          volumeVisible={volumeVisible}
          onVolumeToggle={handleVolumeToggle}
        />
      )}
      
      {isLoading && (
        <div className="chart-loading">
          Loading...
        </div>
      )}
      
      {!displayData && !isLoading && (
        <div className="chart-no-data">
          No data available
        </div>
      )}
    </div>
  );
};

export default CandlestickChart;