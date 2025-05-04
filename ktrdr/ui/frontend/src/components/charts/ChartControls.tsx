import React from 'react';
import { IChartApi } from 'lightweight-charts';
import { Button } from '../common/Button';

import './ChartControls.css';

export interface ChartControlsProps {
  /** Chart instance */
  chart: IChartApi | null;
  /** Whether to show zoom controls */
  showZoom?: boolean;
  /** Whether to show the reset button */
  showReset?: boolean;
  /** Whether to show the toggle volume button */
  showVolumeToggle?: boolean;
  /** Whether volume is currently visible */
  volumeVisible?: boolean;
  /** Callback when volume toggle is clicked */
  onVolumeToggle?: () => void;
  /** Custom class name */
  className?: string;
}

/**
 * ChartControls component
 * 
 * Provides user controls for chart interactions like zoom, reset, etc.
 */
export const ChartControls: React.FC<ChartControlsProps> = ({
  chart,
  showZoom = true,
  showReset = true,
  showVolumeToggle = true,
  volumeVisible = true,
  onVolumeToggle,
  className = '',
}) => {
  // Handle zoom in action
  const handleZoomIn = () => {
    if (!chart) return;
    
    // Scale time by a factor of 0.5 (zoom in)
    const timeScale = chart.timeScale();
    timeScale.zoom(0.5);
  };

  // Handle zoom out action
  const handleZoomOut = () => {
    if (!chart) return;
    
    // Scale time by a factor of 2 (zoom out)
    const timeScale = chart.timeScale();
    timeScale.zoom(2);
  };

  // Handle reset action
  const handleReset = () => {
    if (!chart) return;
    
    // Reset the chart to fit all content
    const timeScale = chart.timeScale();
    timeScale.fitContent();
  };

  return (
    <div className={`chart-controls ${className}`}>
      {showZoom && (
        <div className="chart-controls-zoom">
          <Button 
            variant="ghost"
            size="small"
            onClick={handleZoomIn}
            aria-label="Zoom in"
          >
            <span className="chart-controls-icon">➕</span>
          </Button>
          <Button 
            variant="ghost"
            size="small"
            onClick={handleZoomOut}
            aria-label="Zoom out"
          >
            <span className="chart-controls-icon">➖</span>
          </Button>
        </div>
      )}
      
      {showReset && (
        <Button 
          variant="ghost"
          size="small"
          onClick={handleReset}
          aria-label="Reset view"
        >
          <span className="chart-controls-icon">🔄</span>
        </Button>
      )}
      
      {showVolumeToggle && onVolumeToggle && (
        <Button 
          variant="ghost"
          size="small"
          onClick={onVolumeToggle}
          aria-label={volumeVisible ? "Hide volume" : "Show volume"}
        >
          <span className="chart-controls-icon">
            {volumeVisible ? "📊" : "📈"}
          </span>
        </Button>
      )}
    </div>
  );
};

export default ChartControls;