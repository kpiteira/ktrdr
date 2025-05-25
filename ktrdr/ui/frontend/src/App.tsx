import { FC, useState } from 'react';
import BasicChart, { SMAData } from './components/BasicChart';
import RSIChart, { RSIData } from './components/RSIChart';
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
  const [rsiToAdd, setRsiToAdd] = useState<number | null>(null);
  const [rsiToRemove, setRsiToRemove] = useState<string | null>(null);
  const [rsiToToggle, setRsiToToggle] = useState<string | null>(null);
  const [rsiLoading, setRsiLoading] = useState(false);
  const [rsiList, setRsiList] = useState<RSIData[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [dateRange, setDateRange] = useState<{start: string, end: string} | null>(null);

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
    } else if (type === 'RSI') {
      setRsiLoading(true);
      setRsiToAdd(period);
    }
  };

  const handleSMAAdded = () => {
    console.log('[App] SMA added successfully');
    setSmaLoading(false);
    setSmaToAdd(null);
  };

  const handleRemoveIndicator = (id: string) => {
    console.log('[App] Removing indicator:', id);
    if (id.startsWith('SMA_')) {
      setSmaToRemove(id);
    } else if (id.startsWith('RSI_')) {
      setRsiToRemove(id);
    }
  };

  const handleSMARemoved = () => {
    console.log('[App] SMA removed successfully');
    setSmaToRemove(null);
  };

  const handleRSIAdded = () => {
    console.log('[App] RSI added successfully');
    setRsiLoading(false);
    setRsiToAdd(null);
  };

  const handleRSIRemoved = () => {
    console.log('[App] RSI removed successfully');
    setRsiToRemove(null);
  };

  const handleToggleIndicator = (id: string) => {
    console.log('[App] Toggling indicator:', id);
    if (id.startsWith('SMA_')) {
      setSmaToToggle(id);
    } else if (id.startsWith('RSI_')) {
      setRsiToToggle(id);
    }
  };

  const handleSMAToggled = () => {
    console.log('[App] SMA toggled successfully');
    setSmaToToggle(null);
  };

  const handleRSIToggled = () => {
    console.log('[App] RSI toggled successfully');
    setRsiToToggle(null);
  };

  const handleSMAListChange = (newSmaList: SMAData[]) => {
    setSmaList(newSmaList);
  };

  const handleRSIListChange = (newRsiList: RSIData[]) => {
    setRsiList(newRsiList);
  };

  const handleDateRangeChange = (newDateRange: {start: string, end: string} | null) => {
    setDateRange(newDateRange);
  };

  const handleUpdateIndicator = (id: string, updates: Partial<{ id: string; type: string; period: number; color: string; visible: boolean; }>) => {
    console.log('[App] Updating indicator:', id, updates);
    
    if (id.startsWith('SMA_')) {
      // Update SMA indicator
      setSmaList(prev => prev.map(sma => 
        sma.id === id ? { ...sma, ...updates } : sma
      ));
    } else if (id.startsWith('RSI_')) {
      // Update RSI indicator
      setRsiList(prev => prev.map(rsi => 
        rsi.id === id ? { ...rsi, ...updates } : rsi
      ));
    }
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
            <h1 style={{ margin: 0, fontSize: '1.25rem' }}>KTRDR Trading Research - MVP Slice 5</h1>
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
            indicators={[
              ...smaList.map(sma => ({
                id: sma.id,
                type: 'SMA',
                period: sma.period,
                color: sma.color,
                visible: sma.visible
              })),
              ...rsiList.map(rsi => ({
                id: rsi.id,
                type: 'RSI',
                period: rsi.period,
                color: rsi.color,
                visible: rsi.visible
              }))
            ]}
            onAddIndicator={handleAddIndicator}
            onRemoveIndicator={handleRemoveIndicator}
            onToggleIndicator={handleToggleIndicator}
            onUpdateIndicator={handleUpdateIndicator}
            isCollapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            isLoading={smaLoading || rsiLoading}
          />
          
          {/* Chart Area */}
          <div style={{ 
            flex: 1, 
            padding: '1rem',
            overflow: 'auto',
            backgroundColor: '#fafafa',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Main Price Chart */}
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
                onDateRangeChange={handleDateRangeChange}
                smaList={smaList}
                width={sidebarCollapsed ? 920 : 800}
                height={400}
              />
            </ErrorBoundary>

            {/* RSI Oscillator Chart */}
            <ErrorBoundary>
              <RSIChart
                symbol={selectedSymbol}
                timeframe={selectedTimeframe}
                rsiToAdd={rsiToAdd}
                onRSIAdded={handleRSIAdded}
                rsiToRemove={rsiToRemove}
                onRSIRemoved={handleRSIRemoved}
                rsiToToggle={rsiToToggle}
                onRSIToggled={handleRSIToggled}
                onRSIListChange={handleRSIListChange}
                dateRange={dateRange}
                rsiList={rsiList}
                width={sidebarCollapsed ? 920 : 800}
                height={200}
              />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;