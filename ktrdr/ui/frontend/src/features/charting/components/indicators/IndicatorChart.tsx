// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/indicators/IndicatorChart.tsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  OHLCVData, 
  IndicatorData, 
  IndicatorConfig, 
  IndicatorMetadata,
  IndicatorDisplay,
  IndicatorType
} from '../../../types/data';
import { useTheme } from '../../layouts/ThemeProvider';
import CandlestickChart from '../core/CandlestickChart';
import { CrosshairData } from '../core/CrosshairInfo';
import IndicatorSeries from './IndicatorSeries';
import IndicatorPanel from './IndicatorPanel';
import IndicatorControls from './IndicatorControls';
import IndicatorTooltip from './IndicatorTooltip';
import './IndicatorChart.css';

interface IndicatorChartProps {
  /** OHLCV data for the chart */
  data: OHLCVData;
  /** Indicator data array */
  indicators?: IndicatorData[];
  /** Indicator configurations */
  indicatorConfigs?: IndicatorConfig[];
  /** Indicator metadata */
  indicatorMetadata?: IndicatorMetadata[];
  /** Height of the chart in pixels */
  height?: number;
  /** Width of the chart in pixels, defaults to container width */
  width?: number;
  /** Chart title */
  title?: string;
  /** Whether to show volume */
  showVolume?: boolean;
  /** Whether to fit content on load and data change */
  fitContent?: boolean;
  /** Whether to resize the chart when container size changes */
  autoResize?: boolean;
  /** Whether to show indicator controls */
  showControls?: boolean;
  /** Whether to show indicator tooltips */
  showTooltips?: boolean;
  /** CSS class name for additional styling */
  className?: string;
  /** Callback when indicator config changes */
  onIndicatorConfigChange?: (configs: IndicatorConfig[]) => void;
}

/**
 * IndicatorChart component
 * 
 * Enhanced chart component that combines CandlestickChart with indicator visualization
 * capabilities, including overlay indicators, separate panels, and interactive controls.
 */
