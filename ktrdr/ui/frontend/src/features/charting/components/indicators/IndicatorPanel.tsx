// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/indicators/IndicatorPanel.tsx
import React, { useState, useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import { 
  IndicatorData, 
  IndicatorConfig, 
  IndicatorType
} from '../../../types/data';
import { useTheme } from '../../layouts/ThemeProvider';
import IndicatorSeries from './IndicatorSeries';
import './IndicatorPanel.css';

/**
 * Format a date to YYYY-MM-DD format required by lightweight-charts
 */
const formatDateForChart = (date: string | number): string => {
  if (typeof date === 'string' && date.includes('T')) {
    // Convert ISO date string (2025-01-25T03:25:26.115Z) to yyyy-mm-dd
    return date.split('T')[0];
  }
  
  // Handle numeric timestamps or other formats
  if (typeof date === 'number' || !date.match(/^\d{4}-\d{2}-\d{2}$/)) {
    const dateObj = new Date(date);
    return dateObj.toISOString().split('T')[0];
  }
  
  // Already in correct format
  return date;
};

interface IndicatorPanelProps {
  /** Main chart that this panel will synchronize with */
  mainChart: IChartApi;
  /** Indicator data to visualize */
  data: IndicatorData;
  /** Indicator configuration */
  config: IndicatorConfig;
  /** Indicator type */
  type: IndicatorType;
  /** Height of the panel in pixels */
  height?: number;
  /** Width of the panel in pixels, defaults to container width */
  width?: number;
  /** Panel title */
  title?: string;
  /** Whether the panel is visible */
  visible?: boolean;
  /** Callback when user clicks remove button */
  onRemove?: () => void;
}

/**
 * IndicatorPanel component
 * 
 * Creates a separate chart panel for displaying indicators below the main chart.
 * Synchronizes time scale with the main chart for unified navigation.
 */
const IndicatorPanel: React.FC<IndicatorPanelProps> = ({
  mainChart,
  data,
  config,
  type,
  height = 150,
  width,
  title,
  visible = true,
  onRemove
}) => {
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  
  // Get time range updates from main chart
  useEffect(() => {
    if (!mainChart || !chartRef.current || !visible) return;
    
    // Synchronize visible time range
    const mainTimeScale = mainChart.timeScale();
    const panelTimeScale = chartRef.current.timeScale();
    
    const syncTimeRange = () => {
      try {
        const visibleRange = mainTimeScale.getVisibleRange();
        
        // Only proceed if we have a valid range
        if (visibleRange && panelTimeScale && 
            visibleRange.from && visibleRange.to) {
          
          // Create a safe copy with properly formatted dates
          const safeRange = {
            from: formatDateForChart(visibleRange.from),
            to: formatDateForChart(visibleRange.to)
          };
          
          // Only set the visible range if we have valid dates
          if (safeRange.from && safeRange.to) {
            panelTimeScale.setVisibleRange(safeRange);
          }
        }
      } catch (error) {
        // Silently handle any errors during synchronization
        console.debug('Error synchronizing indicator time scale:', error);
      }
    };
    
    // Wait a small delay before initial synchronization to ensure chart is ready
    const initialSyncTimeout = setTimeout(() => {
      try {
        syncTimeRange();
      } catch (error) {
        console.debug('Error during initial time scale sync:', error);
      }
    }, 100);
    
    // Subscribe to time range changes
    const mainTimeScaleApi = mainTimeScale;
    let subscription;
    try {
      subscription = mainTimeScaleApi.subscribeVisibleTimeRangeChange(syncTimeRange);
    } catch (error) {
      console.debug('Error subscribing to time range changes:', error);
    }
    
    return () => {
      clearTimeout(initialSyncTimeout);
      if (subscription) {
        try {
          subscription.unsubscribe();
        } catch (error) {
          console.debug('Error unsubscribing from time range changes:', error);
        }
      }
    };
  }, [mainChart, visible]);
  
  // Initialize chart
  useEffect(() => {
    if (!containerRef.current || !visible) return;
    
    // Clear any existing chart
    if (chartRef.current) {
      try {
        chartRef.current.remove();
      } catch (error) {
        console.debug('Error removing existing chart:', error);
      }
      chartRef.current = null;
    }
    
    // Theme-specific chart options
    const chartOptions = {
      width: width || containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: isDarkTheme ? '#1E1E1E' : '#FFFFFF' },
        textColor: isDarkTheme ? '#D9D9D9' : '#333333',
      },
      grid: {
        vertLines: { color: isDarkTheme ? '#2B2B43' : '#E6E6E6' },
        horzLines: { color: isDarkTheme ? '#2B2B43' : '#E6E6E6' },
      },
      timeScale: {
        borderColor: isDarkTheme ? '#2B2B43' : '#E6E6E6',
        timeVisible: true,
        borderVisible: false,
      },
      rightPriceScale: {
        borderColor: isDarkTheme ? '#2B2B43' : '#E6E6E6',
      },
      handleScroll: false,
      handleScale: false,
    };
    
    try {
      // Create chart instance
      const chart = createChart(containerRef.current, chartOptions);
      chartRef.current = chart;
      
      // Handle resize
      const handleResize = () => {
        if (containerRef.current && chart && !chart.isDisposed?.()) {
          try {
            chart.applyOptions({ 
              width: width || containerRef.current.clientWidth
            });
          } catch (error) {
            console.debug('Error resizing chart:', error);
          }
        }
      };
      
      window.addEventListener('resize', handleResize);
      
      return () => {
        window.removeEventListener('resize', handleResize);
        if (chart && !chart.isDisposed?.()) {
          try {
            chart.remove();
          } catch (error) {
            console.debug('Error removing chart in cleanup:', error);
          }
        }
        chartRef.current = null;
      };
    } catch (error) {
      console.error('Error creating chart:', error);
      return () => {};
    }
  }, [height, width, isDarkTheme, visible]);
  
  // Don't render anything if not visible
  if (!visible) {
    return null;
  }
  
  return (
    <div className={`indicator-panel ${isDarkTheme ? 'dark-theme' : 'light-theme'}`}>
      <div className="indicator-panel-header">
        <div className="indicator-panel-title">
          {title}
        </div>
        
        {onRemove && (
          <button 
            className="indicator-panel-remove" 
            onClick={onRemove}
            title="Remove indicator"
          >
            ✕
          </button>
        )}
      </div>
      
      <div 
        ref={containerRef} 
        className="indicator-panel-chart-container"
      >
        {chartRef.current && (
          <IndicatorSeries
            chart={chartRef.current}
            data={data}
            config={config}
            type={type}
            visible
          />
        )}
      </div>
    </div>
  );
};

export default IndicatorPanel;