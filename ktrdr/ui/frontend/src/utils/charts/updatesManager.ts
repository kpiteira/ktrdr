/**
 * Chart Updates Manager
 * 
 * Provides utilities for efficiently updating chart data with new data points
 * and optimizing real-time data streams.
 */
import { 
  ISeriesApi, 
  SeriesType, 
  CandlestickData, 
  LineData, 
  HistogramData,
  BarData,
  IChartApi
} from 'lightweight-charts';
import { OHLCVData } from '../../types/data';
import { 
  formatCandlestickData, 
  formatLineData, 
  formatHistogramData,
  formatBarData,
  createUpdateData
} from './chartDataUtils';

/**
 * Update modes for chart data
 */
export enum UpdateMode {
  /** Replace all data */
  REPLACE = 'replace',
  /** Append new data points only */
  APPEND = 'append',
  /** Update last point and append new ones */
  UPDATE_LAST_AND_APPEND = 'update_last_and_append',
  /** Update visible range only */
  VISIBLE_RANGE_ONLY = 'visible_range_only'
}

/**
 * Options for ChartUpdater
 */
export interface ChartUpdaterOptions {
  /** Maximum number of points to keep in memory (0 for unlimited) */
  maxPoints?: number;
  /** Default update mode */
  defaultUpdateMode?: UpdateMode;
  /** Default update interval in milliseconds */
  updateInterval?: number;
  /** Whether to automatically update time scale after data update */
  autoUpdateTimeScale?: boolean;
  /** Whether to disable updates while user is interacting with chart */
  pauseDuringInteraction?: boolean;
}

/**
 * Options for update operations
 */
export interface UpdateOptions {
  /** Update mode to use for this update */
  mode?: UpdateMode;
  /** Whether to update the time scale after update */
  updateTimeScale?: boolean;
  /** Whether to animate the update */
  animate?: boolean;
}

/**
 * Handles efficient updates for chart series
 */
export class ChartUpdater {
  private series: Map<string, ISeriesApi<SeriesType>> = new Map();
  private seriesData: Map<string, any[]> = new Map();
  private seriesTypes: Map<string, SeriesType> = new Map();
  private chart: IChartApi | null = null;
  private options: ChartUpdaterOptions;
  private lastOHLCVData: Map<string, OHLCVData> = new Map();
  private userInteracting: boolean = false;
  private updateTimer: NodeJS.Timeout | null = null;
  
  /**
   * Creates a new ChartUpdater instance
   * @param chart Chart instance to update
   * @param options Configuration options
   */
  constructor(chart: IChartApi | null = null, options: ChartUpdaterOptions = {}) {
    this.chart = chart;
    this.options = {
      maxPoints: options.maxPoints || 10000,
      defaultUpdateMode: options.defaultUpdateMode || UpdateMode.UPDATE_LAST_AND_APPEND,
      updateInterval: options.updateInterval || 0,
      autoUpdateTimeScale: options.autoUpdateTimeScale !== false,
      pauseDuringInteraction: options.pauseDuringInteraction !== false,
    };
    
    // Set up interaction tracking if needed
    if (this.options.pauseDuringInteraction && chart) {
      chart.subscribeCrosshairMove(this.handleUserInteraction);
    }
  }
  
  /**
   * Sets the chart instance
   * @param chart Chart instance to update
   */
  public setChart(chart: IChartApi): void {
    this.chart = chart;
    
    // Set up interaction tracking if needed
    if (this.options.pauseDuringInteraction) {
      chart.subscribeCrosshairMove(this.handleUserInteraction);
    }
    
    // Update any existing series with new chart
    this.refreshAllSeries();
  }
  
  /**
   * Adds a series to manage
   * @param id Unique identifier for the series
   * @param series Series instance
   * @param type Series type
   */
  public addSeries(id: string, series: ISeriesApi<SeriesType>, type: SeriesType): void {
    this.series.set(id, series);
    this.seriesTypes.set(id, type);
    this.seriesData.set(id, []);
  }
  
  /**
   * Removes a series from management
   * @param id Series identifier
   */
  public removeSeries(id: string): void {
    this.series.delete(id);
    this.seriesTypes.delete(id);
    this.seriesData.delete(id);
    this.lastOHLCVData.delete(id);
  }
  
  /**
   * Updates a series with new OHLCV data
   * @param id Series identifier
   * @param data New OHLCV data
   * @param options Update options
   */
  public updateSeries(
    id: string, 
    data: OHLCVData, 
    options: UpdateOptions = {}
  ): void {
    const series = this.series.get(id);
    const type = this.seriesTypes.get(id);
    
    if (!series || !type) {
      console.warn(`Series not found: ${id}`);
      return;
    }
    
    // Determine update mode
    const mode = options.mode || this.options.defaultUpdateMode;
    const lastData = this.lastOHLCVData.get(id);
    
    let formattedData: any[] = [];
    
    // Process data based on update mode
    if (mode === UpdateMode.REPLACE || !lastData) {
      // Full replacement or first update
      this.lastOHLCVData.set(id, data);
    } else {
      // Apply update based on mode
      switch (mode) {
        case UpdateMode.APPEND:
        case UpdateMode.UPDATE_LAST_AND_APPEND:
          const updatedData = createUpdateData(
            lastData,
            data,
            this.options.maxPoints
          );
          this.lastOHLCVData.set(id, updatedData);
          break;
          
        case UpdateMode.VISIBLE_RANGE_ONLY:
          if (this.chart) {
            // Get visible range
            const visibleRange = this.chart.timeScale().getVisibleRange();
            if (visibleRange) {
              // Filter data to visible range
              const filteredData = this.filterDataToTimeRange(data, visibleRange.from, visibleRange.to);
              this.lastOHLCVData.set(id, filteredData);
            } else {
              // Fallback to full replacement if no visible range
              this.lastOHLCVData.set(id, data);
            }
          } else {
            // Fallback to full replacement if no chart
            this.lastOHLCVData.set(id, data);
          }
          break;
      }
    }
    
    // Format data based on series type
    const dataToUse = this.lastOHLCVData.get(id) || data;
    
    switch (type) {
      case 'Candlestick':
        formattedData = formatCandlestickData(dataToUse);
        break;
        
      case 'Line':
        formattedData = formatLineData(dataToUse);
        break;
        
      case 'Histogram':
        formattedData = formatHistogramData(dataToUse);
        break;
        
      case 'Bar':
        formattedData = formatBarData(dataToUse);
        break;
    }
    
    // Store formatted data
    this.seriesData.set(id, formattedData);
    
    // Update the series
    this.updateSeriesWithData(id, formattedData, options);
  }
  
