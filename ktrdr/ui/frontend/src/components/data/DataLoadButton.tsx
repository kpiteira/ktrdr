import React from 'react';
import { Button, LoadingSpinner } from '../common';
import { useOhlcvData, useDataSelection } from '../../store/hooks';

interface DataLoadButtonProps {
  className?: string;
  dateRange?: { startDate: string; endDate: string };
  onDataLoaded?: () => void;
  variant?: 'primary' | 'secondary' | 'outline';
  size?: 'small' | 'medium' | 'large';
}

export const DataLoadButton: React.FC<DataLoadButtonProps> = ({
  className = '',
  dateRange,
  onDataLoaded,
  variant = 'primary',
  size = 'medium'
}) => {
  const { currentSymbol, currentTimeframe, hasActiveSelection } = useDataSelection();
  const { dataStatus, loadData } = useOhlcvData();
  
  // Check if data is currently loading
  const isLoading = dataStatus === 'loading';
  
  // Button should be disabled if we don't have a symbol and timeframe selected
  // or if data is currently loading
  const isDisabled = !hasActiveSelection || isLoading;
  
  // Handle button click
  const handleClick = () => {
    // Only proceed if we have both symbol and timeframe
    if (currentSymbol && currentTimeframe) {
      loadData({
        symbol: currentSymbol,
        timeframe: currentTimeframe,
        startDate: dateRange?.startDate,
        endDate: dateRange?.endDate
      });
      
      // Notify parent component when data is loaded (if callback is provided)
      if (onDataLoaded && !isLoading) {
        onDataLoaded();
      }
    } else {
      console.warn('Cannot load data: Symbol or timeframe is missing');
    }
  };
  
  return (
    <div className={`data-load-button ${className}`}>
      <Button
        onClick={handleClick}
        disabled={isDisabled}
        variant={variant}
        size={size}
      >
        {isLoading ? (
          <>
            <LoadingSpinner size="small" />
            <span style={{ marginLeft: '8px' }}>Loading...</span>
          </>
        ) : (
          'Load Data'
        )}
      </Button>
    </div>
  );
};

export default DataLoadButton;