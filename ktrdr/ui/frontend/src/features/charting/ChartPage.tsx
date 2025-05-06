import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useOHLCVData } from '../../api/hooks/useData';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { ErrorMessage } from '../../components/common/ErrorMessage';
import ChartPanel from './ChartPanel';

/**
 * ChartPage component for displaying OHLCV chart for a selected symbol
 * This page fetches data from the API and passes it to the ChartPanel component
 */
const ChartPage: React.FC = () => {
  // Get the symbol from the URL parameters
  const { symbol } = useParams<{ symbol: string }>();
  const [timeframe, setTimeframe] = useState<string>('1d'); // Default to daily timeframe

  // Fetch OHLCV data using the existing hook
  const { data, isLoading, error } = useOHLCVData(
    symbol ? { 
      symbol,
      timeframe,
      startDate: undefined, // Optional: could add date picker controls later
      endDate: undefined
    } : null
  );

  // If symbol is undefined, show error
  if (!symbol) {
    return (
      <div className="p-4">
        <ErrorMessage message="No symbol specified. Please select a symbol." />
      </div>
    );
  }

  return (
    <div className="chart-page-container">
      <div className="chart-header flex justify-between items-center p-4 border-b">
        <h1 className="text-xl font-semibold">
          {symbol} - {timeframe} Chart
        </h1>
        <div className="chart-controls flex gap-2">
          <select 
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-gray-700 text-white px-3 py-1 rounded"
          >
            <option value="1m">1 Minute</option>
            <option value="5m">5 Minutes</option>
            <option value="15m">15 Minutes</option>
            <option value="1h">1 Hour</option>
            <option value="4h">4 Hours</option>
            <option value="1d">1 Day</option>
          </select>
        </div>
      </div>

      <div className="chart-content p-4">
        {isLoading && (
          <div className="flex justify-center items-center h-96">
            <LoadingSpinner message="Loading chart data..." />
          </div>
        )}
        
        {error && (
          <ErrorMessage 
            message={`Error loading chart data: ${error.message}`} 
          />
        )}
        
        {!isLoading && !error && data && (
          <ChartPanel 
            data={data} 
            symbol={symbol} 
            timeframe={timeframe}
          />
        )}
      </div>
    </div>
  );
};

export default ChartPage;