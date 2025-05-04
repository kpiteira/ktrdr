/**
 * Chart factory functions for creating different chart types
 */
import { 
  IChartApi, 
  SeriesType, 
  CandlestickData, 
  LineData, 
  HistogramData,
  ColorType
} from 'lightweight-charts';
import { ThemeMode } from '../../types/ui';
import { 
  createCandlestickOptions, 
  createLineOptions, 
  createHistogramOptions 
} from './chartUtils';

/**
 * Creates a candlestick series on the chart
 * @param chart Chart instance
 * @param theme Current theme mode
 * @param data Optional initial data
 * @returns The created candlestick series
 */
export const createCandlestickSeries = (
  chart: IChartApi,
  theme: ThemeMode,
  data?: CandlestickData[]
) => {
  const series = chart.addCandlestickSeries(createCandlestickOptions(theme));
  
  if (data && data.length > 0) {
    series.setData(data);
  }
  
  return series;
};

/**
 * Creates a line series on the chart
 * @param chart Chart instance
 * @param color Line color
 * @param title Series title
 * @param data Optional initial data
 * @param lineWidth Line width
 * @param priceScaleId Price scale ID for the series
 * @returns The created line series
 */
export const createLineSeries = (
  chart: IChartApi,
  color: string,
  title?: string,
  data?: LineData[],
  lineWidth: number = 2,
  priceScaleId?: string
) => {
  const series = chart.addLineSeries({
    ...createLineOptions(color, lineWidth),
    title,
    priceScaleId,
  });
  
  if (data && data.length > 0) {
    series.setData(data);
  }
  
  return series;
};

/**
 * Creates a histogram series on the chart
 * @param chart Chart instance
 * @param color Base color for histogram
 * @param title Series title
 * @param data Optional initial data
 * @param priceScaleId Price scale ID for the series
 * @returns The created histogram series
 */
export const createHistogramSeries = (
  chart: IChartApi,
  color: string,
  title?: string,
  data?: HistogramData[],
  priceScaleId?: string
) => {
  const series = chart.addHistogramSeries({
    ...createHistogramOptions(color),
    title,
    priceScaleId,
  });
  
  if (data && data.length > 0) {
    series.setData(data);
  }
  
  return series;
};

/**
 * Creates a volume series as a histogram
 * @param chart Chart instance
 * @param data Optional initial data
 * @returns The created volume series
 */
export const createVolumeSeries = (
  chart: IChartApi,
  data?: HistogramData[]
) => {
  const series = chart.addHistogramSeries({
    color: 'rgba(38, 166, 154, 0.5)' as ColorType,
    priceFormat: {
      type: 'volume',
    },
    priceScaleId: 'volume',
    scaleMargins: {
      top: 0.8, // Start at 80% from the top
      bottom: 0,
    },
  });
  
  // Configure the price scale
  chart.priceScale('volume').applyOptions({
    scaleMargins: {
      top: 0.8,
      bottom: 0,
    },
    borderVisible: false,
  });
  
  if (data && data.length > 0) {
    series.setData(data);
  }
  
  return series;
};

/**
 * Creates a multi-panel chart with separate panels for indicators
 * @param chart Chart instance
 * @param indicators Array of indicator configs
 * @param mainPriceScaleId ID of the main price scale
 * @returns Map of created series by indicator ID
 */
export const createIndicatorPanels = (
  chart: IChartApi,
  indicators: Array<{
    id: string;
    type: 'line' | 'histogram';
    color: string;
    title: string;
    data?: LineData[] | HistogramData[];
    height?: number;
  }>,
  mainPriceScaleId?: string
) => {
  const seriesMap = new Map<string, any>();
  
  // Process each indicator
  indicators.forEach((indicator, index) => {
    const { id, type, color, title, data, height } = indicator;
    
    // Determine if this should be an overlay or separate panel
    const useMainScale = mainPriceScaleId && type === 'line' && height === undefined;
    const priceScaleId = useMainScale ? mainPriceScaleId : `indicator-${id}`;
    
    let series: any;
    
    if (type === 'line') {
      series = createLineSeries(chart, color, title, data as LineData[], 2, priceScaleId);
    } else {
      series = createHistogramSeries(chart, color, title, data as HistogramData[], priceScaleId);
    }
    
    // Configure separate panel if needed
    if (!useMainScale) {
      // Set scale margins based on the panel position
      chart.priceScale(priceScaleId).applyOptions({
        scaleMargins: {
          top: 0.2,
          bottom: 0.2,
        },
        visible: true,
        autoScale: true,
        alignLabels: true,
        borderVisible: true,
      });
    }
    
    seriesMap.set(id, series);
  });
  
  return seriesMap;
};