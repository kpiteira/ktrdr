import { FC, useEffect, useState } from 'react';
import LoadingSpinner from './common/LoadingSpinner';
import { MarketStatusIndicator } from './presentation/indicators/MarketStatusIndicator';
import { createLogger } from '../utils/logger';
import type { SymbolInfo } from '../api/types';

const logger = createLogger('SymbolSelector');

interface SymbolSelectorProps {
  selectedSymbol: string;
  onSymbolChange: (symbol: string, timeframe: string, symbolData?: SymbolInfo) => void;
}

interface Symbol extends SymbolInfo {
  // Extend SymbolInfo with any additional properties if needed
}

const SymbolSelector: FC<SymbolSelectorProps> = ({ selectedSymbol, onSymbolChange }) => {
  const [symbols, setSymbols] = useState<Symbol[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSymbols();
  }, []);

  const fetchSymbols = async () => {
    try {
      setLoading(true);
      setError(null);

      logger.info('🔄 Fetching symbols from /api/v1/symbols...');
      const response = await fetch('/api/v1/symbols');
      
      logger.info('📡 Symbols API response:', {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        url: response.url
      });

      if (!response.ok) {
        const errorText = await response.text();
        logger.error('❌ Symbols API HTTP error:', {
          status: response.status,
          statusText: response.statusText,
          errorBody: errorText
        });
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      logger.info('📋 Symbols API response data:', data);

      if (!data.success || !data.data) {
        logger.error('❌ Invalid symbols API response format:', data);
        throw new Error('Failed to fetch symbols - invalid response format');
      }

      logger.info('✅ Successfully loaded symbols:', {
        count: data.data.length,
        symbols: data.data.map((s: any) => s.symbol || s)
      });

      setSymbols(data.data);
      setLoading(false);
      
      // If we have a selected symbol, notify the parent with the symbol data
      if (selectedSymbol) {
        const symbolData = data.data.find((s: any) => s.symbol === selectedSymbol);
        if (symbolData) {
          // Determine timeframe
          let timeframe = '1h'; // Default fallback
          if (symbolData.available_timeframes && symbolData.available_timeframes.length > 0) {
            timeframe = symbolData.available_timeframes[0];
          } else if (selectedSymbol === 'AAPL') {
            timeframe = '1d';
          } else if (selectedSymbol === 'MSFT') {
            timeframe = '1h';
          }
          
          // Notify parent with current selection
          onSymbolChange(selectedSymbol, timeframe, symbolData);
        }
      }
    } catch (err) {
      logger.error('❌ Failed to fetch available symbols:', err);
      setError(err instanceof Error ? err.message : 'Failed to load symbols');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <label htmlFor="symbol-select">Symbol:</label>
        <div style={{ 
          padding: '0.5rem', 
          minWidth: '120px',
          border: '1px solid #ddd',
          borderRadius: '4px',
          backgroundColor: '#f9f9f9',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <LoadingSpinner 
            size="small" 
            message="Loading..." 
            inline={true}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <label htmlFor="symbol-select">Symbol:</label>
        <select disabled style={{ padding: '0.5rem', minWidth: '120px' }}>
          <option>Error loading symbols</option>
        </select>
        <button 
          onClick={fetchSymbols}
          style={{
            padding: '0.25rem 0.5rem',
            fontSize: '0.8rem',
            backgroundColor: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '3px',
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const selectedSymbolData = symbols.find(s => s.symbol === selectedSymbol);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <label htmlFor="symbol-select">Symbol:</label>
      <select
        id="symbol-select"
        value={selectedSymbol}
        onChange={(e) => {
          const symbol = e.target.value;
          const symbolData = symbols.find(s => s.symbol === symbol);
          
          // More robust timeframe selection
          let timeframe = '1h'; // Default fallback
          if (symbolData && symbolData.available_timeframes && symbolData.available_timeframes.length > 0) {
            timeframe = symbolData.available_timeframes[0];
          } else if (symbol === 'AAPL') {
            timeframe = '1d'; // Known timeframe for AAPL
          } else if (symbol === 'MSFT') {
            timeframe = '1h'; // Known timeframe for MSFT
          }
          
          onSymbolChange(symbol, timeframe, symbolData);
        }}
        style={{
          padding: '0.5rem',
          minWidth: '120px',
          borderRadius: '4px',
          border: '1px solid #ccc',
          fontSize: '1rem'
        }}
      >
        {symbols.map((symbol) => (
          <option key={symbol.symbol} value={symbol.symbol}>
            {symbol.symbol} - {symbol.name} ({symbol.available_timeframes?.join(', ') || 'N/A'})
          </option>
        ))}
      </select>
      
      {/* Market Status Indicator */}
      {selectedSymbolData && (
        <MarketStatusIndicator 
          symbol={selectedSymbolData} 
          showDetails={false}
          className="ml-2"
        />
      )}
      
      <span style={{ fontSize: '0.8rem', color: '#666' }}>
        ({symbols.length} available)
        {selectedSymbolData?.exchange && (
          <span className="ml-2 text-xs text-gray-500">
            {selectedSymbolData.exchange}
          </span>
        )}
      </span>
    </div>
  );
};

export default SymbolSelector;