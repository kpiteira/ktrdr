import React, { useState, useEffect } from 'react';
import { Card, Button, ErrorMessage } from '../components/common';
import { 
  SymbolSelector, 
  TimeframeSelector, 
  DateRangePicker, 
  DataLoadButton,
  DataPreview
} from '../components/data';
import { useThemeControl, useDataSelection, useOhlcvData } from '../store/hooks';

/**
 * DataSelectionContainer provides a clean, integrated example of all data selection components
 * working together in a unified interface.
 */
const DataSelectionContainer: React.FC = () => {
  const { theme, toggleTheme } = useThemeControl();
  const { loadMetadata, symbols, timeframes } = useDataSelection();
  const { errorMessage } = useOhlcvData();
  const [dateRange, setDateRange] = useState<{ startDate: string; endDate: string }>({
    startDate: '',
    endDate: ''
  });
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Load metadata (symbols and timeframes) when the component mounts
  useEffect(() => {
    console.log("DataSelectionContainer mounted, loading metadata");
    
    // Load metadata with error handling
    const loadMetadataWithErrorHandling = async () => {
      try {
        await loadMetadata();
        setConnectionError(null);
      } catch (error) {
        console.error('Failed to load metadata:', error);
        setConnectionError('Failed to connect to the API server. Please check your network connection and server status.');
      }
    };
    
    loadMetadataWithErrorHandling();
    
    // Apply theme to document
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [loadMetadata]);

  // Update document theme when theme changes
  useEffect(() => {
    console.log("Theme changed:", theme);
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  // Handle date range changes
  const handleDateRangeChange = (range: { startDate: string; endDate: string }) => {
    setDateRange(range);
  };

  // Handle reload button
  const handleReload = async () => {
    try {
      await loadMetadata();
      setConnectionError(null);
    } catch (error) {
      console.error('Failed to reload metadata:', error);
      setConnectionError('Failed to connect to the API server. Please check your network connection and server status.');
    }
  };

  return (
    <div className="data-selection-container">
      <div className="theme-toggle" style={{ textAlign: 'right', marginBottom: '16px' }}>
        <Button 
          onClick={toggleTheme} 
          variant="outline"
          size="small"
        >
          {theme === 'light' ? '🌙 Switch to Dark Mode' : '☀️ Switch to Light Mode'}
        </Button>
      </div>
      
      {/* Connection error message */}
      {connectionError && (
        <ErrorMessage 
          message="API Connection Error" 
          details={connectionError}
          actions={
            <Button 
              onClick={handleReload} 
              size="small" 
              variant="primary"
              style={{ marginLeft: '10px' }}
            >
              Retry Connection
            </Button>
          }
        />
      )}
      
      {/* Data selection card */}
      <Card title="Market Data Selection">
        <div className="selection-panel">
          <div className="selection-grid">
            <div className="selection-row">
              <SymbolSelector />
              <TimeframeSelector />
            </div>
            
            <div className="date-range-section">
              <h4>Date Range</h4>
              <DateRangePicker 
                startDate={dateRange.startDate}
                endDate={dateRange.endDate}
                onDateRangeChange={handleDateRangeChange}
              />
            </div>
            
            <div className="action-buttons">
              <DataLoadButton dateRange={dateRange} />
            </div>
          </div>
        </div>
      </Card>
      
      {/* Error messages from data operations */}
      {errorMessage && !connectionError && (
        <div style={{ marginTop: '20px' }}>
          <ErrorMessage message={errorMessage} />
        </div>
      )}
      
      {/* Data preview */}
      <div style={{ marginTop: '24px' }}>
        <DataPreview maxPreviewRows={5} />
      </div>
    </div>
  );
};

export default DataSelectionContainer;