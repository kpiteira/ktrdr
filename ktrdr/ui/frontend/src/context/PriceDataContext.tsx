import React, { createContext, useContext, ReactNode } from 'react';
import { useSharedPriceData } from '../hooks/useSharedPriceData';
import { CandlestickData } from 'lightweight-charts';

/**
 * Price Data Context for sharing price data across chart containers
 * 
 * This context eliminates the need for multiple containers to load the same
 * price data, improving performance and consistency.
 */

interface PriceDataContextType {
  priceData: CandlestickData[];
  isLoading: boolean;
  error: string | null;
  loadPriceData: (symbol: string, timeframe: string) => Promise<void>;
  getCurrentSymbol: () => string;
  getCurrentTimeframe: () => string;
}

const PriceDataContext = createContext<PriceDataContextType | undefined>(undefined);

interface PriceDataProviderProps {
  children: ReactNode;
}

export const PriceDataProvider: React.FC<PriceDataProviderProps> = ({ children }) => {
  const sharedPriceData = useSharedPriceData();

  return (
    <PriceDataContext.Provider value={sharedPriceData}>
      {children}
    </PriceDataContext.Provider>
  );
};

export const usePriceDataContext = (): PriceDataContextType => {
  const context = useContext(PriceDataContext);
  if (context === undefined) {
    throw new Error('usePriceDataContext must be used within a PriceDataProvider');
  }
  return context;
};