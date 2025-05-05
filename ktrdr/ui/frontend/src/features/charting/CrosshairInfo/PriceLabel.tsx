import React from 'react';
import './PriceLabel.css';

export interface PriceLabelProps {
  /** Price value to display */
  price: number;
  /** Whether this is an up or down move (affects color) */
  direction?: 'up' | 'down' | 'neutral';
  /** Format the price with specific decimal places */
  decimals?: number;
  /** Additional className for styling */
  className?: string;
  /** Position of the label */
  position?: 'left' | 'right';
}

/**
 * PriceLabel component
 * 
 * Displays a price label at the crosshair y-position
 */
const PriceLabel: React.FC<PriceLabelProps> = ({
  price,
  direction = 'neutral',
  decimals = 2,
  className = '',
  position = 'right'
}) => {
  // Format the price with the specified number of decimal places
  const formattedPrice = price.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });

  // Set color based on price direction
  const getDirectionColor = () => {
    switch (direction) {
      case 'up':
        return 'price-up';
      case 'down':
        return 'price-down';
      default:
        return 'price-neutral';
    }
  };

  return (
    <div className={`price-label ${getDirectionColor()} position-${position} ${className}`}>
      {formattedPrice}
    </div>
  );
};

export default PriceLabel;