/**
 * SymbolListPage component
 * Displays a list of available trading symbols with filtering options
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSymbolSelection } from './hooks/useSymbolSelection';
import { SymbolInfo } from './types';

// Import common UI components
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';

const SymbolListPage: React.FC = () => {
  const navigate = useNavigate();
  const { 
    symbols, 
    isLoading, 
    error, 
    loadMetadata 
  } = useSymbolSelection();
  
  // Local state for filtering
  const [searchText, setSearchText] = useState('');
  const [filteredSymbols, setFilteredSymbols] = useState<any[]>([]);
  
  // Load symbols data on component mount - with empty dependency array to run only once
  useEffect(() => {
    // We use a reference flag to ensure we only trigger this once
    const triggerFetch = async () => {
      try {
        await loadMetadata();
      } catch (err) {
        console.error('Failed to load symbols on mount:', err);
      }
    };
    
    triggerFetch();
    // Empty dependency array means this only runs once when component mounts
  }, []);
  
  // Filter symbols when search text or symbols array changes
  useEffect(() => {
    if (!symbols?.length) {
      setFilteredSymbols([]);
      return;
    }
    
    if (!searchText) {
      setFilteredSymbols(symbols);
      return;
    }
    
    const filtered = symbols.filter(symbol => {
      const term = searchText.toLowerCase();
      const symbolMatch = symbol.symbol?.toLowerCase().includes(term);
      const nameMatch = symbol.name?.toLowerCase().includes(term);
      return symbolMatch || nameMatch;
    });
    
    setFilteredSymbols(filtered);
  }, [symbols, searchText]);
  
  // Handle symbol selection (navigate to chart)
  const handleSymbolSelect = useCallback((symbol: any) => {
    navigate(`/charts/${symbol.symbol}`);
  }, [navigate]);
  
  // Handle search input changes
  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchText(e.target.value);
  }, []);
  
  // Handle filter resets
  const handleResetFilters = useCallback(() => {
    setSearchText('');
  }, []);
  
  // Handle refresh button click
  const handleRefresh = useCallback(() => {
    loadMetadata().catch(err => {
      console.error('Error refreshing data:', err);
    });
  }, [loadMetadata]);
  
  // Render loading state
  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Symbols</h1>
        <div className="flex justify-center items-center h-64">
          <div className="loading-spinner"></div>
          <span className="ml-2">Loading symbols...</span>
        </div>
      </div>
    );
  }
  
  // Render error state
  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-4">Symbols</h1>
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4" role="alert">
          <p className="font-bold">Error</p>
          <p>{error?.message || 'Failed to load symbols'}</p>
          <button 
            className="mt-2 text-blue-500 hover:text-blue-700" 
            onClick={handleRefresh}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-6">
      <div className="flex flex-wrap items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Symbols</h1>
        <div className="mt-2 sm:mt-0">
          <Button 
            onClick={handleRefresh} 
            variant="outline" 
            size="small"
          >
            Refresh
          </Button>
        </div>
      </div>
      
      {/* Filter section */}
      <Card className="mb-6">
        <div className="p-4">
          <h2 className="text-lg font-semibold mb-4">Filter Symbols</h2>
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[200px]">
              <Input
                id="symbol-search"
                type="text"
                placeholder="Search by symbol or name..."
                value={searchText}
                onChange={handleSearchChange}
                label="Search"
              />
            </div>
            <div className="flex items-end">
              <Button 
                onClick={handleResetFilters} 
                variant="ghost" 
                size="medium"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </div>
      </Card>
      
      {/* Results count */}
      <div className="mb-4 text-sm text-gray-500">
        Showing {filteredSymbols.length} symbols
      </div>
      
      {/* Symbol list */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100 dark:bg-gray-800">
              <th className="text-left p-3 border-b">Symbol</th>
              <th className="text-left p-3 border-b">Name</th>
              <th className="text-left p-3 border-b">Exchange</th>
              <th className="text-left p-3 border-b">Type</th>
              <th className="text-left p-3 border-b">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredSymbols.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-4 text-center text-gray-500">
                  No symbols found matching your filters.
                </td>
              </tr>
            ) : (
              filteredSymbols.map((symbol) => (
                <tr key={symbol.symbol} className="border-b hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="p-3 font-medium">{symbol.symbol}</td>
                  <td className="p-3">{symbol.name || '-'}</td>
                  <td className="p-3">{symbol.exchange || '-'}</td>
                  <td className="p-3">{symbol.type || '-'}</td>
                  <td className="p-3">
                    <Button
                      onClick={() => handleSymbolSelect(symbol)}
                      variant="primary"
                      size="small"
                    >
                      View Chart
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SymbolListPage;