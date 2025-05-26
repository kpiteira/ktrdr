import React, { FC, useState, useCallback, useMemo } from 'react';
import { useChartSynchronizer } from './hooks/useChartSynchronizer';
import IndicatorSidebarContainer from './components/containers/IndicatorSidebarContainer';
import BasicChartContainer from './components/containers/BasicChartContainer';
import RSIChartContainer from './components/containers/RSIChartContainer';
import SymbolSelector from './components/SymbolSelector';
import ErrorBoundary from './components/ErrorBoundary';
import { PriceDataProvider } from './context/PriceDataContext';
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
  
  // Chart synchronization - RE-ENABLED with visual-only sync
  const chartSynchronizer = useChartSynchronizer();
  
  // Manual sync RSI chart to main chart when both are ready
  const handleRSIChartReady = useCallback(() => {
    // Small delay to ensure both charts are fully initialized and have data
    setTimeout(() => {
      chartSynchronizer.syncAllToChart('main-chart');
    }, 200);
  }, [chartSynchronizer]);
  
  // Time range synchronization between charts
  const [timeRange, setTimeRange] = useState<{ start: string; end: string } | null>(null);
  
  // Indicator state for coordination between sidebar and charts
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([]);

  // Handle symbol changes from the symbol selector
  const handleSymbolChange = useCallback((symbol: string, timeframe: string) => {
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
    }
    
    // Update state
    setSelectedSymbol(symbol);
    setSelectedTimeframe(actualTimeframe);
    
    // Clear time range when symbol changes
    setTimeRange(null);
  }, []);

  // Handle time range changes from the main chart
  const handleTimeRangeChange = useCallback((range: { start: string; end: string }) => {
    setTimeRange(range);
  }, []);

  // Handle indicator addition from the sidebar
  const handleIndicatorAdded = useCallback((indicator: IndicatorInfo) => {
    setIndicators(prev => {
      // Check if indicator already exists
      const exists = prev.some(ind => ind.id === indicator.id);
      if (exists) {
        return prev.map(ind => ind.id === indicator.id ? indicator : ind);
      }
      return [...prev, indicator];
    });
  }, []);

  // Handle indicator removal from the sidebar
  const handleIndicatorRemoved = useCallback((indicatorId: string) => {
    setIndicators(prev => prev.filter(ind => ind.id !== indicatorId));
  }, []);

  // Handle indicator updates from the sidebar
  const handleIndicatorUpdated = useCallback((indicatorId: string, updates: Partial<IndicatorInfo>) => {
    setIndicators(prev => prev.map(ind => 
      ind.id === indicatorId ? { ...ind, ...updates } : ind
    ));
  }, []);

  // Handle indicator visibility toggle from the sidebar
  const handleIndicatorToggled = useCallback((indicatorId: string, visible: boolean) => {
    setIndicators(prev => prev.map(ind => 
      ind.id === indicatorId ? { ...ind, visible } : ind
    ));
  }, []);

  // Stable error handlers for charts
  const handleMainChartError = useCallback((error: string) => {
    console.error('[App] Main chart error:', error);
  }, []);

  const handleRSIChartError = useCallback((error: string) => {
    console.error('[App] RSI chart error:', error);
  }, []);

  // Split indicators by chart type (memoized for performance)
  const { overlayIndicators, separateIndicators } = useMemo(() => {
    const overlay = indicators.filter(ind => ind.chartType === 'overlay');
    const separate = indicators.filter(ind => ind.chartType === 'separate');
    
    console.log('[App] Indicator split - Total:', indicators.length, 'Overlay:', overlay.length, 'Separate:', separate.length);
    console.log('[App] Overlay indicators:', overlay.map(ind => `${ind.displayName} (visible: ${ind.visible})`));
    
    return {
      overlayIndicators: overlay,
      separateIndicators: separate
    };
  }, [indicators]);

  // Memoize chart dimensions to prevent unnecessary re-renders
  const chartDimensions = useMemo(() => ({
    width: sidebarCollapsed ? 920 : 800,
    height: {
      main: 400,
      rsi: 200
    }
  }), [sidebarCollapsed]);

  return (
    <ErrorBoundary>
      <PriceDataProvider>
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
            {/* Main Price Chart Container - Overlay indicators only */}
            <ErrorBoundary>
              <BasicChartContainer
                symbol={selectedSymbol}
                timeframe={selectedTimeframe}
                indicators={overlayIndicators}
                chartSynchronizer={chartSynchronizer}
                chartId="main-chart"
                width={chartDimensions.width}
                height={chartDimensions.height.main}
                onTimeRangeChange={handleTimeRangeChange}
                onError={handleMainChartError}
              />
            </ErrorBoundary>

            {/* RSI Chart Container - Separate panel for oscillators */}
            {separateIndicators.some(ind => ind.name === 'rsi') && (
              <ErrorBoundary>
                <RSIChartContainer
                  symbol={selectedSymbol}
                  timeframe={selectedTimeframe}
                  indicators={separateIndicators}
                  chartSynchronizer={chartSynchronizer}
                  chartId="rsi-chart"
                  timeRange={timeRange}
                  width={chartDimensions.width}
                  height={chartDimensions.height.rsi}
                  onChartReady={handleRSIChartReady}
                  onError={handleRSIChartError}
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
      </PriceDataProvider>
    </ErrorBoundary>
  );
};

export default App;