/**
 * Example DataViewer component
 * Demonstrates how to use the API client and data hooks
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Card, 
  Select, 
  Button, 
  LoadingSpinner, 
  ErrorMessage 
} from '../components/common';
import { apiClient } from '../api';
import { config } from '../config';

// Define proper TypeScript interfaces for better type safety
interface OHLCVDataParams {
  symbol: string;
  timeframe: string;
  startDate?: string;
  endDate?: string;
}

interface OHLCVPoint {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface OHLCVData {
  dates: string[];
  ohlcv: number[][];
  metadata: {
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    point_count: number;
  };
}

// Custom hook implementation with proper typing
const useOHLCVData = (params: OHLCVDataParams | null) => {
  const [data, setData] = useState<OHLCVData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  
  useEffect(() => {
    // Reset state if params are null
    if (!params) {
      return;
    }
    
    const fetchData = async () => {
      try {
        setIsLoading(true);
        console.log("📊 API call initiated with params:", params);
        
        // Call the API client to get OHLCV data
        const response = await apiClient.post('data/load', {
          symbol: params.symbol,
          timeframe: params.timeframe,
          start_date: params.startDate,
          end_date: params.endDate
        });
        
        setData(response);
        setError(null);
      } catch (err) {
        console.error("📊 API call failed:", err);
        setError(err instanceof Error ? err : new Error('Unknown error occurred'));
        setData(null);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchData();
  }, [params?.symbol, params?.timeframe, params?.startDate, params?.endDate]);
  
  return { data, isLoading, error };
};

// Timeframes fallback data when the API fails
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

// Helper to get stored data from sessionStorage with typed return value
const getStoredItem = <T,>(key: string): T | null => {
  try {
    const stored = sessionStorage.getItem(key);
    return stored ? JSON.parse(stored) : null;
  } catch (e) {
    console.error(`Error retrieving stored ${key}`, e);
    return null;
  }
};

/**
 * DataViewer component demonstrates the API integration
 * This shows how to load symbols, timeframes, and OHLCV data
 */
