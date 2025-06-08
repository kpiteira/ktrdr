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
import RSIPanel from '../presentation/panels/RSIPanel';
import MACDPanel from '../presentation/panels/MACDPanel';
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
  /** Trading hours filtering */
  tradingHoursOnly?: boolean;
  includeExtended?: boolean;
  /** Timezone for display */
  timezone?: string;
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
  tradingHoursOnly = false,
  includeExtended = false,
  timezone = 'UTC',
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
  const panelsRef = useRef<PanelState[]>([]);
  const pendingPanelCreation = useRef<Set<string>>(new Set()); // Track panel types being created
  
  // Keep panelsRef updated and clean up pending flags
  useEffect(() => {
    panelsRef.current = panels;
    
    // Clean up pending flags for panels that now exist
    const existingPanelTypes = new Set(panels.map(p => p.config.type));
    const pendingTypes = Array.from(pendingPanelCreation.current);
    
    pendingTypes.forEach(type => {
      if (existingPanelTypes.has(type)) {
        pendingPanelCreation.current.delete(type);
      }
    });
  }, [panels]);

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
    
    logger.debug('Grouped indicators by panel type:', {
      groups,
      groupKeys: Object.keys(groups),
      totalGroups: Object.keys(groups).length
    });
    return groups;
  }, [indicators]);

  /**
   * Create panel for indicator type
   */
  const createPanel = useCallback((type: string, typeIndicators: IndicatorInfo[]): string => {
    logger.debug(`createPanel called for type: ${type}`, {
      typeIndicators: typeIndicators.map(ind => ind.id),
      nextPanelOrder
    });
    
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
    
    logger.debug(`About to set panels state`, {
      panelId,
      type,
      newPanelOrder: nextPanelOrder
    });
    
    setPanels(prev => {
      logger.debug(`setPanels updater function called`, {
        previousPanels: prev.map(p => ({ id: p.id, type: p.config.type })),
        newPanel: { id: panelId, type },
        willHaveDuplicateType: prev.some(p => p.config.type === type)
      });
      
      return [...prev, newPanel];
    });
    setNextPanelOrder(prev => prev + 1);
    
    // Pending flag will be cleaned up by the panels effect when state updates
    
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
    // Find the panel to get its type before removing
    const panelToRemove = panels.find(p => p.id === panelId);
    const panelType = panelToRemove?.config.type;
    
    // Remove chart from synchronizer
    if (chartSynchronizer) {
      chartSynchronizer.unregisterChart(panelId);
    }
    
    // Clean up chart reference
    panelChartsRef.current.delete(panelId);
    
    // Clean up pending flag if needed
    if (panelType) {
      pendingPanelCreation.current.delete(panelType);
    }
    
    // Remove from state
    setPanels(prev => prev.filter(p => p.id !== panelId));
    
    if (onPanelRemoved) {
      onPanelRemoved(panelId);
    }
    
    logger.debug(`Removed panel ${panelId}`);
  }, [chartSynchronizer, onPanelRemoved, panels]);

  // Stable references for functions to prevent dependency loops
  const createPanelRef = useRef(createPanel);
  const removePanelRef = useRef(removePanel);
  
  // Update refs when functions change
  useEffect(() => {
    createPanelRef.current = createPanel;
    removePanelRef.current = removePanel;
  }, [createPanel, removePanel]);

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
   * Select appropriate panel component based on panel type
   */
  const createPanelComponent = useCallback((
    panel: PanelState,
    panelIndicators: IndicatorInfo[],
    containerData: any
  ) => {
    const commonProps = {
      state: panel,
      indicators: panelIndicators,
      lifecycle: panelLifecycle,
      width,
      height: panel.isCollapsed ? 40 : panel.height,
      actions: createPanelActions(panel.id),
      oscillatorData: containerData.oscillatorData || undefined,
      isLoading: containerData.isLoading,
      error: containerData.error || undefined,
      fuzzyData: containerData.fuzzyData,
      fuzzyVisible: containerData.fuzzyVisible,
      fuzzyOpacity: containerData.fuzzyOpacity,
      fuzzyColorScheme: containerData.fuzzyColorScheme,
      onChartCreated: (chart: IChartApi) => handleChartCreated(panel.id, chart),
      onChartDestroyed: () => handleChartDestroyed(panel.id),
      onCrosshairMove: (params: any) => handleCrosshairMove(panel.id, params),
      preserveTimeScale: true
    };

    // Return specialized panel component based on type
    switch (panel.config.type) {
      case 'rsi':
        return <RSIPanel {...commonProps} />;
      case 'macd':
        return <MACDPanel {...commonProps} />;
      default:
        // Fallback to base panel for unknown types
        return <BaseOscillatorPanel {...commonProps} />;
    }
  }, [
    panelLifecycle, 
    width, 
    createPanelActions, 
    handleChartCreated, 
    handleChartDestroyed, 
    handleCrosshairMove
  ]);

  /**
   * Synchronize panels with grouped indicators
   * Create panels for new indicator types, remove panels with no indicators
   */
  useEffect(() => {
    // Use the most up-to-date panels state instead of ref to avoid timing issues
    const currentPanels = panels;
    const currentPanelTypes = new Set(currentPanels.map(p => p.config.type));
    const requiredPanelTypes = new Set(Object.keys(groupedIndicators));
    
    logger.debug('Panel sync effect triggered:', {
      currentPanels: currentPanels.map(p => ({ id: p.id, type: p.config.type })),
      currentPanelTypes: Array.from(currentPanelTypes),
      requiredPanels: Array.from(requiredPanelTypes),
      groupedIndicators: Object.keys(groupedIndicators).map(key => ({
        type: key,
        count: groupedIndicators[key].length,
        indicators: groupedIndicators[key].map(ind => ind.id)
      })),
      totalCurrentPanels: currentPanels.length,
      totalRequiredPanels: requiredPanelTypes.size
    });
    
    // Check if there are any changes needed
    const needsCreation = Array.from(requiredPanelTypes).filter(type => !currentPanelTypes.has(type));
    const needsRemoval = currentPanels.filter(panel => !requiredPanelTypes.has(panel.config.type));
    
    logger.debug('Panel sync changes needed:', {
      needsCreation: needsCreation,
      needsRemoval: needsRemoval.map(p => ({ id: p.id, type: p.config.type }))
    });
    
    // Create panels for new indicator types (only if they don't exist)
    needsCreation.forEach(type => {
      logger.debug(`About to create panel for type: ${type}`, {
        existingPanelsOfType: currentPanels.filter(p => p.config.type === type).length,
        requiredIndicators: groupedIndicators[type].map(ind => ind.id),
        alreadyExistsInCurrent: currentPanelTypes.has(type),
        willCreateDuplicate: currentPanels.some(p => p.config.type === type)
      });
      
      // Check if panel already exists OR is pending creation
      const typeExistsInCurrentState = currentPanelTypes.has(type);
      const typeExistsInRef = panelsRef.current.some(p => p.config.type === type);
      const typeIsPendingCreation = pendingPanelCreation.current.has(type);
      
      if (!typeExistsInCurrentState && !typeExistsInRef && !typeIsPendingCreation) {
        logger.debug(`Creating panel for type: ${type} - no duplicates detected`);
        // Mark as pending before creating
        pendingPanelCreation.current.add(type);
        createPanelRef.current(type, groupedIndicators[type]);
      } else {
        logger.debug(`Prevented duplicate panel creation for type: ${type}`, {
          existsInCurrentState: typeExistsInCurrentState,
          existsInRef: typeExistsInRef,
          isPendingCreation: typeIsPendingCreation
        });
      }
    });
    
    // Remove panels that no longer have indicators
    if (needsRemoval.length > 0) {
      logger.debug(`Removing ${needsRemoval.length} obsolete panels`);
      needsRemoval.forEach(panel => {
        removePanelRef.current(panel.id);
      });
    }
    
    if (needsCreation.length === 0 && needsRemoval.length === 0) {
      logger.debug('No panel changes needed - synchronization complete');
    }
    
  }, [groupedIndicators]); // Only depend on groupedIndicators to avoid infinite loops

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
              tradingHoursOnly={tradingHoursOnly}
              includeExtended={includeExtended}
              timezone={timezone}
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
              render={(containerData) => 
                createPanelComponent(panel, panelIndicators, containerData)
              }
            />
          </div>
        );
      })}
    </div>
  );
};

export default OscillatorPanelManager;