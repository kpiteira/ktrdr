import React from 'react';
import './LegendItem.css';

export interface LegendItemProps {
  /** Label for the legend item */
  label: string;
  /** Value to display */
  value: string | number;
  /** Color indicator for the legend item */
  color?: string;
  /** CSS class name for additional styling */
  className?: string;
  /** Whether the item is currently active */
  isActive?: boolean;
  /** Callback for when the item is clicked */
  onClick?: () => void;
}

/**
 * LegendItem component
 * 
 * Displays a single item in the chart legend with label, value, and color indicator
 */
const LegendItem: React.FC<LegendItemProps> = ({
  label,
  value,
  color = '#999',
  className = '',
  isActive = true,
  onClick
}) => {
  const formattedValue = typeof value === 'number' 
    ? value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : value;

  const handleClick = () => {
    if (onClick) {
      onClick();
    }
  };

  return (
    <div 
      className={`legend-item ${isActive ? 'active' : 'inactive'} ${className}`}
      onClick={handleClick}
      style={{ opacity: isActive ? 1 : 0.5, cursor: onClick ? 'pointer' : 'default' }}
    >
      <div 
        className="legend-color-indicator"
        style={{ backgroundColor: color }}
      />
      <div className="legend-content">
        <span className="legend-label">{label}</span>
        <span className="legend-value">{formattedValue}</span>
      </div>
    </div>
  );
};

export default LegendItem;