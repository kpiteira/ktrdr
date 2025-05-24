import { FC, useState } from 'react';
import BasicChart, { SMAData } from './components/BasicChart';
import SymbolSelector from './components/SymbolSelector';
import IndicatorSidebar from './components/IndicatorSidebar';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';

const App: FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('MSFT');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h');
  const [smaToAdd, setSmaToAdd] = useState<number | null>(null);
  const [smaToRemove, setSmaToRemove] = useState<string | null>(null);
  const [smaToToggle, setSmaToToggle] = useState<string | null>(null);
  const [smaLoading, setSmaLoading] = useState(false);
  const [smaList, setSmaList] = useState<SMAData[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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

  const handleAddIndicator = (type: string, period: number) => {
    console.log('[App] Adding indicator:', { type, period });
    if (type === 'SMA') {
      setSmaLoading(true);
      setSmaToAdd(period);
    }
  };

  const handleSMAAdded = () => {
    console.log('[App] SMA added successfully');
    setSmaLoading(false);
    setSmaToAdd(null);
  };

  const handleRemoveIndicator = (id: string) => {
    console.log('[App] Removing indicator:', id);
    setSmaToRemove(id);
  };

  const handleSMARemoved = () => {
    console.log('[App] SMA removed successfully');
    setSmaToRemove(null);
  };

  const handleToggleIndicator = (id: string) => {
    console.log('[App] Toggling indicator:', id);
    setSmaToToggle(id);
  };

  const handleSMAToggled = () => {
    console.log('[App] SMA toggled successfully');
    setSmaToToggle(null);
  };

  const handleSMAListChange = (newSmaList: SMAData[]) => {
    setSmaList(newSmaList);
  };

  return (
    <ErrorBoundary>
      <div className="App" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        <header className="App-header" style={{ 
          padding: '0.75rem 1rem', 
          backgroundColor: '#1976d2', 
          color: 'white',
          borderBottom: '1px solid #e0e0e0',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 style={{ margin: 0, fontSize: '1.25rem' }}>KTRDR Trading Research - MVP Slice 4</h1>
            <SymbolSelector 
              selectedSymbol={selectedSymbol}
              onSymbolChange={handleSymbolChange}
            />
          </div>
        </header>
        
        <main style={{ 
          display: 'flex', 
          height: 'calc(100vh - 60px)', 
          overflow: 'hidden'
        }}>
          {/* Indicator Sidebar */}
          <IndicatorSidebar
            indicators={smaList.map(sma => ({
              id: sma.id,
              type: 'SMA',
              period: sma.period,
              color: sma.color,
              visible: sma.visible
            }))}
            onAddIndicator={handleAddIndicator}
            onRemoveIndicator={handleRemoveIndicator}
            onToggleIndicator={handleToggleIndicator}
            isCollapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            isLoading={smaLoading}
          />
          
          {/* Chart Area */}
          <div style={{ 
            flex: 1, 
            padding: '1rem',
            overflow: 'auto',
            backgroundColor: '#fafafa'
          }}>
            <ErrorBoundary>
              <BasicChart 
                symbol={selectedSymbol} 
                timeframe={selectedTimeframe}
                smaToAdd={smaToAdd}
                onSMAAdded={handleSMAAdded}
                smaToRemove={smaToRemove}
                onSMARemoved={handleSMARemoved}
                smaToToggle={smaToToggle}
                onSMAToggled={handleSMAToggled}
                onSMAListChange={handleSMAListChange}
                width={sidebarCollapsed ? 920 : 800}
                height={500}
              />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;