import React, { useState } from 'react';
import { TimeNavigation } from './';
import './ChartToolbar.css';

export interface ToolbarAction {
  /** Unique ID for the action */
  id: string;
  /** Label to display */
  label: string;
  /** Icon to display (optional) */
  icon?: React.ReactNode;
  /** Whether the action is currently active */
  isActive?: boolean;
  /** Callback when the action is clicked */
  onClick: () => void;
}

export interface ChartToolbarProps {
  /** Chart instance to control */
  chart: any; // This would ideally be typed as IChartApi from lightweight-charts
  /** CSS class name for additional styling */
  className?: string;
  /** Whether to show time navigation controls */
  showTimeNavigation?: boolean;
  /** Additional actions to include in the toolbar */
  actions?: ToolbarAction[];
  /** Whether to show the options button */
  showOptionsButton?: boolean;
  /** Callback when options button is clicked */
  onOptionsClick?: () => void;
}

/**
 * ChartToolbar component
 * 
 * Provides a toolbar with controls for chart interaction
 */
const ChartToolbar: React.FC<ChartToolbarProps> = ({
  chart,
  className = '',
  showTimeNavigation = true,
  actions = [],
  showOptionsButton = true,
  onOptionsClick
}) => {
  const [expanded, setExpanded] = useState(true);

  // Toggle toolbar expansion
  const toggleExpanded = () => {
    setExpanded(!expanded);
  };

  // Handle options button click
  const handleOptionsClick = () => {
    if (onOptionsClick) {
      onOptionsClick();
    }
  };

  return (
    <div className={`chart-toolbar ${expanded ? 'expanded' : 'collapsed'} ${className}`}>
      <div className="toolbar-toggle" onClick={toggleExpanded} title={expanded ? 'Collapse toolbar' : 'Expand toolbar'}>
        {expanded ? '▼' : '▲'}
      </div>

      {expanded && (
        <div className="toolbar-content">
          {showTimeNavigation && chart && (
            <div className="toolbar-section time-navigation-section">
              <TimeNavigation chart={chart} />
            </div>
          )}

          {actions.length > 0 && (
            <div className="toolbar-section actions-section">
              {actions.map(action => (
                <button
                  key={action.id}
                  className={`toolbar-action ${action.isActive ? 'active' : ''}`}
                  onClick={action.onClick}
                  title={action.label}
                >
                  {action.icon || action.label}
                </button>
              ))}
            </div>
          )}

          {showOptionsButton && (
            <div className="toolbar-section options-section">
              <button
                className="options-button"
                onClick={handleOptionsClick}
                title="Chart Options"
              >
                ⚙️
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ChartToolbar;