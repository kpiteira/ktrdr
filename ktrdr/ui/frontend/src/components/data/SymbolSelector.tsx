import React, { useEffect, useState } from 'react';
import { useDataSelection } from '../../hooks';
import { LoadingSpinner, ErrorMessage, Select } from '../common';

interface SymbolSelectorProps {
  className?: string;
  disabled?: boolean;
  onSymbolChange?: (symbol: string) => void;
}

// Define potential symbol object structure
interface SymbolObject {
  symbol?: string;
  name?: string;
  [key: string]: any; // Allow other properties
}

// Type for symbol which can be string or object
type SymbolType = string | SymbolObject;

export const SymbolSelector: React.FC<SymbolSelectorProps> = ({
  className = '',
  disabled = false,
  onSymbolChange
}) => {
  const {
    symbols,
    currentSymbol,
    selectSymbol
  } = useDataSelection();

  const [isLoading, setIsLoading] = useState(true);

  // Monitor loading state
  useEffect(() => {
    // If symbols loaded or there's been enough time, clear loading state
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 2000); // 2 second timeout

    // If symbols load successfully, clear loading state
    if (symbols) {
      setIsLoading(false);
      clearTimeout(timer);
    }

    return () => clearTimeout(timer);
  }, [symbols]);

  // Handle symbol selection
  const handleChange = (value: string) => {
    selectSymbol(value);
    if (onSymbolChange) {
      onSymbolChange(value);
    }
  };

  // If still loading, show spinner
  if (isLoading) {
    return <LoadingSpinner size="small" />;
  }

  // If API error / no symbols received
  if (!symbols) {
    return (
      <ErrorMessage 
        message="Failed to load symbols from API" 
        details="Please check your backend connection and reload the page." 
      />
    );
  }

  // Check if we have valid symbols to display
  if (!Array.isArray(symbols) || symbols.length === 0) {
    return <ErrorMessage message="No symbols available" />;
  }

  return (
    <div className={`symbol-selector ${className}`}>
      <Select
        id="symbol-select"
        label="Symbol"
        value={currentSymbol || ''}
        options={symbols.map((s: SymbolType) => {
          // Handle both string and object formats for symbols
          if (typeof s === 'string') {
            return { value: s, label: s };
          } else if (typeof s === 'object' && s !== null) {
            const symbolObj = s as SymbolObject;
            const symbolId = symbolObj.symbol || symbolObj.name || JSON.stringify(s);
            const symbolLabel = symbolObj.name || symbolObj.symbol || JSON.stringify(s);
            return { value: symbolId, label: symbolLabel };
          }
          // Fallback for unexpected types
          return { value: String(s), label: String(s) };
        })}
        onChange={handleChange}
        placeholder="Select a symbol"
        disabled={disabled}
      />
    </div>
  );
};

export default SymbolSelector;