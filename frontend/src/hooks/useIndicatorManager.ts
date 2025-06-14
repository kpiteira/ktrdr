import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  IndicatorInfo, 
  getIndicatorConfig, 
  createIndicatorInstance, 
  generateIndicatorId,
  validateIndicatorParameters 
} from '../store/indicatorRegistry';

/**
 * Custom hook for managing indicator state and operations
 * 
 * Centralizes all indicator CRUD operations and state management,
 * providing a clean interface for container components.
 */

export interface UseIndicatorManagerReturn {
  // State
  indicators: IndicatorInfo[];
  expandedIndicators: Set<string>;
  localParameterValues: Record<string, Record<string, any>>;
  newSMAPeriod: number;
  newRSIPeriod: number;
  newMACDFastPeriod: number;
  newMACDSlowPeriod: number;
  newMACDSignalPeriod: number;
  newZigZagThreshold: number;
  isLoading: boolean;
  
  // Actions
  addIndicator: (name: string, customParameters?: Record<string, any>) => Promise<void>;
  removeIndicator: (id: string) => void;
  toggleIndicator: (id: string) => void;
  updateIndicator: (id: string, updates: Partial<IndicatorInfo>) => void;
  toggleParameterControls: (indicatorId: string) => void;
  
  // Form handlers
  setNewSMAPeriod: (period: number) => void;
  setNewRSIPeriod: (period: number) => void;
  setNewMACDFastPeriod: (period: number) => void;
  setNewMACDSlowPeriod: (period: number) => void;
  setNewMACDSignalPeriod: (period: number) => void;
  setNewZigZagThreshold: (threshold: number) => void;
  handleAddSMA: () => Promise<void>;
  handleAddRSI: () => Promise<void>;
  handleAddMACD: () => Promise<void>;
  handleAddZigZag: () => Promise<void>;
  handleParameterUpdate: (indicatorId: string, parameterName: string, value: any) => void;
}

export interface UseIndicatorManagerOptions {
  onIndicatorCalculated?: (indicator: IndicatorInfo, data: number[]) => void;
  onError?: (error: string) => void;
}

