/**
 * OscillatorPanelManager - Container component for managing multiple oscillator panels
 * 
 * This component handles the creation, management, and synchronization of multiple
 * oscillator panels (RSI, MACD, etc.) with proper state management and lifecycle handling.
 */

import { FC, useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { IChartApi } from 'lightweight-charts';
import { IndicatorInfo, getIndicatorConfig } from '../../store/indicatorRegistry';
import { PanelConfig, PanelState } from '../../types/panels';
import { useChartSynchronizer } from '../../hooks/useChartSynchronizer';
import { createLogger } from '../../utils/logger';
import BaseOscillatorPanel from '../presentation/panels/BaseOscillatorPanel';
import OscillatorChartContainer from './OscillatorChartContainer';

const logger = createLogger('OscillatorPanelManager');

/**
 * Props for OscillatorPanelManager
 */
interface OscillatorPanelManagerProps {
  /** All indicators from the indicator manager */
  indicators: IndicatorInfo[];
  /** Symbol being displayed */
  symbol: string;
  /** Timeframe being displayed */
  timeframe: string;
  /** Container width */
  width?: number;
  /** Chart synchronizer instance */
  chartSynchronizer?: ReturnType<typeof useChartSynchronizer>;
  /** Callbacks */
  onPanelCreated?: (panelId: string) => void;
  onPanelRemoved?: (panelId: string) => void;
  onPanelError?: (panelId: string, error: string) => void;
}

/**
 * Default panel configurations for different indicator types
 */
const DEFAULT_PANEL_CONFIGS: Record<string, PanelConfig> = {
  rsi: {
    type: 'rsi',
    title: 'RSI Oscillator',
    defaultHeight: 200,
    collapsible: true,
    yAxisConfig: {
      type: 'fixed',
      range: { min: 0, max: 100 },
      referenceLines: [
        { value: 30, color: '#888888', label: 'Oversold', style: 'dashed' },
        { value: 70, color: '#888888', label: 'Overbought', style: 'dashed' }
      ]
    }
  },
  macd: {
    type: 'macd',
    title: 'MACD Oscillator',
    defaultHeight: 200,
    collapsible: true,
    yAxisConfig: {
      type: 'auto',
      referenceLines: [
        { value: 0, color: '#888888', label: 'Zero Line', style: 'solid' }
      ]
    }
  },
  stochastic: {
    type: 'stochastic',
    title: 'Stochastic Oscillator',
    defaultHeight: 200,
    collapsible: true,
    yAxisConfig: {
      type: 'fixed',
      range: { min: 0, max: 100 },
      referenceLines: [
        { value: 20, color: '#888888', label: 'Oversold', style: 'dashed' },
        { value: 80, color: '#888888', label: 'Overbought', style: 'dashed' }
      ]
    }
  }
};

/**
 * OscillatorPanelManager component
 */
const OscillatorPanelManager: FC<OscillatorPanelManagerProps> = ({
  indicators,
  symbol,
  timeframe,
  width = 800,
  chartSynchronizer,
  onPanelCreated,
  onPanelRemoved,
  onPanelError
}) => {
  // Panel state management
  const [panels, setPanels] = useState<PanelState[]>([]);
  const [nextPanelOrder, setNextPanelOrder] = useState(0);
  
  // References for tracking
  const panelChartsRef = useRef<Map<string, IChartApi>>(new Map());
  const panelIdCounterRef = useRef(0);

  /**
   * Generate unique panel ID
   */
  const generatePanelId = useCallback((type: string): string => {
    const id = `${type}-panel-${panelIdCounterRef.current++}`;
    logger.debug(`Generated panel ID: ${id}`);
    return id;
  }, []);

  /**
   * Group indicators by their panel type (based on chartType: 'separate')
   */
  const groupedIndicators = useMemo(() => {
    const groups: Record<string, IndicatorInfo[]> = {};
    
    indicators.forEach(indicator => {
      const config = getIndicatorConfig(indicator.name);
      if (config && config.chartType === 'separate') {
        const panelType = indicator.name; // Use indicator name as panel type
        if (!groups[panelType]) {
          groups[panelType] = [];
        }
        groups[panelType].push(indicator);
      }
    });
    
    logger.debug('Grouped indicators by panel type:', groups);
    return groups;
  }, [indicators]);

  /**
   * Create panel for indicator type
   */
  const createPanel = useCallback((type: string, typeIndicators: IndicatorInfo[]): string => {
    const panelId = generatePanelId(type);
    const config = DEFAULT_PANEL_CONFIGS[type] || DEFAULT_PANEL_CONFIGS.rsi; // Fallback to RSI config
    
    const newPanel: PanelState = {
      id: panelId,
      config: { ...config, type },
      height: config.defaultHeight,
      isCollapsed: false,
      isVisible: true,
      order: nextPanelOrder,
      isLoading: false
    };
    
    setPanels(prev => [...prev, newPanel]);
    setNextPanelOrder(prev => prev + 1);
    
    if (onPanelCreated) {
      onPanelCreated(panelId);
    }
    
    logger.debug(`Created panel ${panelId} for type ${type} with ${typeIndicators.length} indicators`);
    return panelId;
  }, [generatePanelId, nextPanelOrder, onPanelCreated]);

  /**
   * Remove panel
   */
  const removePanel = useCallback((panelId: string) => {
    // Remove chart from synchronizer
    if (chartSynchronizer) {
      chartSynchronizer.unregisterChart(panelId);
    }
    
    // Clean up chart reference
    panelChartsRef.current.delete(panelId);
    
    // Remove from state
    setPanels(prev => prev.filter(p => p.id !== panelId));
    
    if (onPanelRemoved) {
      onPanelRemoved(panelId);
    }
    
    logger.debug(`Removed panel ${panelId}`);
  }, [chartSynchronizer, onPanelRemoved]);

  /**
   * Update panel state
   */
  const updatePanelState = useCallback((panelId: string, updates: Partial<PanelState>) => {
    setPanels(prev => prev.map(panel => 
      panel.id === panelId ? { ...panel, ...updates } : panel
    ));
  }, []);

  /**
   * Handle chart creation for a panel
   */
  const handleChartCreated = useCallback((panelId: string, chart: IChartApi) => {
    panelChartsRef.current.set(panelId, chart);
    
    if (chartSynchronizer) {
      chartSynchronizer.registerChart(panelId, chart);
    }
    
    logger.debug(`Chart registered for panel ${panelId}`);
  }, [chartSynchronizer]);

  /**
   * Handle chart destruction for a panel
   */
  const handleChartDestroyed = useCallback((panelId: string) => {
    if (chartSynchronizer) {
      chartSynchronizer.unregisterChart(panelId);
    }
    
    panelChartsRef.current.delete(panelId);
    logger.debug(`Chart unregistered for panel ${panelId}`);
  }, [chartSynchronizer]);

  /**
   * Handle crosshair synchronization
   */
  const handleCrosshairMove = useCallback((panelId: string, params: any) => {
    if (chartSynchronizer) {
      chartSynchronizer.synchronizeCrosshair(panelId, params);
    }
  }, [chartSynchronizer]);

  /**
   * Create panel actions for a specific panel
   */
  const createPanelActions = useCallback((panelId: string) => ({
    toggleCollapse: () => {
      updatePanelState(panelId, { 
        isCollapsed: !panels.find(p => p.id === panelId)?.isCollapsed 
      });
    },
    updateHeight: (height: number) => {
      updatePanelState(panelId, { height });
    },
    remove: () => {
      removePanel(panelId);
    },
    updateConfig: (configUpdates: Partial<PanelConfig>) => {
      const panel = panels.find(p => p.id === panelId);
      if (panel) {
        updatePanelState(panelId, {
          config: { ...panel.config, ...configUpdates }
        });
      }
    }
  }), [panels, updatePanelState, removePanel]);

  /**
   * Panel lifecycle callbacks
   */
  const panelLifecycle = useMemo(() => ({
    onChartReady: (panelId: string, chart: IChartApi) => {
      handleChartCreated(panelId, chart);
    },
    onDestroy: (panelId: string) => {
      handleChartDestroyed(panelId);
    }
  }), [handleChartCreated, handleChartDestroyed]);

  /**
   * Synchronize panels with grouped indicators
   * Create panels for new indicator types, remove panels with no indicators
   */
  useEffect(() => {
    const currentPanelTypes = new Set(panels.map(p => p.config.type));
    const requiredPanelTypes = new Set(Object.keys(groupedIndicators));
    
    // Create panels for new indicator types
    requiredPanelTypes.forEach(type => {
      if (!currentPanelTypes.has(type)) {
        createPanel(type, groupedIndicators[type]);
      }
    });
    
    // Remove panels that no longer have indicators
    const panelsToRemove = panels.filter(panel => 
      !requiredPanelTypes.has(panel.config.type)
    );
    
    panelsToRemove.forEach(panel => {
      removePanel(panel.id);
    });
    
  }, [groupedIndicators, panels, createPanel, removePanel]);

  /**
   * Get sorted panels by order
   */
  const sortedPanels = useMemo(() => {
    return [...panels].sort((a, b) => a.order - b.order);
  }, [panels]);

  // If no oscillator indicators, don't render anything
  if (Object.keys(groupedIndicators).length === 0) {
    return null;
  }

  return (
    <div
      style={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem'
      }}
      data-testid="oscillator-panel-manager"
    >
      {sortedPanels.map(panel => {
        const panelIndicators = groupedIndicators[panel.config.type] || [];
        
        return (
          <div key={panel.id} style={{ width: '100%' }}>
            {/* Panel with integrated data container */}
            <OscillatorChartContainer
              width={width}
              height={panel.height}
              symbol={symbol}
              timeframe={timeframe}
              indicators={panelIndicators}
              chartSynchronizer={chartSynchronizer}
              chartId={panel.id}
              onChartReady={() => {}} // Handled by panel lifecycle
              onError={(error) => {
                updatePanelState(panel.id, { error });
                if (onPanelError) {
                  onPanelError(panel.id, error);
                }
              }}
              render={(containerData) => (
                <BaseOscillatorPanel
                  state={panel}
                  indicators={panelIndicators}
                  lifecycle={panelLifecycle}
                  width={width}
                  height={panel.isCollapsed ? 40 : panel.height}
                  actions={createPanelActions(panel.id)}
                  oscillatorData={containerData.oscillatorData || undefined}
                  isLoading={containerData.isLoading}
                  error={containerData.error || undefined}
                  fuzzyData={containerData.fuzzyData}
                  fuzzyVisible={containerData.fuzzyVisible}
                  fuzzyOpacity={containerData.fuzzyOpacity}
                  fuzzyColorScheme={containerData.fuzzyColorScheme}
                  onChartCreated={(chart) => handleChartCreated(panel.id, chart)}
                  onChartDestroyed={() => handleChartDestroyed(panel.id)}
                  onCrosshairMove={(params) => handleCrosshairMove(panel.id, params)}
                  preserveTimeScale={true}
                />
              )}
            />
          </div>
        );
      })}
    </div>
  );
};

export default OscillatorPanelManager;