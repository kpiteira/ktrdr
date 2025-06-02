import { FC, useCallback } from 'react';
import { useIndicatorManager } from '../../hooks/useIndicatorManager';
import { useToast } from '../../context/ToastContext';
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
  const { showToast } = useToast();
  
  // Use the indicator manager hook for all state and operations
  const indicatorManager = useIndicatorManager({
    onIndicatorCalculated: useCallback((indicator: IndicatorInfo, data: number[]) => {
      // Show success toast
      showToast({
        type: 'success',
        title: 'Indicator Added',
        message: `${indicator.displayName} has been added to your chart`,
        duration: 3000
      });
      
      // Only notify parent, don't update local state to avoid circular updates
      if (onIndicatorAdded) {
        onIndicatorAdded({ ...indicator, data });
      }
    }, [onIndicatorAdded, showToast]),
    
    onError: useCallback((error: string) => {
      console.error('[IndicatorSidebarContainer] Indicator error:', error);
      
      // Show error toast with user-friendly message
      const userFriendlyError = error.includes('Network') 
        ? 'Connection error. Please check your internet and try again.'
        : error.includes('calculation') 
        ? 'Failed to calculate indicator. Please try again.'
        : 'Something went wrong. Please try again.';
        
      showToast({
        type: 'error',
        title: 'Indicator Error',
        message: userFriendlyError,
        duration: 5000
      });
    }, [showToast])
  });

  // Wrap the indicator manager actions to provide parent notifications
  const handleRemoveIndicator = useCallback((id: string) => {
    const indicator = indicatorManager.indicators.find(ind => ind.id === id);
    indicatorManager.removeIndicator(id);
    
    if (indicator) {
      showToast({
        type: 'info',
        title: 'Indicator Removed',
        message: `${indicator.displayName} has been removed from your chart`,
        duration: 2000
      });
    }
    
    if (onIndicatorRemoved) {
      onIndicatorRemoved(id);
    }
  }, [indicatorManager.indicators, indicatorManager.removeIndicator, onIndicatorRemoved, showToast]);

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
        // Handle fuzzy parameters differently from regular parameters
        const isFuzzyParameter = ['fuzzyVisible', 'fuzzyOpacity', 'fuzzyColorScheme'].includes(parameterName);
        
        if (isFuzzyParameter) {
          onIndicatorUpdated(indicatorId, { [parameterName]: value });
        } else {
          onIndicatorUpdated(indicatorId, { 
            parameters: { ...indicator.parameters, [parameterName]: value } 
          });
        }
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