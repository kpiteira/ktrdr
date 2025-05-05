import React from 'react';
import LegendItem from './LegendItem';
import './LegendContainer.css';

export interface LegendItemData {
  /** Label for the legend item */
  label: string;
  /** Value to display */
  value: string | number;
  /** Color indicator for the legend item */
  color?: string;
  /** Whether the item is active and visible */
  isActive?: boolean;
  /** Unique ID for the legend item */
  id: string;
}

export interface LegendContainerProps {
  /** Array of legend item data */
  items: LegendItemData[];
  /** Position of the legend */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** CSS class name for additional styling */
  className?: string;
  /** Title for the legend */
  title?: string;
  /** Callback when a legend item is clicked */
  onItemClick?: (itemId: string) => void;
}

/**
 * LegendContainer component
 * 
 * Displays a container with chart legend items showing current values
 */
const LegendContainer: React.FC<LegendContainerProps> = ({
  items,
  position = 'top',
  className = '',
  title,
  onItemClick
}) => {
  // Handle legend item click
  const handleItemClick = (itemId: string) => {
    if (onItemClick) {
      onItemClick(itemId);
    }
  };

  return (
    <div className={`legend-container position-${position} ${className}`}>
      {title && <div className="legend-title">{title}</div>}
      <div className="legend-items-container">
        {items.map((item) => (
          <LegendItem
            key={item.id}
            label={item.label}
            value={item.value}
            color={item.color}
            isActive={item.isActive !== false}
            onClick={() => handleItemClick(item.id)}
          />
        ))}
      </div>
    </div>
  );
};

export default LegendContainer;