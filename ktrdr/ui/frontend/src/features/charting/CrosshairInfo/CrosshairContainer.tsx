import React from 'react';
import PriceLabel from './PriceLabel';
import './CrosshairContainer.css';

export interface CrosshairData {
  /** Time value (can be date string or timestamp) */
  time: string | number;
  /** Price values for each series */
  prices: {
    [seriesId: string]: {
      value: number;
      color?: string;
      seriesName?: string;
    };
  };
  /** Additional contextual data */
  additionalData?: Record<string, any>;
}

export interface CrosshairContainerProps {
  /** Crosshair data to display */
  data?: CrosshairData;
  /** Whether the crosshair is currently visible */
  visible?: boolean;
  /** Function to format the time value */
  formatTime?: (time: string | number) => string;
  /** CSS class name for additional styling */
  className?: string;
  /** Position of the price labels */
  priceLabelsPosition?: 'left' | 'right';
  /** Default decimal places for price formatting */
  priceDecimals?: number;
}

/**
 * CrosshairContainer component
 * 
 * Displays information at the crosshair position including time and prices
 */
const CrosshairContainer: React.FC<CrosshairContainerProps> = ({
  data,
  visible = false,
  formatTime = (time) => typeof time === 'string' ? time : new Date(time).toLocaleString(),
  className = '',
  priceLabelsPosition = 'right',
  priceDecimals = 2
}) => {
  if (!data || !visible) {
    return null;
  }

  // Get the main price (first or primary series)
  const mainSeriesId = Object.keys(data.prices)[0];
  const mainPrice = mainSeriesId ? data.prices[mainSeriesId].value : null;

  // Format time
  const formattedTime = formatTime(data.time);

  return (
    <div className={`crosshair-container ${className}`}>
      {/* Time label at the bottom */}
      <div className="time-label">
        {formattedTime}
      </div>

      {/* Price labels */}
      <div className="price-labels">
        {Object.entries(data.prices).map(([seriesId, priceData]) => (
          <PriceLabel
            key={seriesId}
            price={priceData.value}
            direction={
              mainPrice !== null
                ? priceData.value > mainPrice
                  ? 'up'
                  : priceData.value < mainPrice
                  ? 'down'
                  : 'neutral'
                : 'neutral'
            }
            decimals={priceDecimals}
            position={priceLabelsPosition}
            className={`price-label-${seriesId}`}
          />
        ))}
      </div>
    </div>
  );
};

export default CrosshairContainer;