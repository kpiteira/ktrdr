/**
 * Chart Debug Utilities
 * 
 * Provides tools for debugging and inspecting chart data and performance.
 */
import { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import { OHLCVData } from '../../types/data';
import { validateOHLCVData, ValidationResult } from './dataValidation';
import { convertToChartTime, formatTimeForDisplay } from './chartDataUtils';

/**
 * Debug log levels
 */
export enum LogLevel {
  INFO = 'info',
  DEBUG = 'debug',
  WARN = 'warn',
  ERROR = 'error'
}

/**
 * Chart debug logger class
 */
export class ChartDebugger {
  /** Whether debugging is enabled */
  private enabled: boolean;
  /** Default log level */
  private logLevel: LogLevel;
  /** Custom prefix for log messages */
  private prefix: string;
  /** Performance measurements */
  private measurements: Map<string, { start: number; duration?: number }>;
  /** Last data summary by chart/series ID */
  private lastDataSummaries: Map<string, any>;
  
  /**
   * Creates a new ChartDebugger
   * @param enabled Whether debugging is enabled by default
   * @param logLevel Default log level
   * @param prefix Custom prefix for log messages
   */
  constructor(enabled = false, logLevel = LogLevel.DEBUG, prefix = 'ChartDebug') {
    this.enabled = enabled;
    this.logLevel = logLevel;
    this.prefix = prefix;
    this.measurements = new Map();
    this.lastDataSummaries = new Map();
    
    // Check if debug mode is enabled in URL or localStorage
    this.checkDebugModeFromEnvironment();
  }
  
  /**
   * Checks if debug mode should be enabled based on URL or localStorage
   */
  private checkDebugModeFromEnvironment(): void {
    if (typeof window !== 'undefined') {
      // Check URL parameters
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has('chartDebug')) {
        this.enabled = true;
        const level = urlParams.get('chartDebug');
        if (level && Object.values(LogLevel).includes(level as LogLevel)) {
          this.logLevel = level as LogLevel;
        }
      }
      
      // Check localStorage
      try {
        const storedDebug = localStorage.getItem('ktrdr_chart_debug');
        if (storedDebug) {
          const debugSettings = JSON.parse(storedDebug);
          this.enabled = debugSettings.enabled ?? this.enabled;
          if (debugSettings.logLevel && Object.values(LogLevel).includes(debugSettings.logLevel)) {
            this.logLevel = debugSettings.logLevel;
          }
        }
      } catch (e) {
        // Ignore localStorage errors
      }
    }
  }
  
  /**
   * Enables or disables debug logging
   * @param enabled Whether debugging should be enabled
   * @param saveToStorage Whether to save this setting to localStorage
   */
  public setEnabled(enabled: boolean, saveToStorage = true): void {
    this.enabled = enabled;
    
    if (saveToStorage && typeof window !== 'undefined') {
      try {
        let debugSettings: any = {};
        const storedDebug = localStorage.getItem('ktrdr_chart_debug');
        
        if (storedDebug) {
          debugSettings = JSON.parse(storedDebug);
        }
        
        debugSettings.enabled = enabled;
        
        localStorage.setItem('ktrdr_chart_debug', JSON.stringify(debugSettings));
      } catch (e) {
        // Ignore localStorage errors
      }
    }
  }
  
  /**
   * Sets the debug log level
   * @param level Log level to use
   * @param saveToStorage Whether to save this setting to localStorage
   */
  public setLogLevel(level: LogLevel, saveToStorage = true): void {
    this.logLevel = level;
    
    if (saveToStorage && typeof window !== 'undefined') {
      try {
        let debugSettings: any = {};
        const storedDebug = localStorage.getItem('ktrdr_chart_debug');
        
        if (storedDebug) {
          debugSettings = JSON.parse(storedDebug);
        }
        
        debugSettings.logLevel = level;
        
        localStorage.setItem('ktrdr_chart_debug', JSON.stringify(debugSettings));
      } catch (e) {
        // Ignore localStorage errors
      }
    }
  }
  
  /**
   * Logs a debug message
   * @param message Message to log
   * @param data Optional data to include
   * @param level Log level
   */
  public log(message: string, data?: any, level: LogLevel = this.logLevel): void {
    if (!this.enabled) return;
    
    const formattedMessage = `[${this.prefix}] ${message}`;
    
    switch (level) {
      case LogLevel.INFO:
        console.info(formattedMessage, data);
        break;
      case LogLevel.DEBUG:
        console.debug(formattedMessage, data);
        break;
      case LogLevel.WARN:
        console.warn(formattedMessage, data);
        break;
      case LogLevel.ERROR:
        console.error(formattedMessage, data);
        break;
    }
  }
  
  /**
   * Starts a performance measurement
   * @param label Measurement label
   */
  public startMeasure(label: string): void {
    if (!this.enabled) return;
    
    this.measurements.set(label, { start: performance.now() });
    this.log(`Starting measurement: ${label}`, null, LogLevel.DEBUG);
  }
  
  /**
   * Ends a performance measurement and logs the duration
   * @param label Measurement label
   * @param logLevel Log level for the result
   * @returns Measured duration in milliseconds
   */
  public endMeasure(label: string, logLevel: LogLevel = LogLevel.DEBUG): number | undefined {
    if (!this.enabled) return;
    
    const measurement = this.measurements.get(label);
    
    if (!measurement) {
      this.log(`No measurement found with label: ${label}`, null, LogLevel.WARN);
      return;
    }
    
    const end = performance.now();
    const duration = end - measurement.start;
    
    // Update measurement
    measurement.duration = duration;
    
    this.log(`Measurement '${label}': ${duration.toFixed(2)}ms`, { duration }, logLevel);
    
    return duration;
  }
  
  /**
   * Logs detailed information about chart data
   * @param data OHLCV data to inspect
   * @param chartId Optional chart identifier for tracking
   * @returns Validation result and statistics
   */
  public inspectData(data: OHLCVData, chartId = 'default'): { 
    validation: ValidationResult;
    stats: any;
  } {
    if (!this.enabled || !data) return { validation: { valid: false, issues: [], summary: {}, errorPercentage: 0, preventRendering: false }, stats: {} };
    
    // Start performance measurement
    this.startMeasure(`inspectData-${chartId}`);
    
    // Validate the data
    const validation = validateOHLCVData(data);
    
    // Calculate basic statistics
    const stats: any = {
      points: data.dates?.length || 0,
      timeRange: {
        start: data.dates?.[0],
        end: data.dates?.[data.dates.length - 1]
      },
      priceRange: {
        min: Number.MAX_VALUE,
        max: Number.MIN_VALUE
      },
      volume: {
        min: Number.MAX_VALUE,
        max: Number.MIN_VALUE,
        total: 0,
        average: 0
      },
      changes: {
        totalBars: 0,
        upBars: 0,
        downBars: 0,
        dojiBars: 0,
        percentageChange: 0
      }
    };
    
    // Calculate detailed statistics
    if (data.ohlcv && data.ohlcv.length > 0) {
      let totalPriceChange = 0;
      let upBars = 0;
      let downBars = 0;
      let dojiBars = 0;
      
      for (const ohlcv of data.ohlcv) {
        const [open, high, low, close, volume] = ohlcv;
        
        // Update price range
        stats.priceRange.min = Math.min(stats.priceRange.min, low);
        stats.priceRange.max = Math.max(stats.priceRange.max, high);
        
        // Update volume stats
        if (volume !== undefined && !isNaN(volume)) {
          stats.volume.min = Math.min(stats.volume.min, volume);
          stats.volume.max = Math.max(stats.volume.max, volume);
          stats.volume.total += volume;
        }
        
        // Calculate price change
        if (!isNaN(open) && !isNaN(close)) {
          const priceChange = close - open;
          
          // Count up/down/doji bars
          if (priceChange > 0) {
            upBars++;
          } else if (priceChange < 0) {
            downBars++;
          } else {
            dojiBars++;
          }
          
          totalPriceChange += priceChange;
        }
      }
      
      // Update statistics
      stats.volume.average = stats.volume.total / data.ohlcv.length;
      stats.changes.totalBars = data.ohlcv.length;
      stats.changes.upBars = upBars;
      stats.changes.downBars = downBars;
      stats.changes.dojiBars = dojiBars;
      
      // Calculate overall price change percentage
      const firstPrice = data.ohlcv[0][0]; // First open price
      const lastPrice = data.ohlcv[data.ohlcv.length - 1][3]; // Last close price
      
      if (firstPrice !== 0) {
        stats.changes.percentageChange = ((lastPrice - firstPrice) / firstPrice) * 100;
      }
    }
    
    // Add sample data points
    const sampleSize = Math.min(3, data.ohlcv?.length || 0);
    const samples = {
      start: data.ohlcv?.slice(0, sampleSize) || [],
      end: data.ohlcv?.slice(-sampleSize) || []
    };
    
    stats.samples = samples;
    
    // Store for reference and comparison
    const previousSummary = this.lastDataSummaries.get(chartId);
    this.lastDataSummaries.set(chartId, { validation, stats });
    
    // Generate change report if there was a previous summary
    let changeReport = null;
    if (previousSummary) {
      changeReport = this.compareDataSummaries(previousSummary, { validation, stats });
    }
    
    // End performance measurement
    this.endMeasure(`inspectData-${chartId}`);
    
    // Log the summary
    this.log(`Data inspection for chart ${chartId}`, {
      validation, 
      stats,
      changeReport
    });
    
    return { validation, stats };
  }
  
  /**
   * Compares two data summaries to identify changes
   * @param previous Previous data summary
   * @param current Current data summary
   * @returns Changes between the two summaries
   */
  private compareDataSummaries(previous: any, current: any): any {
    const changes = {
      pointsChanged: current.stats.points !== previous.stats.points,
      pointsDelta: current.stats.points - previous.stats.points,
      priceRangeChanged: 
        current.stats.priceRange.min !== previous.stats.priceRange.min ||
        current.stats.priceRange.max !== previous.stats.priceRange.max,
      validationChanged: 
        current.validation.valid !== previous.validation.valid ||
        current.validation.issues.length !== previous.validation.issues.length,
      newIssues: [] as string[],
      resolvedIssues: [] as string[]
    };
    
    // Find new and resolved validation issues
    if (changes.validationChanged) {
      const previousIssueMessages = previous.validation.issues.map((i: any) => i.message);
      const currentIssueMessages = current.validation.issues.map((i: any) => i.message);
      
      // Find new issues
      changes.newIssues = currentIssueMessages.filter(
        (message: string) => !previousIssueMessages.includes(message)
      );
      
      // Find resolved issues
      changes.resolvedIssues = previousIssueMessages.filter(
        (message: string) => !currentIssueMessages.includes(message)
      );
    }
    
    return changes;
  }
  
  /**
   * Logs information about chart series
   * @param chart Chart instance
   * @param seriesId Optional series identifier
   */
  public inspectSeries(chart: IChartApi, seriesId?: string): void {
    if (!this.enabled || !chart) return;
    
    // Check if specific series provided
    if (seriesId) {
      // We can't directly access series from chart, so we'll log what we know
      this.log(`Series inspection for ${seriesId}`, {
        info: 'Limited series info available from chart API',
        chart: {
          timeScale: chart.timeScale().getVisibleRange(),
          options: chart.options()
        }
      });
      return;
    }
    
    // Log general chart information
    this.log('Chart inspection', {
      timeScale: chart.timeScale().getVisibleRange(),
      options: chart.options()
    });
  }
  
  /**
   * Creates a visual overlay with debug information on the chart
   * @param chart Chart instance
   * @param container Container element
   * @param data Chart data
   */
  public createDebugOverlay(chart: IChartApi, container: HTMLElement, data?: OHLCVData): void {
    if (!this.enabled || !chart || !container) return;
    
    // Remove any existing overlay
    const existingOverlay = container.querySelector('.chart-debug-overlay');
    if (existingOverlay) {
      container.removeChild(existingOverlay);
    }
    
    // Create overlay element
    const overlay = document.createElement('div');
    overlay.className = 'chart-debug-overlay';
    overlay.style.cssText = `
      position: absolute;
      top: 10px;
      right: 10px;
      background: rgba(0, 0, 0, 0.7);
      color: white;
      padding: 10px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      z-index: 100;
      max-width: 300px;
      max-height: 200px;
      overflow: auto;
    `;
    
    // Create content
    let content = `<div><strong>Chart Debug</strong> <span class="time">${new Date().toISOString()}</span></div>`;
    
    // Add data points count if data available
    if (data) {
      content += `<div>Data points: ${data.dates?.length || 0}</div>`;
      
      // Add validation info
      const validation = validateOHLCVData(data);
      content += `<div>Validation: ${validation.valid ? '✅ Valid' : '❌ Invalid'}</div>`;
      if (validation.issues.length > 0) {
        content += `<div>Issues: ${validation.issues.length}</div>`;
      }
    }
    
    // Add visible range
    const visibleRange = chart.timeScale().getVisibleRange();
    if (visibleRange) {
      content += `<div>Visible: ${formatTimeValue(visibleRange.from)} to ${formatTimeValue(visibleRange.to)}</div>`;
    }
    
    // Add update button
    content += `<button class="update-debug" style="margin-top: 5px; padding: 2px 5px;">Update</button>`;
    
    // Set content and add to container
    overlay.innerHTML = content;
    container.appendChild(overlay);
    
    // Add event listener to update button
    const updateButton = overlay.querySelector('.update-debug');
    if (updateButton) {
      updateButton.addEventListener('click', () => {
        this.createDebugOverlay(chart, container, data);
      });
    }
  }
  
  /**
   * Creates a text representation of chart for sharing debug info
   * @param chart Chart instance
   * @param data Chart data
   * @returns Text representation
   */
  public createDebugText(chart: IChartApi, data?: OHLCVData): string {
    if (!chart) return 'No chart instance provided';
    
    let debugText = '=== CHART DEBUG INFO ===\n';
    
    // Add timestamp
    debugText += `Time: ${new Date().toISOString()}\n\n`;
    
    // Add visible range
    const visibleRange = chart.timeScale().getVisibleRange();
    if (visibleRange) {
      debugText += `Visible Range: ${formatTimeValue(visibleRange.from)} to ${formatTimeValue(visibleRange.to)}\n`;
    }
    
    // Add data overview if available
    if (data) {
      debugText += `\n=== DATA INFO ===\n`;
      debugText += `Symbol: ${data.metadata?.symbol || 'Unknown'}\n`;
      debugText += `Timeframe: ${data.metadata?.timeframe || 'Unknown'}\n`;
      debugText += `Points: ${data.dates?.length || 0}\n`;
      
      if (data.dates && data.dates.length > 0) {
        debugText += `Date Range: ${data.dates[0]} to ${data.dates[data.dates.length - 1]}\n`;
      }
      
      // Add validation overview
      const validation = validateOHLCVData(data);
      debugText += `\n=== VALIDATION ===\n`;
      debugText += `Valid: ${validation.valid ? 'Yes' : 'No'}\n`;
      debugText += `Issues: ${validation.issues.length}\n`;
      
      if (validation.issues.length > 0) {
        debugText += `\nIssue Summary:\n`;
        for (const [type, count] of Object.entries(validation.summary)) {
          debugText += `- ${type}: ${count}\n`;
        }
        
        debugText += `\nFirst 5 Issues:\n`;
        for (let i = 0; i < Math.min(5, validation.issues.length); i++) {
          const issue = validation.issues[i];
          debugText += `- [${issue.severity}] ${issue.message}\n`;
        }
      }
      
      // Add price statistics
      if (data.ohlcv && data.ohlcv.length > 0) {
        let priceMin = Number.MAX_VALUE;
        let priceMax = Number.MIN_VALUE;
        
        for (const [_open, high, low, _close, _volume] of data.ohlcv) {
          priceMin = Math.min(priceMin, low);
          priceMax = Math.max(priceMax, high);
        }
        
        debugText += `\n=== PRICE INFO ===\n`;
        debugText += `Range: ${priceMin} to ${priceMax}\n`;
        debugText += `Span: ${(priceMax - priceMin).toFixed(4)}\n`;
      }
    }
    
    return debugText;
  }
}

/**
 * Helper to format time values
 * @param time Time value to format
 * @returns Formatted time string
 */
function formatTimeValue(time: Time): string {
  if (typeof time === 'number') {
    // Unix timestamp in seconds
    return new Date(time * 1000).toLocaleString();
  } else if (typeof time === 'object' && 'year' in time) {
    // BusinessDay format
    return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
  } else {
    return String(time);
  }
}

// Create singleton instance
export const chartDebugger = new ChartDebugger();

// Add window function for external access
if (typeof window !== 'undefined') {
  (window as any).enableChartDebug = (enable = true) => {
    chartDebugger.setEnabled(enable);
    console.log(`Chart debugging ${enable ? 'enabled' : 'disabled'}`);
    return `Chart debugging ${enable ? 'enabled' : 'disabled'}`;
  };
}