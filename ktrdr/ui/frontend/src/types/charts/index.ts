import { Time, LineData, CandlestickData, HistogramData, UTCTimestamp, SeriesType } from 'lightweight-charts';
import { ThemeMode } from '../ui';

/**
 * Represents the configuration for a chart
 */
export interface ChartConfig {
  /** Width of the chart in pixels */
  width?: number;
  /** Height of the chart in pixels */
  height?: number;
  /** Whether to automatically resize the chart when container size changes */
  autoResize?: boolean;
  /** Theme to use for the chart (light or dark) */
  theme?: ThemeMode;
  /** Custom font family for chart text */
  fontFamily?: string;
  /** Whether to show the time scale (x-axis) */
  timeVisible?: boolean;
  /** Whether to show seconds in the time scale */
  secondsVisible?: boolean;
  /** Whether to fit all data in the visible range on initial render */
  fitContentOnInit?: boolean;
}

/**
 * Chart data types supported by lightweight-charts
 */
export type ChartData = LineData | CandlestickData | HistogramData;

/**
 * Configuration for a series on the chart
 */
export interface SeriesConfig {
  /** Type of series to add to the chart */
  type: SeriesType;
  /** Data for the series */
  data: ChartData[];
  /** Title to display for the series */
  title?: string;
  /** Color for the series */
  color?: string;
  /** Line width (for line series) */
  lineWidth?: number;
  /** Whether to show the series */
  visible?: boolean;
  /** Price line configuration */
  priceLine?: {
    /** Whether to show the last value line */
    show?: boolean;
    /** Color of the price line */
    color?: string;
    /** Width of the price line */
    width?: number;
    /** Style of the price line ('solid', 'dashed', etc.) */
    style?: number;
  };
}

/**
 * Options specific to candlestick series
 */
export interface CandlestickOptions {
  /** Color of the up candles */
  upColor?: string;
  /** Color of the down candles */
  downColor?: string;
  /** Color of the wick */
  wickUpColor?: string;
  /** Color of the wick */
  wickDownColor?: string;
  /** Color of the border of candles */
  borderUpColor?: string;
  /** Color of the border of candles */
  borderDownColor?: string;
  /** Width of the border of candles */
  borderVisible?: boolean;
  /** Whether to draw the candles as hollow candles */
  wickVisible?: boolean;
}

/**
 * Options specific to line series
 */
export interface LineOptions {
  /** Color of the line */
  color?: string;
  /** Width of the line */
  lineWidth?: number;
  /** Style of the line */
  lineStyle?: number;
  /** Type of the line join */
  lineJoin?: 'round' | 'bevel' | 'miter';
  /** Type of the line cap */
  lineCap?: 'butt' | 'round' | 'square';
  /** Whether to show the point markers */
  pointMarkersVisible?: boolean;
  /** Radius of the point markers */
  pointMarkersRadius?: number;
}

/**
 * Options specific to histogram series
 */
export interface HistogramOptions {
  /** Color of the histogram columns */
  color?: string;
  /** Base value for the histogram */
  base?: number;
}

/**
 * Theme configuration for the chart
 */
export interface ChartTheme {
  /** Background color of the chart */
  backgroundColor: string;
  /** Text color used in the chart */
  textColor: string;
  /** Color of the vertical grid lines */
  gridLinesColor: string;
  /** Color of the horizontal grid lines */
  crosshairColor: string;
  /** Color of the watermark */
  watermarkColor: string;
  /** Candlestick theme configuration */
  candlestick: {
    upColor: string;
    downColor: string;
    wickUpColor: string;
    wickDownColor: string;
    borderUpColor: string;
    borderDownColor: string;
  };
}

/**
 * Chart themes for light and dark mode
 */
export const chartThemes: Record<ThemeMode, ChartTheme> = {
  light: {
    backgroundColor: '#FFFFFF',
    textColor: '#191919',
    gridLinesColor: '#E6E6E6',
    crosshairColor: '#989898',
    watermarkColor: 'rgba(0, 0, 0, 0.1)',
    candlestick: {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
    },
  },
  dark: {
    backgroundColor: '#1E1E1E',
    textColor: '#D9D9D9',
    gridLinesColor: '#2B2B43',
    crosshairColor: '#758696',
    watermarkColor: 'rgba(255, 255, 255, 0.1)',
    candlestick: {
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
    },
  },
};