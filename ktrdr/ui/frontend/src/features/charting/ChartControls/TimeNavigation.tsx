import React from 'react';
import './TimeNavigation.css';

export interface TimeNavigationProps {
  /** Chart instance to control */
  chart: any; // This would ideally be typed as IChartApi from lightweight-charts
  /** CSS class name for additional styling */
  className?: string;
  /** Whether to show zoom buttons */
  showZoomButtons?: boolean;
  /** Whether to show pan buttons */
  showPanButtons?: boolean;
  /** Whether to show reset button */
  showResetButton?: boolean;
  /** Whether to show all data button */
  showFitContentButton?: boolean;
  /** Callback when a button is clicked */
  onButtonClick?: (action: 'zoomIn' | 'zoomOut' | 'panLeft' | 'panRight' | 'reset' | 'fitContent') => void;
}

/**
 * TimeNavigation component
 * 
 * Provides zoom, pan, and reset controls for chart time navigation
 */
const TimeNavigation: React.FC<TimeNavigationProps> = ({
  chart,
  className = '',
  showZoomButtons = true,
  showPanButtons = true,
  showResetButton = true,
  showFitContentButton = true,
  onButtonClick
}) => {
  // Handle zoom in
  const handleZoomIn = () => {
    if (!chart) return;
    
    try {
      const timeScale = chart.timeScale();
      // Get current visible logical range
      const range = timeScale.getVisibleLogicalRange();
      if (range) {
        // Calculate new range (zoomed in)
        const newRange = {
          from: range.from + (range.to - range.from) * 0.25,
          to: range.to - (range.to - range.from) * 0.25
        };
        // Set the new range
        timeScale.setVisibleLogicalRange(newRange);
      }
    } catch (error) {
      console.error('Error zooming in:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('zoomIn');
    }
  };

  // Handle zoom out
  const handleZoomOut = () => {
    if (!chart) return;
    
    try {
      const timeScale = chart.timeScale();
      // Get current visible logical range
      const range = timeScale.getVisibleLogicalRange();
      if (range) {
        // Calculate new range (zoomed out)
        const rangeSize = range.to - range.from;
        const newRange = {
          from: range.from - rangeSize * 0.25,
          to: range.to + rangeSize * 0.25
        };
        // Set the new range
        timeScale.setVisibleLogicalRange(newRange);
      }
    } catch (error) {
      console.error('Error zooming out:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('zoomOut');
    }
  };

  // Handle pan left
  const handlePanLeft = () => {
    if (!chart) return;
    
    try {
      const timeScale = chart.timeScale();
      // Get current visible logical range
      const range = timeScale.getVisibleLogicalRange();
      if (range) {
        // Calculate new range (panned left)
        const shift = (range.to - range.from) * 0.2;
        const newRange = {
          from: range.from - shift,
          to: range.to - shift
        };
        // Set the new range
        timeScale.setVisibleLogicalRange(newRange);
      }
    } catch (error) {
      console.error('Error panning left:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('panLeft');
    }
  };

  // Handle pan right
  const handlePanRight = () => {
    if (!chart) return;
    
    try {
      const timeScale = chart.timeScale();
      // Get current visible logical range
      const range = timeScale.getVisibleLogicalRange();
      if (range) {
        // Calculate new range (panned right)
        const shift = (range.to - range.from) * 0.2;
        const newRange = {
          from: range.from + shift,
          to: range.to + shift
        };
        // Set the new range
        timeScale.setVisibleLogicalRange(newRange);
      }
    } catch (error) {
      console.error('Error panning right:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('panRight');
    }
  };

  // Handle reset to default view
  const handleReset = () => {
    if (!chart) return;
    
    try {
      const timeScale = chart.timeScale();
      // Reset to default view (last 50 bars)
      const visibleBars = 50;
      const points = chart.serieses()[0]?.data()?.length || 0;
      if (points > 0) {
        timeScale.setVisibleLogicalRange({
          from: Math.max(0, points - visibleBars),
          to: points
        });
      }
    } catch (error) {
      console.error('Error resetting view:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('reset');
    }
  };

  // Handle fit content to view all data
  const handleFitContent = () => {
    if (!chart) return;
    
    try {
      chart.timeScale().fitContent();
    } catch (error) {
      console.error('Error fitting content:', error);
    }
    
    if (onButtonClick) {
      onButtonClick('fitContent');
    }
  };

  return (
    <div className={`time-navigation ${className}`}>
      {showZoomButtons && (
        <div className="zoom-controls">
          <button 
            className="zoom-button zoom-in"
            onClick={handleZoomIn}
            title="Zoom In"
          >
            +
          </button>
          <button 
            className="zoom-button zoom-out"
            onClick={handleZoomOut}
            title="Zoom Out"
          >
            -
          </button>
        </div>
      )}
      
      {showPanButtons && (
        <div className="pan-controls">
          <button 
            className="pan-button pan-left"
            onClick={handlePanLeft}
            title="Pan Left"
          >
            ←
          </button>
          <button 
            className="pan-button pan-right"
            onClick={handlePanRight}
            title="Pan Right"
          >
            →
          </button>
        </div>
      )}
      
      <div className="additional-controls">
        {showResetButton && (
          <button 
            className="reset-button"
            onClick={handleReset}
            title="Reset View"
          >
            Reset
          </button>
        )}
        
        {showFitContentButton && (
          <button 
            className="fit-content-button"
            onClick={handleFitContent}
            title="Fit All Data"
          >
            Fit
          </button>
        )}
      </div>
    </div>
  );
};

export default TimeNavigation;