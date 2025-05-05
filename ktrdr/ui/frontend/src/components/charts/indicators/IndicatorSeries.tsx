// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/indicators/IndicatorSeries.tsx
import React, { useEffect, useRef } from 'react';
import { 
  IndicatorData, 
  IndicatorConfig, 
  IndicatorType
} from '../../../types/data';
import { formatIndicatorForChart } from '../transformers/indicatorAdapters';

interface IndicatorSeriesProps {
  /** Chart instance to render the indicator on */
  chart: any;
  /** Indicator data to visualize */
  data: IndicatorData;
  /** Indicator configuration */
  config: IndicatorConfig;
  /** Indicator type */
  type: IndicatorType;
  /** Whether the indicator is visible */
  visible?: boolean;
}

/**
 * Check if chart is disposed safely
 */
const isChartDisposed = (chart: any): boolean => {
  try {
    return chart.isDisposed?.() === true;
  } catch (error) {
    return true; // If we can't check, assume it's disposed for safety
  }
};

/**
 * IndicatorSeries component
 * 
 * Renders indicator series as overlays on an existing chart.
 * Supports various indicator types with appropriate visualization.
 */
const IndicatorSeries: React.FC<IndicatorSeriesProps> = ({
  chart,
  data,
  config,
  type,
  visible = true
}) => {
  // Store series references
  const seriesRefs = useRef<any[]>([]);
  
  // Create and update series on changes
  useEffect(() => {
    if (!chart || !data || isChartDisposed(chart)) return;
    
    // Clear existing series
    try {
      seriesRefs.current.forEach(series => {
        if (chart && !isChartDisposed(chart)) {
          try {
            chart.removeSeries(series);
          } catch (error) {
            console.debug('Error removing series:', error);
          }
        }
      });
      seriesRefs.current = [];
    } catch (error) {
      console.debug('Error clearing existing series:', error);
      seriesRefs.current = [];
    }
    
    // Don't create new series if not visible
    if (!visible) return;
    
    try {
      // Format data for the chart
      const { seriesData, seriesOptions } = formatIndicatorForChart(data, config, type);
      
      // Create series for each data set
      seriesData.forEach((dataset, index) => {
        if (isChartDisposed(chart)) return;
        
        try {
          // Create appropriate series type based on indicator type and index
          let series;
          
          if (type === IndicatorType.HISTOGRAM) {
            series = chart.addHistogramSeries(seriesOptions[index]);
          } else if (type === IndicatorType.AREA) {
            series = chart.addAreaSeries(seriesOptions[index]);
          } else if (type === IndicatorType.CLOUD && index === 0) {
            // First cloud dataset is an area series
            series = chart.addAreaSeries(seriesOptions[index]);
          } else if (type === IndicatorType.CLOUD && index === 1) {
            // Second cloud dataset needs special handling
            // It's actually rendered as an area series with boundaries
            series = chart.addAreaSeries(seriesOptions[index]);
          } else {
            // Default to line series
            series = chart.addLineSeries(seriesOptions[index]);
          }
          
          // Set the data for this series
          if (series) {
            series.setData(dataset);
            
            // Store reference to series
            seriesRefs.current.push(series);
          }
        } catch (error) {
          console.debug(`Error creating series at index ${index}:`, error);
        }
      });
    } catch (error) {
      console.debug('Error formatting or creating indicator series:', error);
    }
    
    // Clean up function that removes series when unmounting
    return () => {
      try {
        seriesRefs.current.forEach(series => {
          if (chart && !isChartDisposed(chart)) {
            try {
              chart.removeSeries(series);
            } catch (error) {
              console.debug('Error removing series during cleanup:', error);
            }
          }
        });
      } catch (error) {
        console.debug('Error during series cleanup:', error);
      }
      seriesRefs.current = [];
    };
  }, [chart, data, config, type, visible]);
  
  // The component doesn't render anything visible itself
  return null;
};

export default IndicatorSeries;