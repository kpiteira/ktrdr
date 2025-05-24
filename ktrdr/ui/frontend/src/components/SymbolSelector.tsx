import { FC, useEffect, useState } from 'react';

interface Symbol {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
  available_timeframes: string[];
}

interface SymbolSelectorProps {
  selectedSymbol: string;
  onSymbolChange: (symbol: string, timeframe: string) => void;
}

const SymbolSelector: FC<SymbolSelectorProps> = ({ selectedSymbol, onSymbolChange }) => {
  console.log('[SymbolSelector] Component render with props:', { selectedSymbol });
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

      const response = await fetch('/api/v1/symbols');
      const data = await response.json();

      if (!data.success || !data.data) {
        throw new Error('Failed to fetch symbols');
      }

      console.log('[SymbolSelector] Fetched symbols:', data.data);
      setSymbols(data.data);
      setLoading(false);
    } catch (err) {
      console.error('[SymbolSelector] Error fetching symbols:', err);
      setError(err instanceof Error ? err.message : 'Failed to load symbols');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <label htmlFor="symbol-select">Symbol:</label>
        <select disabled style={{ padding: '0.5rem', minWidth: '120px' }}>
          <option>Loading...</option>
        </select>
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

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <label htmlFor="symbol-select">Symbol:</label>
      <select
        id="symbol-select"
        value={selectedSymbol}
        onChange={(e) => {
          console.log('[SymbolSelector] onChange fired with value:', e.target.value);
          const symbol = e.target.value;
          const symbolData = symbols.find(s => s.symbol === symbol);
          console.log('[SymbolSelector] Symbol change debug:', { 
            symbol, 
            symbolData, 
            available_timeframes: symbolData?.available_timeframes,
            allSymbols: symbols 
          });
          
          // More robust timeframe selection
          let timeframe = '1h'; // Default fallback
          if (symbolData && symbolData.available_timeframes && symbolData.available_timeframes.length > 0) {
            timeframe = symbolData.available_timeframes[0];
          } else if (symbol === 'AAPL') {
            timeframe = '1d'; // Known timeframe for AAPL
          } else if (symbol === 'MSFT') {
            timeframe = '1h'; // Known timeframe for MSFT
          }
          
          console.log('[SymbolSelector] Final timeframe selected:', timeframe);
          onSymbolChange(symbol, timeframe);
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
            {symbol.symbol} - {symbol.name} ({symbol.available_timeframes.join(', ')})
          </option>
        ))}
      </select>
      <span style={{ fontSize: '0.8rem', color: '#666' }}>
        ({symbols.length} available)
      </span>
    </div>
  );
};

export default SymbolSelector;