  /**
   * Updates all series with new data
   * @param data Map of series IDs to their new data
   * @param options Update options
   */
  public updateAllSeries(
    data: Map<string, OHLCVData> | Record<string, OHLCVData>, 
    options: UpdateOptions = {}
  ): void {
    // Convert record to map if needed
    const dataMap = data instanceof Map ? data : new Map(Object.entries(data));
    
    // Update each series
    for (const [id, seriesData] of dataMap) {
      this.updateSeries(id, seriesData, options);
    }
    
    // Update time scale if requested
    if ((options.updateTimeScale ?? this.options.autoUpdateTimeScale) && this.chart) {
      this.chart.timeScale().fitContent();
    }
  }
  
  /**
   * Sets up periodic updates from a data source
   * @param getDataFn Function that returns the data for each series
   * @param interval Update interval in milliseconds
   * @param options Update options
   */
  public startPeriodicUpdates(
    getDataFn: () => Promise<Map<string, OHLCVData> | Record<string, OHLCVData>>,
    interval: number = this.options.updateInterval || 1000,
    options: UpdateOptions = {}
  ): void {
    // Clear any existing timer
    this.stopPeriodicUpdates();
    
    // Start new update cycle
    const updateFn = async () => {
      // Skip update if user is interacting with chart
      if (this.options.pauseDuringInteraction && this.userInteracting) {
        this.scheduleNextUpdate(updateFn, interval);
        return;
      }
      
      try {
        const data = await getDataFn();
        this.updateAllSeries(data, options);
      } catch (error) {
        console.error('Error updating chart data:', error);
      }
      
      this.scheduleNextUpdate(updateFn, interval);
    };
    
    // Kick off first update
    updateFn();
  }
  
  /**
   * Stops periodic updates
   */
  public stopPeriodicUpdates(): void {
    if (this.updateTimer) {
      clearTimeout(this.updateTimer);
      this.updateTimer = null;
    }
  }
  
  /**
   * Cleans up resources
   */
  public dispose(): void {
    this.stopPeriodicUpdates();
    
    if (this.chart && this.options.pauseDuringInteraction) {
      this.chart.unsubscribeCrosshairMove(this.handleUserInteraction);
    }
    
    this.series.clear();
    this.seriesTypes.clear();
    this.seriesData.clear();
    this.lastOHLCVData.clear();
    this.chart = null;
  }
  
  /**
   * Filters data to a specific time range
   * @param data Original data
   * @param fromTime Start time
   * @param toTime End time
   * @returns Filtered data
   */
  private filterDataToTimeRange(
    data: OHLCVData, 
    fromTime: number,
    toTime: number
  ): OHLCVData {
    if (!data || !data.dates || !data.ohlcv) {
      return data;
    }
    
    const filteredDates: string[] = [];
    const filteredOHLCV: number[][] = [];
    
    for (let i = 0; i < data.dates.length; i++) {
      const date = data.dates[i];
      let timestamp: number;
      
      if (typeof date === 'number') {
        timestamp = date;
      } else {
        timestamp = new Date(date).getTime() / 1000;
      }
      
      if (timestamp >= fromTime && timestamp <= toTime) {
        filteredDates.push(data.dates[i]);
        filteredOHLCV.push(data.ohlcv[i]);
      }
    }
    
    return {
      dates: filteredDates,
      ohlcv: filteredOHLCV,
      metadata: {
        ...data.metadata,
        points: filteredDates.length
      }
    };
  }
  
  /**
   * Updates a series with formatted data
   * @param id Series identifier
   * @param formattedData Formatted data for the series
   * @param options Update options
   */
  private updateSeriesWithData(
    id: string, 
    formattedData: any[], 
    options: UpdateOptions
  ): void {
    const series = this.series.get(id);
    
    if (!series) {
      return;
    }
    
    // Apply the update
    series.setData(formattedData);
    
    // Update time scale if requested
    if ((options.updateTimeScale ?? this.options.autoUpdateTimeScale) && this.chart) {
      this.chart.timeScale().fitContent();
    }
  }
  
  /**
   * Refreshes all series with their current data
   */
  private refreshAllSeries(): void {
    for (const id of this.series.keys()) {
      const data = this.seriesData.get(id);
      if (data) {
        this.updateSeriesWithData(id, data, {});
      }
    }
  }
  
  /**
   * Schedules the next update
   * @param updateFn Update function to call
   * @param interval Interval in milliseconds
   */
  private scheduleNextUpdate(updateFn: () => void, interval: number): void {
    this.updateTimer = setTimeout(updateFn, interval);
  }
  
  /**
   * Handles user interaction with the chart
   */
  private handleUserInteraction = () => {
    this.userInteracting = true;
    
    // Reset after a short delay
    setTimeout(() => {
      this.userInteracting = false;
    }, 1000);
  };
}