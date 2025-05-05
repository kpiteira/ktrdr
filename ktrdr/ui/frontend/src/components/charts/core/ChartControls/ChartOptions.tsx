import React, { useState } from 'react';
import './ChartOptions.css';

export interface ChartOptionsProps {
  /** Chart instance to customize */
  chart: any; // This would ideally be typed as IChartApi from lightweight-charts
  /** Whether the options panel is visible */
  isVisible?: boolean;
  /** Callback when visibility changes */
  onVisibilityChange?: (isVisible: boolean) => void;
  /** Default chart options */
  defaultOptions?: ChartCustomizableOptions;
  /** Callback when options change */
  onOptionsChange?: (options: ChartCustomizableOptions) => void;
  /** CSS class name for additional styling */
  className?: string;
}

export interface ChartCustomizableOptions {
  /** Show grid lines */
  showGrid?: boolean;
  /** Show volume */
  showVolume?: boolean;
  /** Chart background color */
  backgroundColor?: string;
  /** Text color */
  textColor?: string;
  /** Grid line color */
  gridColor?: string;
  /** Candle up color */
  upColor?: string;
  /** Candle down color */
  downColor?: string;
  /** Candle wick up color */
  wickUpColor?: string;
  /** Candle wick down color */
  wickDownColor?: string;
  /** Volume up color */
  volumeUpColor?: string;
  /** Volume down color */
  volumeDownColor?: string;
  /** Crosshair color */
  crosshairColor?: string;
}

/**
 * ChartOptions component
 * 
 * Provides a panel for customizing chart appearance
 */
const ChartOptions: React.FC<ChartOptionsProps> = ({
  chart,
  isVisible = false,
  onVisibilityChange,
  defaultOptions = {
    showGrid: true,
    showVolume: true,
    backgroundColor: '',
    textColor: '',
    gridColor: '',
    upColor: '#26a69a',
    downColor: '#ef5350',
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
    volumeUpColor: 'rgba(38, 166, 154, 0.5)',
    volumeDownColor: 'rgba(239, 83, 80, 0.5)',
    crosshairColor: '#9db2bd'
  },
  onOptionsChange,
  className = ''
}) => {
  const [options, setOptions] = useState<ChartCustomizableOptions>(defaultOptions);
  const [isPanelOpen, setIsPanelOpen] = useState<boolean>(isVisible);

  // Toggle panel visibility
  const togglePanel = () => {
    const newVisibility = !isPanelOpen;
    setIsPanelOpen(newVisibility);
    
    if (onVisibilityChange) {
      onVisibilityChange(newVisibility);
    }
  };

  // Handle option changes
  const handleOptionChange = (key: keyof ChartCustomizableOptions, value: any) => {
    const newOptions = { ...options, [key]: value };
    setOptions(newOptions);
    
    // Apply changes to the chart if it exists
    if (chart) {
      try {
        applyOptionsToChart(newOptions);
      } catch (error) {
        console.error('Error applying options to chart:', error);
      }
    }
    
    if (onOptionsChange) {
      onOptionsChange(newOptions);
    }
  };

  // Apply options to the chart
  const applyOptionsToChart = (opts: ChartCustomizableOptions) => {
    if (!chart) return;
    
    // Apply grid visibility
    if (opts.showGrid !== undefined) {
      chart.applyOptions({
        grid: {
          vertLines: { visible: opts.showGrid },
          horzLines: { visible: opts.showGrid }
        }
      });
    }
    
    // Apply colors
    const colorOptions: any = {};
    
    if (opts.backgroundColor) {
      colorOptions.layout = {
        ...colorOptions.layout,
        background: { type: 'solid', color: opts.backgroundColor }
      };
    }
    
    if (opts.textColor) {
      colorOptions.layout = {
        ...colorOptions.layout,
        textColor: opts.textColor
      };
    }
    
    if (opts.gridColor) {
      colorOptions.grid = {
        vertLines: { color: opts.gridColor },
        horzLines: { color: opts.gridColor }
      };
    }
    
    if (opts.crosshairColor) {
      colorOptions.crosshair = {
        ...colorOptions.crosshair,
        color: opts.crosshairColor
      };
    }
    
    // Apply any color options to chart
    if (Object.keys(colorOptions).length > 0) {
      chart.applyOptions(colorOptions);
    }
    
    // Apply series-specific options
    const series = chart.serieses();
    if (series && series.length > 0) {
      // Find candlestick series
      const candlestickSeries = series.find((s: any) => s.seriesType() === 'Candlestick');
      if (candlestickSeries && (opts.upColor || opts.downColor || opts.wickUpColor || opts.wickDownColor)) {
        const candleOptions: any = {};
        
        if (opts.upColor) candleOptions.upColor = opts.upColor;
        if (opts.downColor) candleOptions.downColor = opts.downColor;
        if (opts.wickUpColor) candleOptions.wickUpColor = opts.wickUpColor;
        if (opts.wickDownColor) candleOptions.wickDownColor = opts.wickDownColor;
        
        candlestickSeries.applyOptions(candleOptions);
      }
      
      // Find volume series if exists
      const volumeSeries = series.find((s: any) => s.seriesType() === 'Histogram');
      if (volumeSeries && (opts.volumeUpColor || opts.volumeDownColor)) {
        // For volume series, we'd need a more complex approach as there isn't a direct API
        // for setting colors based on up/down. This would likely require updating the data
        // with color information.
      }
    }
  };

  if (!isPanelOpen) {
    return (
      <button 
        className={`chart-options-toggle ${className}`}
        onClick={togglePanel}
        title="Show chart options"
      >
        Show Options
      </button>
    );
  }

  return (
    <div className={`chart-options-panel ${className}`}>
      <div className="options-header">
        <h3>Chart Options</h3>
        <button 
          className="close-button"
          onClick={togglePanel}
          title="Close options panel"
        >
          ×
        </button>
      </div>
      
      <div className="options-section">
        <h4>Display Options</h4>
        
        <div className="option-row">
          <label>
            <input
              type="checkbox"
              checked={options.showGrid}
              onChange={(e) => handleOptionChange('showGrid', e.target.checked)}
            />
            Show Grid
          </label>
        </div>
        
        <div className="option-row">
          <label>
            <input
              type="checkbox"
              checked={options.showVolume}
              onChange={(e) => handleOptionChange('showVolume', e.target.checked)}
            />
            Show Volume
          </label>
        </div>
      </div>
      
      <div className="options-section">
        <h4>Colors</h4>
        
        <div className="color-options">
          <div className="color-option">
            <label>Up Color</label>
            <input
              type="color"
              value={options.upColor || '#26a69a'}
              onChange={(e) => handleOptionChange('upColor', e.target.value)}
              title="Color for rising candles"
            />
          </div>
          
          <div className="color-option">
            <label>Down Color</label>
            <input
              type="color"
              value={options.downColor || '#ef5350'}
              onChange={(e) => handleOptionChange('downColor', e.target.value)}
              title="Color for falling candles"
            />
          </div>
        </div>
      </div>
      
      <div className="options-actions">
        <button
          className="reset-button"
          onClick={() => {
            setOptions(defaultOptions);
            if (chart) {
              try {
                applyOptionsToChart(defaultOptions);
              } catch (error) {
                console.error('Error resetting chart options:', error);
              }
            }
            if (onOptionsChange) {
              onOptionsChange(defaultOptions);
            }
          }}
        >
          Reset to Default
        </button>
      </div>
    </div>
  );
};

export default ChartOptions;