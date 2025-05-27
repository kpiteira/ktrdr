import React, { FC, useCallback } from 'react';
import { useIndicatorManager } from '../../hooks/useIndicatorManager';
import IndicatorSidebar from '../presentation/sidebar/IndicatorSidebar';
import { IndicatorInfo } from '../../store/indicatorRegistry';

/**
 * Container component for the indicator sidebar
 * 
 * This component manages all the state and business logic for indicator management,
 * while delegating the UI rendering to the pure IndicatorSidebar presentation component.
 */

interface IndicatorSidebarContainerProps {
  // Forwarded props
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  
  // Callbacks for parent coordination
  onIndicatorAdded?: (indicator: IndicatorInfo) => void;
  onIndicatorRemoved?: (indicatorId: string) => void;
  onIndicatorUpdated?: (indicatorId: string, updates: Partial<IndicatorInfo>) => void;
  onIndicatorToggled?: (indicatorId: string, visible: boolean) => void;
  
  // External data (e.g., from API)
  symbolData?: any; // Future: for indicator calculations
}

const IndicatorSidebarContainer: FC<IndicatorSidebarContainerProps> = ({
  isCollapsed,
  onToggleCollapse,
  onIndicatorAdded,
  onIndicatorRemoved,
  onIndicatorUpdated,
  onIndicatorToggled,
  symbolData
}) => {
  // Use the indicator manager hook for all state and operations
  const indicatorManager = useIndicatorManager({
    onIndicatorCalculated: useCallback((indicator: IndicatorInfo, data: number[]) => {
      
      // Only notify parent, don't update local state to avoid circular updates
      if (onIndicatorAdded) {
        onIndicatorAdded({ ...indicator, data });
      } else {
      }
    }, [onIndicatorAdded]),
    
    onError: useCallback((error: string) => {
      console.error('[IndicatorSidebarContainer] Indicator error:', error);
      // Could show toast notification or error state
    }, [])
  });

  // Wrap the indicator manager actions to provide parent notifications
  const handleRemoveIndicator = useCallback((id: string) => {
    indicatorManager.removeIndicator(id);
    if (onIndicatorRemoved) {
      onIndicatorRemoved(id);
    }
  }, [indicatorManager.removeIndicator, onIndicatorRemoved]);

  const handleToggleIndicator = useCallback((id: string) => {
    const indicator = indicatorManager.indicators.find(ind => ind.id === id);
    if (indicator) {
      const newVisible = !indicator.visible;
      indicatorManager.toggleIndicator(id);
      if (onIndicatorToggled) {
        onIndicatorToggled(id, newVisible);
      }
    }
  }, [indicatorManager.indicators, indicatorManager.toggleIndicator, onIndicatorToggled]);

  const handleParameterUpdate = useCallback((indicatorId: string, parameterName: string, value: any) => {
    indicatorManager.handleParameterUpdate(indicatorId, parameterName, value);
    
    // Notify parent of the update
    if (onIndicatorUpdated) {
      const indicator = indicatorManager.indicators.find(ind => ind.id === indicatorId);
      if (indicator) {
        onIndicatorUpdated(indicatorId, { 
          parameters: { ...indicator.parameters, [parameterName]: value } 
        });
      }
    }
  }, [indicatorManager.handleParameterUpdate, indicatorManager.indicators, onIndicatorUpdated]);

  return (
    <IndicatorSidebar
      // State from indicator manager
      indicators={indicatorManager.indicators}
      expandedIndicators={indicatorManager.expandedIndicators}
      localParameterValues={indicatorManager.localParameterValues}
      newSMAPeriod={indicatorManager.newSMAPeriod}
      newRSIPeriod={indicatorManager.newRSIPeriod}
      isLoading={indicatorManager.isLoading}
      
      // UI state
      isCollapsed={isCollapsed}
      
      // Actions
      onAddSMA={indicatorManager.handleAddSMA}
      onAddRSI={indicatorManager.handleAddRSI}
      onRemoveIndicator={handleRemoveIndicator}
      onToggleIndicator={handleToggleIndicator}
      onToggleParameterControls={indicatorManager.toggleParameterControls}
      onParameterUpdate={handleParameterUpdate}
      onNewSMAPeriodChange={indicatorManager.setNewSMAPeriod}
      onNewRSIPeriodChange={indicatorManager.setNewRSIPeriod}
      onToggleCollapse={onToggleCollapse}
    />
  );
};

export default IndicatorSidebarContainer;