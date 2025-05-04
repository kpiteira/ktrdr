/**
 * Utility functions for charts
 */
import { 
  ChartOptions, 
  DeepPartial, 
  IChartApi, 
  LineSeriesOptions, 
  CandlestickSeriesOptions,
  HistogramSeriesOptions,
  PriceLineOptions,
  SeriesType,
  ChartRow,
  CandlestickData,
  LineData,
  HistogramData,
  ColorType
} from 'lightweight-charts';
import { ThemeMode } from '../../types/ui';
import { ChartConfig, ChartTheme, chartThemes } from '../../types/charts';
import { OHLCVData } from '../../types/data';

/**
 * Creates chart options based on config and theme
 * @param config Chart configuration
 * @returns Chart options for lightweight-charts
 */
export const createChartOptions = (config: ChartConfig): DeepPartial<ChartOptions> => {
  const theme = config.theme || 'light';
  const themeSettings = chartThemes[theme];
  
  return {
    width: config.width,
    height: config.height,
    layout: {
      background: { 
        type: 'solid', 
        color: themeSettings.backgroundColor 
      },
      textColor: themeSettings.textColor,
      fontFamily: config.fontFamily || '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", sans-serif',
    },
    grid: {
      vertLines: { color: themeSettings.gridLinesColor },
      horzLines: { color: themeSettings.gridLinesColor },
    },
    crosshair: {
      vertLine: {
        color: themeSettings.crosshairColor,
        width: 1,
        style: 2, // Dashed
        visible: true,
        labelVisible: true,
      },
      horzLine: {
        color: themeSettings.crosshairColor,
        width: 1,
        style: 2, // Dashed
        visible: true,
        labelVisible: true,
      },
      mode: 1, // CrosshairMode.Normal
    },
    timeScale: {
      timeVisible: config.timeVisible ?? true,
      secondsVisible: config.secondsVisible ?? false,
      borderColor: themeSettings.gridLinesColor,
    },
    watermark: {
      color: themeSettings.watermarkColor,
      visible: false,
    },
    autoSize: config.autoResize ?? true,
  };
};

/**
 * Creates style options for a candlestick series based on the theme
 * @param theme Current theme mode
 * @returns Candlestick style options
 */
export const createCandlestickOptions = (theme: ThemeMode): DeepPartial<CandlestickSeriesOptions> => {
  const themeSettings = chartThemes[theme];
  
  return {
    upColor: themeSettings.candlestick.upColor as ColorType,
    downColor: themeSettings.candlestick.downColor as ColorType,
    wickUpColor: themeSettings.candlestick.wickUpColor as ColorType,
    wickDownColor: themeSettings.candlestick.wickDownColor as ColorType,
    borderUpColor: themeSettings.candlestick.borderUpColor as ColorType,
    borderDownColor: themeSettings.candlestick.borderDownColor as ColorType,
    borderVisible: true,
    wickVisible: true,
  };
};

/**
 * Creates style options for a line series
 * @param color Line color
 * @param lineWidth Line width
 * @returns Line style options
 */
export const createLineOptions = (
  color: string,
  lineWidth: number = 2
): DeepPartial<LineSeriesOptions> => {
  return {
    color: color as ColorType,
    lineWidth,
    lineType: 0, // Solid
    lineJoin: 'round',
    lineCap: 'round',
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 4,
    lastValueVisible: true,
  };
};

/**
 * Creates style options for a histogram series
 * @param color Histogram color
 * @returns Histogram style options
 */
export const createHistogramOptions = (
  color: string
): DeepPartial<HistogramSeriesOptions> => {
  return {
    color: color as ColorType,
    base: 0,
  };
};

/**
 * Converts OHLCV data to candlestick data for the chart
 * @param data OHLCV data
 * @returns Formatted candlestick data for the chart
 */
export const formatCandlestickData = (data: OHLCVData): CandlestickData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, high, low, close, _volume] = data.ohlcv[index];
    
    // Convert date string to timestamp
    // This handles ISO date strings and UNIX timestamps
    const timestamp = typeof date === 'string' 
      ? new Date(date).getTime() / 1000 as number
      : date as number;
    
    return {
      time: timestamp as number,
      open,
      high,
      low,
      close,
    };
  });
};

/**
 * Converts OHLCV data to volume histogram data
 * @param data OHLCV data
 * @param positiveColor Color for positive volume bars
 * @param negativeColor Color for negative volume bars
 * @returns Formatted histogram data for volume
 */
export const formatVolumeData = (
  data: OHLCVData,
  positiveColor: string = 'rgba(38, 166, 154, 0.5)',
  negativeColor: string = 'rgba(239, 83, 80, 0.5)'
): HistogramData[] => {
  if (!data || !data.dates || !data.ohlcv || data.dates.length === 0) {
    return [];
  }

  return data.dates.map((date, index) => {
    const [open, _high, _low, close, volume] = data.ohlcv[index];
    
    // Convert date string to timestamp
    const timestamp = typeof date === 'string' 
      ? new Date(date).getTime() / 1000 as number
      : date as number;
    
    return {
      time: timestamp as number,
      value: volume,
      color: close >= open ? positiveColor : negativeColor,
    };
  });
};

/**
 * Creates a price line on a series
 * @param chart Chart instance
 * @param series Series instance
 * @param price Price level
 * @param color Line color
 * @param lineWidth Line width
 * @param lineStyle Line style
 * @param text Line label text
 * @returns Price line options
 */
export const createPriceLine = (
  price: number,
  color: string = 'rgba(114, 116, 119, 0.5)',
  lineWidth: number = 1,
  lineStyle: number = 2, // Dashed
  text?: string
): DeepPartial<PriceLineOptions> => {
  return {
    price,
    color: color as ColorType,
    lineWidth,
    lineStyle,
    lineVisible: true,
    axisLabelVisible: true,
    title: text,
  };
};

/**
 * Handles chart resize on window resize events
 * @param chart Chart instance
 * @param container Container element reference
 */
export const handleChartResize = (
  chart: IChartApi | null,
  container: HTMLElement | null
): void => {
  if (!chart || !container) return;
  
  const { width, height } = container.getBoundingClientRect();
  chart.resize(width, height);
};

/**
 * Cleans up chart resources
 * @param chart Chart instance
 */
export const cleanupChart = (chart: IChartApi | null): void => {
  if (chart) {
    chart.remove();
  }
};