export const useIndicatorManager = (
  options: UseIndicatorManagerOptions = {}
): UseIndicatorManagerReturn => {
  const { onIndicatorCalculated, onError } = options;

  // Core state
  const [indicators, setIndicators] = useState<IndicatorInfo[]>([]);
  const [expandedIndicators, setExpandedIndicators] = useState<Set<string>>(new Set());
  const [localParameterValues, setLocalParameterValues] = useState<Record<string, Record<string, any>>>({});
  const [isLoading, setIsLoading] = useState(false);
  
  // Form state
  const [newSMAPeriod, setNewSMAPeriod] = useState(20);
  const [newRSIPeriod, setNewRSIPeriod] = useState(14);
  const [newMACDFastPeriod, setNewMACDFastPeriod] = useState(12);
  const [newMACDSlowPeriod, setNewMACDSlowPeriod] = useState(26);
  const [newMACDSignalPeriod, setNewMACDSignalPeriod] = useState(9);
  const [newZigZagThreshold, setNewZigZagThreshold] = useState(0.05);
  
  // Refs for tracking
  const initializedIndicatorsRef = useRef<Set<string>>(new Set());

  // Initialize local parameter values when indicators change
  useEffect(() => {
    const newLocalValues: Record<string, Record<string, any>> = {};
    indicators.forEach(indicator => {
      // Only initialize if we haven't already initialized this indicator
      if (!initializedIndicatorsRef.current.has(indicator.id)) {
        newLocalValues[indicator.id] = { ...indicator.parameters };
        initializedIndicatorsRef.current.add(indicator.id);
      }
    });
    
    if (Object.keys(newLocalValues).length > 0) {
      setLocalParameterValues(prev => ({ ...prev, ...newLocalValues }));
    }
  }, [indicators]);

  // Generic add indicator function
  const addIndicator = useCallback(async (name: string, customParameters?: Record<string, any>) => {
    setIsLoading(true);
    
    try {
      const config = getIndicatorConfig(name);
      if (!config) {
        throw new Error(`Unknown indicator: ${name}`);
      }

      // Create indicator instance (but don't add it yet)
      const id = generateIndicatorId(name);
      const instance = createIndicatorInstance(name, id, customParameters);
      
      if (!instance) {
        throw new Error(`Failed to create indicator instance: ${name}`);
      }

      // Validate parameters
      const validation = validateIndicatorParameters(name, instance.parameters);
      if (!validation.valid) {
        throw new Error(`Invalid parameters: ${validation.errors.join(', ')}`);
      }

      // Check for duplicates before adding
      const isDuplicate = indicators.some(existing => 
        existing.name === instance.name && 
        JSON.stringify(existing.parameters) === JSON.stringify(instance.parameters)
      );

      if (isDuplicate) {
        return; // Exit early
      }

      // Add to indicators list
      setIndicators(prev => [...prev, instance]);

      // Trigger calculation callback
      if (onIndicatorCalculated) {
        onIndicatorCalculated(instance, []);
      }
      
      
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error.message : 'Failed to add indicator');
      }
    } finally {
      setIsLoading(false);
    }
  }, [onIndicatorCalculated, onError]); // Remove 'indicators' - we use setIndicators(prev => ...) so don't need it

  // Remove indicator
  const removeIndicator = useCallback((id: string) => {
    setIndicators(prev => prev.filter(ind => ind.id !== id));
    setExpandedIndicators(prev => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
    setLocalParameterValues(prev => {
      const newValues = { ...prev };
      delete newValues[id];
      return newValues;
    });
    initializedIndicatorsRef.current.delete(id);
  }, []);

  // Toggle indicator visibility
  const toggleIndicator = useCallback((id: string) => {
    setIndicators(prev => prev.map(ind => 
      ind.id === id ? { ...ind, visible: !ind.visible } : ind
    ));
  }, []);

  // Update indicator
  const updateIndicator = useCallback((id: string, updates: Partial<IndicatorInfo>) => {
    setIndicators(prev => prev.map(ind => 
      ind.id === id ? { ...ind, ...updates } : ind
    ));
  }, []);

  // Toggle parameter controls
  const toggleParameterControls = useCallback((indicatorId: string) => {
    setExpandedIndicators(prev => {
      const newSet = new Set(prev);
      if (newSet.has(indicatorId)) {
        newSet.delete(indicatorId);
      } else {
        newSet.add(indicatorId);
      }
      return newSet;
    });
  }, []);

  // Handle parameter updates
  const handleParameterUpdate = useCallback((indicatorId: string, parameterName: string, value: any) => {
    // Check if this is a fuzzy parameter (top-level property) or regular parameter
    const isFuzzyParameter = ['fuzzyVisible', 'fuzzyOpacity', 'fuzzyColorScheme'].includes(parameterName);
    
    // Update local state immediately for responsive UI (only for regular parameters)
    if (!isFuzzyParameter) {
      setLocalParameterValues(prev => {
        const newValues = {
          ...prev,
          [indicatorId]: {
            ...prev[indicatorId],
            [parameterName]: value
          }
        };
        return newValues;
      });
    }
    
    // Update indicator state
    setIndicators(prev => prev.map(ind => 
      ind.id === indicatorId 
        ? isFuzzyParameter
          ? { ...ind, [parameterName]: value }  // Fuzzy parameters are top-level
          : { ...ind, parameters: { ...ind.parameters, [parameterName]: value } }  // Regular parameters
        : ind
    ));
  }, []);

  // Specific add handlers
  const handleAddSMA = useCallback(async () => {
    if (newSMAPeriod >= 2 && newSMAPeriod <= 500) {
      // Check for duplicate before adding
      const duplicate = indicators.some(ind => 
        ind.name === 'sma' && ind.parameters.period === newSMAPeriod
      );
      
      if (duplicate) {
        return;
      }
      
      await addIndicator('sma', { period: newSMAPeriod });
    }
  }, [newSMAPeriod, addIndicator, indicators]);

  const handleAddRSI = useCallback(async () => {
    if (newRSIPeriod >= 2 && newRSIPeriod <= 100) {
      // Check for duplicate before adding
      const duplicate = indicators.some(ind => 
        ind.name === 'rsi' && ind.parameters.period === newRSIPeriod
      );
      
      if (duplicate) {
        return;
      }
      
      await addIndicator('rsi', { period: newRSIPeriod });
    }
  }, [newRSIPeriod, addIndicator, indicators]);

  const handleAddMACD = useCallback(async () => {
    // Validate MACD parameters
    if (newMACDFastPeriod >= 2 && newMACDFastPeriod <= 50 &&
        newMACDSlowPeriod >= 5 && newMACDSlowPeriod <= 100 &&
        newMACDSignalPeriod >= 2 && newMACDSignalPeriod <= 50 &&
        newMACDFastPeriod < newMACDSlowPeriod) {
      
      // Check for duplicate before adding
      const duplicate = indicators.some(ind => 
        ind.name === 'macd' && 
        ind.parameters.fast_period === newMACDFastPeriod &&
        ind.parameters.slow_period === newMACDSlowPeriod &&
        ind.parameters.signal_period === newMACDSignalPeriod
      );
      
      if (duplicate) {
        return;
      }
      
      await addIndicator('macd', { 
        fast_period: newMACDFastPeriod,
        slow_period: newMACDSlowPeriod,
        signal_period: newMACDSignalPeriod
      });
    }
  }, [newMACDFastPeriod, newMACDSlowPeriod, newMACDSignalPeriod, addIndicator, indicators]);

  const handleAddZigZag = useCallback(async () => {
    if (newZigZagThreshold >= 0.01 && newZigZagThreshold <= 0.5) {
      // Check for duplicate before adding
      const duplicate = indicators.some(ind => 
        ind.name === 'zigzag' && ind.parameters.threshold === newZigZagThreshold
      );
      
      if (duplicate) {
        return;
      }
      
      await addIndicator('zigzag', { threshold: newZigZagThreshold });
    }
  }, [newZigZagThreshold, addIndicator, indicators]);

  return {
    // State
    indicators,
    expandedIndicators,
    localParameterValues,
    newSMAPeriod,
    newRSIPeriod,
    newMACDFastPeriod,
    newMACDSlowPeriod,
    newMACDSignalPeriod,
    newZigZagThreshold,
    isLoading,
    
    // Actions
    addIndicator,
    removeIndicator,
    toggleIndicator,
    updateIndicator,
    toggleParameterControls,
    
    // Form handlers
    setNewSMAPeriod,
    setNewRSIPeriod,
    setNewMACDFastPeriod,
    setNewMACDSlowPeriod,
    setNewMACDSignalPeriod,
    setNewZigZagThreshold,
    handleAddSMA,
    handleAddRSI,
    handleAddMACD,
    handleAddZigZag,
    handleParameterUpdate
  };
};