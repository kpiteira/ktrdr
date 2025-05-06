import React, { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { Card } from '../../components/common';
import CandlestickChart from './CandlestickChart';
import { OHLCVData } from '../../types/data';
import { useOHLCVData } from '../../api/hooks/useData';

/**
 * ChartPage displays trading charts with indicators
 * Handles loading OHLCV data for a selected symbol
 */
const ChartPage: React.FC = () => {
  // Extract symbol from URL params
  const { symbol } = useParams<{ symbol: string }>();
  
  // Define data load parameters for the hook
  const dataParams = useMemo(() => {
    if (!symbol) return null;
    
    return {
      symbol,
      timeframe: '1d', // Default to 1d timeframe
      start: undefined, // Use default server-side range
      end: undefined,   // Use default server-side range
    };
  }, [symbol]);
  
  // Fetch OHLCV data using the API hook
  const { data, isLoading, error } = useOHLCVData(dataParams);
  
  // Handle loading state
  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500" role="status"></div>
      </div>
    );
  }
  
  // Handle error state
  if (error) {
    return (
      <div className="p-4">
        <Card>
          <div className="text-red-500 font-semibold text-lg mb-2">Error loading chart data</div>
          <div className="text-sm text-gray-500">{error.message}</div>
          <div className="mt-4 text-sm">
            <span className="text-gray-500">Symbol: </span>
            <span className="font-medium">{symbol || 'Not specified'}</span>
          </div>
        </Card>
      </div>
    );
  }
  
  return (
    <div className="chart-page p-4">
      <h1 className="text-2xl font-bold mb-4">
        {symbol ? `Chart: ${symbol}` : 'Chart'}
      </h1>
      
      <Card>
        {!symbol ? (
          <div className="p-4">
            <p>Select a symbol from the symbols list to view its chart.</p>
          </div>
        ) : (
          <div className="p-4">
            <div style={{ height: '400px' }}>
              <CandlestickChart 
                data={data as OHLCVData}
                height={400}
                showVolume={true}
                title={`${symbol} Chart`}
              />
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default ChartPage;