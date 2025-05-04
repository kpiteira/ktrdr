import React, { useEffect, useState } from 'react';
import { Card, ErrorMessage } from '../common';
import { useDataSelection, useOhlcvData } from '../../store/hooks';
import SymbolSelector from './SymbolSelector';
import TimeframeSelector from './TimeframeSelector';
import DateRangePicker from './DateRangePicker';
import DataLoadButton from './DataLoadButton';

interface DataSelectionPanelProps {
  className?: string;
  onDataLoaded?: () => void;
  autoLoadMetadata?: boolean;
}

export const DataSelectionPanel: React.FC<DataSelectionPanelProps> = ({
  className = '',
  onDataLoaded,
  autoLoadMetadata = true
}) => {
  const { loadMetadata } = useDataSelection();
  const { errorMessage, resetData } = useOhlcvData();
  const [dateRange, setDateRange] = useState<{ startDate: string; endDate: string }>({
    startDate: '',
    endDate: ''
  });
  
  // Load metadata on component mount if autoLoadMetadata is true
  useEffect(() => {
    if (autoLoadMetadata) {
      loadMetadata();
    }
  }, [autoLoadMetadata, loadMetadata]);
  
  // Handle date range changes
  const handleDateRangeChange = (range: { startDate: string; endDate: string }) => {
    setDateRange(range);
  };
  
  // Handle reset button click
  const handleReset = () => {
    resetData();
  };
  
  return (
    <div className={`data-selection-panel ${className}`}>
      <Card title="Data Selection">
        <div className="data-selection-content">
          {/* Display errors if any */}
          {errorMessage && (
            <ErrorMessage message={errorMessage} />
          )}
          
          <div className="selection-grid">
            {/* Symbol and Timeframe selectors */}
            <div className="selection-row">
              <SymbolSelector />
              <TimeframeSelector />
            </div>
            
            {/* Date range picker */}
            <div className="date-range-section">
              <h4>Date Range</h4>
              <DateRangePicker 
                startDate={dateRange.startDate}
                endDate={dateRange.endDate}
                onDateRangeChange={handleDateRangeChange}
              />
            </div>
            
            {/* Action buttons */}
            <div className="action-buttons">
              <DataLoadButton 
                dateRange={dateRange}
                onDataLoaded={onDataLoaded}
              />
              <button 
                className="reset-button" 
                onClick={handleReset}
                type="button"
              >
                Reset
              </button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default DataSelectionPanel;