const DataViewer: React.FC = () => {
  // Simple flag to show that component is initialized
  const isInitialized = useRef<boolean>(false);
  
  // State for selected values
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<string | null>(null);
  const [dataParams, setDataParams] = useState<OHLCVDataParams | null>(null);
  
  // Initialize with stored values if available
  const [symbols, setSymbols] = useState<any[] | null>(getStoredItem('ktrdr_symbols'));
  const [symbolsLoading, setSymbolsLoading] = useState<boolean>(!getStoredItem('ktrdr_symbols'));
  const [symbolsError, setSymbolsError] = useState<Error | null>(null);
  
  const [timeframes, setTimeframes] = useState<any[] | null>(getStoredItem('ktrdr_timeframes'));
  const [timeframesLoading, setTimeframesLoading] = useState<boolean>(!getStoredItem('ktrdr_timeframes'));
  const [timeframesError, setTimeframesError] = useState<Error | null>(null);
  
  // Load symbols only once
  useEffect(() => {
    // If already initialized or we have stored data, don't fetch again
    if (isInitialized.current || getStoredItem('ktrdr_symbols')) {
      setSymbolsLoading(false);
      return;
    }
    
    const controller = new AbortController();
    
    const loadSymbols = async () => {
      try {
        // Request symbols from API
        const response = await apiClient.get('symbols', undefined, { 
          signal: controller.signal,
          cacheTtl: 60000 // Cache for 1 minute
        });
        
        // Store data and update state
        if (response && Array.isArray(response)) {
          // Store in sessionStorage for persistence across renders
          sessionStorage.setItem('ktrdr_symbols', JSON.stringify(response));
          setSymbols(response);
        }
        
        // Update loading state
        setSymbolsLoading(false);
        
      } catch (error) {
        console.error("Error loading symbols:", error);
        setSymbolsError(error instanceof Error ? error : new Error('Unknown error'));
        setSymbolsLoading(false);
      }
    };
    
    loadSymbols();
    isInitialized.current = true;
    
    return () => {
      controller.abort();
    };
  }, []);
  
  // Load timeframes only once
  useEffect(() => {
    // If we have stored data, don't fetch again
    if (getStoredItem('ktrdr_timeframes')) {
      setTimeframesLoading(false);
      return;
    }
    
    const controller = new AbortController();
    
    const loadTimeframes = async () => {
      try {
        // Request timeframes from API
        const response = await apiClient.get('timeframes', undefined, { 
          signal: controller.signal,
          cacheTtl: 60000 // Cache for 1 minute
        });
        
        // Store data and update state
        if (response && Array.isArray(response)) {
          // Store in sessionStorage for persistence across renders
          sessionStorage.setItem('ktrdr_timeframes', JSON.stringify(response));
          setTimeframes(response);
        }
        
        // Update loading state
        setTimeframesLoading(false);
        
      } catch (error) {
        console.error("Error loading timeframes:", error);
        setTimeframesError(error instanceof Error ? error : new Error('Unknown error'));
        
        // Use fallback timeframes data if API fails
        const fallback = FALLBACK_TIMEFRAMES;
        sessionStorage.setItem('ktrdr_timeframes', JSON.stringify(fallback));
        setTimeframes(fallback);
        
        setTimeframesLoading(false);
      }
    };
    
    loadTimeframes();
    
    return () => {
      controller.abort();
    };
  }, []);

  // Only load OHLCV data when both symbol and timeframe are selected and button is clicked
  const { 
    data: ohlcvData, 
    isLoading: dataLoading, 
    error: dataError 
  } = useOHLCVData(dataParams);

  // Handle load data button click
  const handleLoadData = () => {
    if (selectedSymbol && selectedTimeframe) {
      setDataParams({
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        startDate: '2023-01-01',
        endDate: '2023-04-01'
      });
    }
  };

  // Manual reload functions that clear session storage
  const handleReloadSymbols = () => {
    sessionStorage.removeItem('ktrdr_symbols');
    setSymbolsLoading(true);
    
    const loadSymbols = async () => {
      try {
        const response = await apiClient.get('symbols', undefined, { 
          cacheTtl: 0 // Don't cache this request
        });
        
        if (response && Array.isArray(response)) {
          sessionStorage.setItem('ktrdr_symbols', JSON.stringify(response));
          setSymbols(response);
        }
        setSymbolsLoading(false);
      } catch (error) {
        console.error("Error reloading symbols:", error);
        setSymbolsError(error instanceof Error ? error : new Error('Unknown error'));
        setSymbolsLoading(false);
      }
    };
    
    loadSymbols();
  };
  
  const handleReloadTimeframes = () => {
    sessionStorage.removeItem('ktrdr_timeframes');
    setTimeframesLoading(true);
    
    const loadTimeframes = async () => {
      try {
        const response = await apiClient.get('timeframes', undefined, { 
          cacheTtl: 0 // Don't cache this request
        });
        
        if (response && Array.isArray(response)) {
          sessionStorage.setItem('ktrdr_timeframes', JSON.stringify(response));
          setTimeframes(response);
        }
        setTimeframesLoading(false);
      } catch (error) {
        console.error("Error reloading timeframes:", error);
        setTimeframesError(error instanceof Error ? error : new Error('Unknown error'));
        const fallback = FALLBACK_TIMEFRAMES;
        sessionStorage.setItem('ktrdr_timeframes', JSON.stringify(fallback));
        setTimeframes(fallback);
        setTimeframesLoading(false);
      }
    };
    
    loadTimeframes();
  };

  // Set symbol handler
  const handleSymbolChange = (value: string) => {
    setSelectedSymbol(value);
  };
  
  // Set timeframe handler
  const handleTimeframeChange = (value: string) => {
    setSelectedTimeframe(value);
  };

  // Determine if the load button should be disabled
  const isLoadButtonDisabled = !selectedSymbol || !selectedTimeframe || dataLoading;

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
        <p>Date Range: {metadata.start_date} to {metadata.end_date}</p>
        <p>Total Points: {metadata.point_count}</p>
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
    <Card title="Data Viewer Example">
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
              <ErrorMessage message={symbolsError.message || "Failed to load symbols"} />
            </>
          ) : symbols && symbols.length > 0 ? (
            <>
              <Select
                value={selectedSymbol || ''}
                options={symbols.map(s => ({ value: s.symbol, label: s.name || s.symbol }))}
                onChange={handleSymbolChange}
                placeholder="Select a symbol"
              />
              <span style={{ marginLeft: '8px', color: 'green', fontSize: '0.8rem' }}>
                {symbols.length} symbols loaded
              </span>
            </>
          ) : (
            <>
              <div>No symbols available (but API call completed)</div>
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
                value={selectedTimeframe || ''}
                options={timeframes?.map(t => ({ value: t.id, label: t.name })) || []}
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
                value={selectedTimeframe || ''}
                options={timeframes.map(t => ({ value: t.id, label: t.name }))}
                onChange={handleTimeframeChange}
                placeholder="Select a timeframe"
              />
              <span style={{ marginLeft: '8px', color: 'green', fontSize: '0.8rem' }}>
                {timeframes.length} timeframes loaded
              </span>
            </>
          ) : (
            <>
              <div>No timeframes available (but API call completed)</div>
            </>
          )}
        </div>

        <Button 
          onClick={handleLoadData} 
          disabled={isLoadButtonDisabled}
        >
          {dataLoading ? 'Loading...' : 'Load Data'}
        </Button>
        
        {/* Added reload buttons for debugging */}
        <div style={{ marginTop: '10px' }}>
          <Button onClick={handleReloadSymbols} size="small" variant="secondary">
            Reload Symbols
          </Button>
          <Button onClick={handleReloadTimeframes} size="small" variant="secondary" style={{ marginLeft: '8px' }}>
            Reload Timeframes
          </Button>
        </div>
      </div>

      {dataError && (
        <ErrorMessage message={dataError.message} />
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