const IndicatorChart: React.FC<IndicatorChartProps> = ({
  data,
  indicators = [],
  indicatorConfigs = [],
  indicatorMetadata = [],
  height = 400,
  width,
  title,
  showVolume = true,
  fitContent = true,
  autoResize = true,
  showControls = true,
  showTooltips = true,
  className = '',
  onIndicatorConfigChange
}) => {
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // Refs
  const mainChartRef = useRef<any>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  
  // State
  const [crosshairData, setCrosshairData] = useState<CrosshairData | null>(null);
  const [configs, setConfigs] = useState<IndicatorConfig[]>(indicatorConfigs);
  const [panelHeight, setPanelHeight] = useState<number>(150);
  
  // Update configs when props change
  useEffect(() => {
    setConfigs(indicatorConfigs);
  }, [indicatorConfigs]);
  
  // Calculate main chart height based on number of panels
  const calculateChartHeight = useCallback(() => {
    const panelIndicators = configs.filter(config => {
      const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
      return config.visible && metadata?.display === IndicatorDisplay.SEPARATE;
    });
    
    const panelsHeight = panelIndicators.length * (panelHeight + 10); // panel height + margin
    return Math.max(200, height - panelsHeight); // Ensure minimum height
  }, [configs, indicatorMetadata, height, panelHeight]);
  
  // Calculate main chart height
  const mainChartHeight = calculateChartHeight();
  
  // Get the chart instance from the CandlestickChart
  const handleChartInit = (chart: any) => {
    mainChartRef.current = chart;
  };
  
  // Handle crosshair movement
  const handleCrosshairMove = (data: CrosshairData | null) => {
    setCrosshairData(data);
  };
  
  // Handle indicator config change
  const handleConfigChange = (updatedConfig: IndicatorConfig) => {
    const newConfigs = configs.map(config => 
      config.id === updatedConfig.id ? updatedConfig : config
    );
    setConfigs(newConfigs);
    
    if (onIndicatorConfigChange) {
      onIndicatorConfigChange(newConfigs);
    }
  };
  
  // Handle indicator removal
  const handleIndicatorRemove = (configId: string) => {
    const newConfigs = configs.filter(config => config.id !== configId);
    setConfigs(newConfigs);
    
    if (onIndicatorConfigChange) {
      onIndicatorConfigChange(newConfigs);
    }
  };
  
  // Filter visible overlay indicators
  const overlayIndicators = configs
    .filter(config => {
      const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
      return config.visible && metadata?.display === IndicatorDisplay.OVERLAY;
    })
    .map(config => {
      const indicatorData = indicators.find(ind => ind.indicatorId === config.id);
      const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
      return { config, data: indicatorData, metadata, type: metadata?.type };
    })
    .filter(item => item.data && item.metadata) as Array<{
      config: IndicatorConfig;
      data: IndicatorData;
      metadata: IndicatorMetadata;
      type: IndicatorType;
    }>;
  
  // Filter visible separate panel indicators
  const panelIndicators = configs
    .filter(config => {
      const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
      return config.visible && metadata?.display === IndicatorDisplay.SEPARATE;
    })
    .map(config => {
      const indicatorData = indicators.find(ind => ind.indicatorId === config.id);
      const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
      return { config, data: indicatorData, metadata, type: metadata?.type };
    })
    .filter(item => item.data && item.metadata) as Array<{
      config: IndicatorConfig;
      data: IndicatorData;
      metadata: IndicatorMetadata;
      type: IndicatorType;
    }>;
  
  return (
    <div 
      ref={chartContainerRef}
      className={`indicator-chart-container ${isDarkTheme ? 'dark-theme' : 'light-theme'} ${className}`}
    >
      {/* Controls Panel */}
      {showControls && configs.length > 0 && (
        <div className="indicator-controls-container">
          {configs.map(config => {
            const metadata = indicatorMetadata.find(m => m.id === config.indicatorId);
            if (!metadata) return null;
            
            return (
              <IndicatorControls
                key={config.id}
                config={config}
                metadata={metadata}
                onConfigChange={handleConfigChange}
                onRemove={() => handleIndicatorRemove(config.id)}
              />
            );
          })}
        </div>
      )}
      
      {/* Main Chart */}
      <div className="main-chart-container">
        <CandlestickChart
          data={data}
          height={mainChartHeight}
          width={width}
          title={title}
          showVolume={showVolume}
          fitContent={fitContent}
          autoResize={autoResize}
          onCrosshairMove={handleCrosshairMove}
          onChartInit={handleChartInit}
          className="main-chart"
        />
        
        {/* Overlay Indicators */}
        {mainChartRef.current && overlayIndicators.map(({ config, data, type }) => (
          <IndicatorSeries
            key={config.id}
            chart={mainChartRef.current}
            data={data}
            config={config}
            type={type}
            visible={config.visible}
          />
        ))}
        
        {/* Indicator Tooltips */}
        {showTooltips && crosshairData && mainChartRef.current && (
          <div className="indicator-tooltip-container">
            {overlayIndicators.map(({ config, data, metadata }) => (
              <IndicatorTooltip
                key={config.id}
                crosshairData={crosshairData}
                indicatorData={data}
                config={config}
                metadata={metadata}
                position="right"
              />
            ))}
          </div>
        )}
      </div>
      
      {/* Indicator Panels */}
      {mainChartRef.current && panelIndicators.map(({ config, data, metadata, type }) => (
        <IndicatorPanel
          key={config.id}
          mainChart={mainChartRef.current}
          data={data}
          config={config}
          type={type}
          height={config.panelHeight || panelHeight}
          width={width}
          title={metadata.name}
          visible={config.visible}
          onRemove={() => handleIndicatorRemove(config.id)}
        />
      ))}
    </div>
  );
};

export default IndicatorChart;