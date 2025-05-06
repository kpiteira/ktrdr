// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/charts/indicators/IndicatorTooltip.tsx
import React from 'react';
import { CrosshairData } from '../core/CrosshairInfo';
import { IndicatorData, IndicatorConfig, IndicatorMetadata } from '../../../types/data';
import { useTheme } from '../../layouts/ThemeProvider';
import './IndicatorTooltip.css';

interface IndicatorTooltipProps {
  crosshairData: CrosshairData;
  indicatorData: IndicatorData;
  config: IndicatorConfig;
  metadata: IndicatorMetadata;
  position?: 'left' | 'right';
}

/**
 * IndicatorTooltip component
 * 
 * Displays indicator values at the current crosshair position with detailed information.
 */
const IndicatorTooltip: React.FC<IndicatorTooltipProps> = ({
  crosshairData,
  indicatorData,
  config,
  metadata,
  position = 'right'
}) => {
  const { theme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // Find the relevant data point for the crosshair time
  const crosshairTime = crosshairData.time;
  const index = indicatorData.dates.findIndex(date => {
    if (typeof date === 'string' && typeof crosshairTime === 'string') {
      return date === crosshairTime;
    } else if (typeof date === 'number' && typeof crosshairTime === 'number') {
      return date === crosshairTime;
    }
    return false;
  });
  
  // If no data point found at crosshair position, don't render anything
  if (index === -1) {
    return null;
  }
  
  // Get values for the crosshair position
  const values = indicatorData.values.map(series => series[index]);
  
  // Skip if all values are invalid
  const hasValidValues = values.some(value => value !== null && value !== undefined && !isNaN(value));
  if (!hasValidValues) {
    return null;
  }
  
  // Get series names from metadata
  const seriesNames = indicatorData.metadata?.names || 
    Array(values.length).fill(0).map((_, i) => 
      values.length === 1 ? metadata.name : `${metadata.name} ${i+1}`
    );
  
  // Get colors for each series
  const colors = config.colors.length >= values.length 
    ? config.colors 
    : [...config.colors, ...Array(values.length - config.colors.length).fill('#999')];
  
  // Get precision for formatting
  const precision = indicatorData.metadata?.precision || 2;
  
  return (
    <div className={`indicator-tooltip ${isDarkTheme ? 'dark-theme' : 'light-theme'} position-${position}`}>
      <div className="indicator-tooltip-header">
        <span className="tooltip-title">{metadata.name}</span>
      </div>
      <div className="indicator-tooltip-content">
        <table className="indicator-values-table">
          <tbody>
            {values.map((value, i) => (
              <tr key={i} className="indicator-value-row">
                <td className="indicator-series-name">
                  <span 
                    className="color-marker" 
                    style={{ backgroundColor: colors[i] }}
                  ></span>
                  {seriesNames[i]}:
                </td>
                <td className="indicator-value">
                  {value !== null && value !== undefined && !isNaN(value) 
                    ? value.toFixed(precision) 
                    : 'n/a'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IndicatorTooltip;