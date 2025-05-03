/**
 * Example DataViewer component
 * Demonstrates how to use Redux for state management
 */

import React, { useEffect, useState } from 'react';
import { 
  Card, 
  Select, 
  Button, 
  LoadingSpinner, 
  ErrorMessage 
} from '../components/common';

// Import our Redux hooks
import {
  useDataSelection,
  useOhlcvData
} from '../store/hooks';

// Fallback data when the API fails
const FALLBACK_TIMEFRAMES = [
  { id: '1m', name: '1 Minute' },
  { id: '5m', name: '5 Minutes' },
  { id: '15m', name: '15 Minutes' },
  { id: '30m', name: '30 Minutes' },
  { id: '1h', name: '1 Hour' },
  { id: '4h', name: '4 Hours' },
  { id: '1d', name: 'Daily' },
  { id: '1w', name: 'Weekly' },
  { id: '1M', name: 'Monthly' },
];

const FALLBACK_SYMBOLS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'BTC', 'ETH'
];

/**
 * DataViewer component demonstrates the Redux integration
 * This shows how to load symbols, timeframes, and OHLCV data using Redux
 */
const DataViewer: React.FC = () => {
  // Add local state to track connection errors
  const [apiConnectionError, setApiConnectionError] = useState<boolean>(false);
  
  // Use our custom Redux hooks
  const {
    symbols,
    timeframes,
    currentSymbol,
    currentTimeframe,
    hasActiveSelection,
    loadMetadata,
    selectSymbol,
    selectTimeframe
  } = useDataSelection();

  const {
    ohlcvData,
    loadingState,
    errorMessage,
    loadData,
    resetData
  } = useOhlcvData();

  // Load symbols and timeframes on component mount
  useEffect(() => {
    const loadDataWithErrorHandling = async () => {
      try {
        await loadMetadata();
      } catch (error) {
        console.error('Failed to load metadata:', error);
        setApiConnectionError(true);
      }
    };
    
    loadDataWithErrorHandling();
  }, [loadMetadata]);

  // Handle load data button click
  const handleLoadData = () => {
    if (currentSymbol && currentTimeframe) {
      loadData({
        startDate: '2023-01-01',
        endDate: '2023-04-01'
      });
    }
  };

  // Handle reload metadata
  const handleReloadMetadata = () => {
    setApiConnectionError(false);
    loadMetadata();
  };

  // Set symbol handler
  const handleSymbolChange = (value: string) => {
    selectSymbol(value);
  };
  
  // Set timeframe handler
  const handleTimeframeChange = (value: string) => {
    selectTimeframe(value);
  };

  // Determine loading states
  const symbolsLoading = !symbols && loadingState === 'loading';
  const timeframesLoading = !timeframes && loadingState === 'loading';
  const dataLoading = loadingState === 'loading';
  
  // Determine errors
  const symbolsError = loadingState === 'failed' || apiConnectionError ? errorMessage : null;
  const timeframesError = loadingState === 'failed' || apiConnectionError ? errorMessage : null;
  const dataError = loadingState === 'failed' ? errorMessage : null;

  // Determine if the load button should be disabled
  const isLoadButtonDisabled = !currentSymbol || !currentTimeframe || dataLoading;

  // Render a summary of the loaded data
  const renderDataSummary = () => {
    if (!ohlcvData) {
      return null;
    }
    
    const { dates, ohlcv, metadata } = ohlcvData;
    
    return (
      <div className="data-summary">
        <h4>Data Summary</h4>
        <p>Symbol: {metadata.symbol}</p>
        <p>Timeframe: {metadata.timeframe}</p>
        <p>Date Range: {metadata.start} to {metadata.end}</p>
        <p>Total Points: {metadata.points}</p>
        <p>Sample Data (first 3 points):</p>
        <div className="sample-data">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>Close</th>
                <th>Volume</th>
              </tr>
            </thead>
            <tbody>
              {dates.slice(0, 3).map((date, index) => (
                <tr key={date}>
                  <td>{date}</td>
                  <td>{ohlcv[index][0].toFixed(2)}</td>
                  <td>{ohlcv[index][1].toFixed(2)}</td>
                  <td>{ohlcv[index][2].toFixed(2)}</td>
                  <td>{ohlcv[index][3].toFixed(2)}</td>
                  <td>{ohlcv[index][4].toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <Card title="Data Viewer Example (Redux)">
      {apiConnectionError && (
        <div className="api-connection-error" style={{ padding: '10px', backgroundColor: '#fff3cd', color: '#856404', borderRadius: '4px', marginBottom: '15px' }}>
          <p><strong>Backend Connection Issue:</strong> Could not connect to the backend service. Using fallback data for demonstration.</p>
          <p>Error: Cannot resolve hostname 'backend:8000'. If running locally outside Docker, try changing the API URL in the config.</p>
        </div>
      )}
      
      <div className="data-selection-container">
        <div className="selection-row">
          <label>Symbol:</label>
          {symbolsLoading ? (
            <>
              <LoadingSpinner size="small" />
              <span style={{ marginLeft: '8px' }}>Loading symbols...</span>
            </>
          ) : symbolsError ? (
            <>
              <Select
                value={currentSymbol || ''}
                options={FALLBACK_SYMBOLS.map(s => ({ value: s, label: s }))}
                onChange={handleSymbolChange}
                placeholder="Select a symbol"
              />
              <span className="error-note" style={{ fontSize: '0.8rem', color: 'orange', marginLeft: '8px' }}>
                Using fallback data
              </span>
            </>
          ) : symbols && symbols.length > 0 ? (
            <>
              <Select
                value={currentSymbol || ''}
                options={symbols.map(s => {
                  // Handle both string and object formats for symbols
                  if (typeof s === 'string') {
                    return { value: s, label: s };
                  } else if (typeof s === 'object' && s !== null) {
                    // If symbol is an object, extract the symbol name and use it for both value and label
                    const symbolId = s.symbol || s.name || JSON.stringify(s);
                    const symbolLabel = s.name || s.symbol || JSON.stringify(s);
                    return { value: symbolId, label: symbolLabel };
                  }
                  // Fallback for unexpected types
                  return { value: String(s), label: String(s) };
                })}
                onChange={handleSymbolChange}
                placeholder="Select a symbol"
              />
              <span style={{ marginLeft: '8px', color: 'green', fontSize: '0.8rem' }}>
                {symbols.length} symbols loaded
              </span>
            </>
          ) : (
            <>
              <div>No symbols available</div>
            </>
          )}
        </div>

        <div className="selection-row">
          <label>Timeframe:</label>
          {timeframesLoading ? (
            <>
              <LoadingSpinner size="small" />
              <span style={{ marginLeft: '8px' }}>Loading timeframes...</span>
            </>
          ) : timeframesError ? (
            <>
              <Select
                value={currentTimeframe || ''}
                options={FALLBACK_TIMEFRAMES.map(t => ({ value: t.id, label: t.name }))}
                onChange={handleTimeframeChange}
                placeholder="Select a timeframe"
              />
              <span className="error-note" style={{ fontSize: '0.8rem', color: 'orange', marginLeft: '8px' }}>
                Using fallback data
              </span>
            </>
          ) : timeframes && timeframes.length > 0 ? (
            <>
              <Select
                value={currentTimeframe || ''}
                options={timeframes.map(t => {
                  // Handle both string and object formats for timeframes
                  if (typeof t === 'string') {
                    return { value: t, label: t };
                  } else if (typeof t === 'object' && t !== null) {
                    // If timeframe is an object, extract the id and name
                    const timeframeId = t.id || t.value || String(t);
                    const timeframeLabel = t.name || t.label || String(t);
                    return { value: timeframeId, label: timeframeLabel };
                  }
                  // Fallback for unexpected types
                  return { value: String(t), label: String(t) };
                })}
                onChange={handleTimeframeChange}
                placeholder="Select a timeframe"
              />
              <span style={{ marginLeft: '8px', color: 'green', fontSize: '0.8rem' }}>
                {timeframes.length} timeframes loaded
              </span>
            </>
          ) : (
            <>
              <div>No timeframes available</div>
            </>
          )}
        </div>

        <Button 
          onClick={handleLoadData} 
          disabled={isLoadButtonDisabled}
        >
          {dataLoading ? 'Loading...' : 'Load Data'}
        </Button>
        
        {/* Added reload button for debugging */}
        <div style={{ marginTop: '10px' }}>
          <Button onClick={handleReloadMetadata} size="small" variant="secondary">
            Reload Metadata
          </Button>
          <Button onClick={resetData} size="small" variant="secondary" style={{ marginLeft: '8px' }}>
            Clear Data
          </Button>
        </div>
      </div>

      {dataError && (
        <ErrorMessage message={dataError} />
      )}

      {dataLoading && (
        <div className="loading-container">
          <LoadingSpinner />
          <p>Loading data...</p>
        </div>
      )}

      {ohlcvData && renderDataSummary()}
    </Card>
  );
};

export default DataViewer;