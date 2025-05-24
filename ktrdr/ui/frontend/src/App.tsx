import { FC, useState } from 'react';
import BasicChart from './components/BasicChart';
import SymbolSelector from './components/SymbolSelector';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

const App: FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('MSFT');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h');

  const handleSymbolChange = (symbol: string, timeframe: string) => {
    console.log('[App] handleSymbolChange called:', { symbol, timeframe });
    
    // Ensure we always have a valid timeframe
    let actualTimeframe = timeframe;
    if (!timeframe || timeframe === 'undefined' || timeframe === undefined || timeframe === '') {
      if (symbol === 'AAPL') {
        actualTimeframe = '1d';
      } else if (symbol === 'MSFT') {
        actualTimeframe = '1h';
      } else {
        actualTimeframe = '1h'; // default
      }
      console.log('[App] Fixed undefined/invalid timeframe to:', actualTimeframe);
    }
    
    console.log('[App] Setting state with:', { symbol, timeframe: actualTimeframe });
    
    // Update both states in a single batch
    setSelectedSymbol(symbol);
    setSelectedTimeframe(actualTimeframe);
    
    console.log('[App] State update completed for:', { symbol, timeframe: actualTimeframe });
  };

  return (
    <ErrorBoundary>
      <div className="App">
        <header className="App-header">
          <h1>KTRDR Trading Research - MVP Slice 2</h1>
        </header>
        <main className="App-main">
          <div style={{ marginBottom: '1rem' }}>
            <SymbolSelector 
              selectedSymbol={selectedSymbol}
              onSymbolChange={handleSymbolChange}
            />
          </div>
          <ErrorBoundary>
            <BasicChart symbol={selectedSymbol} timeframe={selectedTimeframe} />
          </ErrorBoundary>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;