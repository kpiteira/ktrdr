import React, { FC, useState, useCallback } from 'react';
import { useChartSynchronizer } from './hooks/useChartSynchronizer';
import IndicatorSidebarContainer from './components/containers/IndicatorSidebarContainer';
import BasicChartContainer from './components/containers/BasicChartContainer';
import RSIChartContainer from './components/containers/RSIChartContainer';
import SymbolSelector from './components/SymbolSelector';
import ErrorBoundary from './components/ErrorBoundary';
import { IndicatorInfo } from './store/indicatorRegistry';
import './App.css';

/**
 * Main application component using Container/Presentation architecture
 * 
 * This component orchestrates the overall application state and coordinates
 * between the different container components. It uses the chart synchronizer
 * to keep charts in sync and manages the global application state.
 */

const App: FC = () => {
  // Core application state
  const [selectedSymbol, setSelectedSymbol] = useState('MSFT');
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Chart synchronization
  const chartSynchronizer = useChartSynchronizer();
  
  // Time range synchronization between charts
  const [timeRange, setTimeRange] = useState<{ start: string; end: string } | null>(null);
  
  // Indicator state for coordination between sidebar and charts
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([]);

  // Handle symbol changes from the symbol selector
  const handleSymbolChange = useCallback((symbol: string, timeframe: string) => {
    console.log('[App] Symbol change requested:', { symbol, timeframe });
    
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
    
    console.log('[App] Setting new symbol and timeframe:', { symbol, timeframe: actualTimeframe });
    
    // Update state
    setSelectedSymbol(symbol);
    setSelectedTimeframe(actualTimeframe);
    
    // Clear time range when symbol changes
    setTimeRange(null);
    
    console.log('[App] Symbol change completed');
  }, []);

  // Handle time range changes from the main chart
  const handleTimeRangeChange = useCallback((range: { start: string; end: string }) => {
    console.log('[App] Time range changed:', range);
    setTimeRange(range);
  }, []);

  // Handle indicator addition from the sidebar
  const handleIndicatorAdded = useCallback((indicator: IndicatorInfo) => {
    console.log('[App] Indicator added:', indicator);
    setIndicators(prev => {
      // Check if indicator already exists
      const exists = prev.some(ind => ind.id === indicator.id);
      if (exists) {
        console.log('[App] Indicator already exists, updating instead of adding');
        return prev.map(ind => ind.id === indicator.id ? indicator : ind);
      }
      return [...prev, indicator];
    });
  }, []);

  // Handle indicator removal from the sidebar
  const handleIndicatorRemoved = useCallback((indicatorId: string) => {
    console.log('[App] Indicator removed:', indicatorId);
    setIndicators(prev => prev.filter(ind => ind.id !== indicatorId));
  }, []);

  // Handle indicator updates from the sidebar
  const handleIndicatorUpdated = useCallback((indicatorId: string, updates: Partial<IndicatorInfo>) => {
    console.log('[App] Indicator updated:', indicatorId, updates);
    setIndicators(prev => prev.map(ind => 
      ind.id === indicatorId ? { ...ind, ...updates } : ind
    ));
  }, []);

  // Handle indicator visibility toggle from the sidebar
  const handleIndicatorToggled = useCallback((indicatorId: string, visible: boolean) => {
    console.log('[App] Indicator toggled:', indicatorId, visible);
    setIndicators(prev => prev.map(ind => 
      ind.id === indicatorId ? { ...ind, visible } : ind
    ));
  }, []);

  // Get indicators by chart type for passing to appropriate chart containers
  const overlayIndicators = indicators.filter(ind => ind.chartType === 'overlay');
  const separateIndicators = indicators.filter(ind => ind.chartType === 'separate');

  return (
    <ErrorBoundary>
      <div className="App" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <header className="App-header" style={{ 
          padding: '0.75rem 1rem', 
          backgroundColor: '#1976d2', 
          color: 'white',
          borderBottom: '1px solid #e0e0e0',
          flexShrink: 0
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 style={{ margin: 0, fontSize: '1.25rem' }}>
              KTRDR Trading Research - Slice 6.5 (Container/Presentation)
            </h1>
            <SymbolSelector 
              selectedSymbol={selectedSymbol}
              onSymbolChange={handleSymbolChange}
            />
          </div>
        </header>
        
        {/* Main content area */}
        <main style={{ 
          display: 'flex', 
          height: 'calc(100vh - 60px)', 
          overflow: 'hidden'
        }}>
          {/* Indicator Sidebar Container */}
          <ErrorBoundary>
            <IndicatorSidebarContainer
              isCollapsed={sidebarCollapsed}
              onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
              onIndicatorAdded={handleIndicatorAdded}
              onIndicatorRemoved={handleIndicatorRemoved}
              onIndicatorUpdated={handleIndicatorUpdated}
              onIndicatorToggled={handleIndicatorToggled}
            />
          </ErrorBoundary>
          
          {/* Chart Area */}
          <div style={{ 
            flex: 1, 
            padding: '1rem',
            overflow: 'auto',
            backgroundColor: '#fafafa',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            {/* Main Price Chart Container */}
            <ErrorBoundary>
              <BasicChartContainer
                symbol={selectedSymbol}
                timeframe={selectedTimeframe}
                indicators={overlayIndicators}
                chartSynchronizer={chartSynchronizer}
                chartId="main-chart"
                width={sidebarCollapsed ? 920 : 800}
                height={400}
                onTimeRangeChange={handleTimeRangeChange}
                onError={(error) => console.error('[App] Main chart error:', error)}
              />
            </ErrorBoundary>

            {/* RSI Chart Container (only show if there are RSI indicators) */}
            {separateIndicators.some(ind => ind.name === 'rsi') && (
              <ErrorBoundary>
                <RSIChartContainer
                  symbol={selectedSymbol}
                  timeframe={selectedTimeframe}
                  indicators={separateIndicators}
                  chartSynchronizer={chartSynchronizer}
                  chartId="rsi-chart"
                  timeRange={timeRange}
                  width={sidebarCollapsed ? 920 : 800}
                  height={200}
                  onError={(error) => console.error('[App] RSI chart error:', error)}
                />
              </ErrorBoundary>
            )}

            {/* Chart instructions for empty state */}
            {indicators.length === 0 && (
              <div style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                color: '#666',
                fontSize: '1rem'
              }}>
                <div>
                  <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📈</div>
                  <div style={{ marginBottom: '0.5rem', fontWeight: '500' }}>
                    Welcome to KTRDR Trading Research
                  </div>
                  <div style={{ fontSize: '0.9rem' }}>
                    Add indicators from the sidebar to start analyzing {selectedSymbol} data
                  </div>
                  <div style={{ fontSize: '0.8rem', marginTop: '0.5rem', color: '#999' }}>
                    Try adding an SMA or RSI indicator to get started
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;