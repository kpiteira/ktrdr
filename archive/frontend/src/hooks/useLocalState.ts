import { useState, useCallback, useRef } from 'react';

/**
 * Custom hook for managing local UI state to prevent circular updates
 * 
 * This hook provides a pattern for managing local state that needs to be
 * synchronized with parent state, but should remain responsive during user
 * interactions to prevent the "action doesn't reflect" issues we've been
 * experiencing.
 */

export interface UseLocalStateOptions<T> {
  initialValue: T;
  onValueChange?: (value: T) => void;
  debounceMs?: number;
}

export interface UseLocalStateReturn<T> {
  localValue: T;
  setLocalValue: (value: T) => void;
  syncWithParent: (parentValue: T) => void;
  isLocallyModified: boolean;
  resetToParent: (parentValue: T) => void;
}

export const useLocalState = <T>(
  options: UseLocalStateOptions<T>
): UseLocalStateReturn<T> => {
  const { initialValue, onValueChange, debounceMs = 300 } = options;
  
  const [localValue, setLocalValueState] = useState<T>(initialValue);
  const [isLocallyModified, setIsLocallyModified] = useState(false);
  const timeoutRef = useRef<number | null>(null);
  const lastParentValueRef = useRef<T>(initialValue);

  const setLocalValue = useCallback((value: T) => {
    setLocalValueState(value);
    setIsLocallyModified(true);
    
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Debounce the parent update
    if (onValueChange) {
      timeoutRef.current = setTimeout(() => {
        onValueChange(value);
        timeoutRef.current = null;
      }, debounceMs);
    }
  }, [onValueChange, debounceMs]);

  const syncWithParent = useCallback((parentValue: T) => {
    
    // Only sync if we haven't locally modified the value recently
    if (!isLocallyModified || JSON.stringify(parentValue) !== JSON.stringify(lastParentValueRef.current)) {
      setLocalValueState(parentValue);
      setIsLocallyModified(false);
    }
    lastParentValueRef.current = parentValue;
  }, [localValue, isLocallyModified]);

  const resetToParent = useCallback((parentValue: T) => {
    
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    
    setLocalValueState(parentValue);
    setIsLocallyModified(false);
    lastParentValueRef.current = parentValue;
  }, []);

  return {
    localValue,
    setLocalValue,
    syncWithParent,
    isLocallyModified,
    resetToParent
  };
};

/**
 * Specialized hook for managing local parameter state for indicators
 */
export interface UseLocalParameterStateOptions {
  indicatorId: string;
  parameters: Record<string, any>;
  onParameterChange?: (indicatorId: string, parameterName: string, value: any) => void;
}

export const useLocalParameterState = (options: UseLocalParameterStateOptions) => {
  const { indicatorId, parameters, onParameterChange } = options;
  
  const [localParameters, setLocalParameters] = useState<Record<string, any>>(parameters);
  const [modifiedParameters, setModifiedParameters] = useState<Set<string>>(new Set());

  const updateParameter = useCallback((parameterName: string, value: any) => {
    
    setLocalParameters(prev => ({
      ...prev,
      [parameterName]: value
    }));
    
    setModifiedParameters(prev => new Set(prev).add(parameterName));
    
    if (onParameterChange) {
      onParameterChange(indicatorId, parameterName, value);
    }
  }, [indicatorId, onParameterChange]);

  const syncWithParentParameters = useCallback((newParameters: Record<string, any>) => {
    
    // Only update parameters that haven't been locally modified
    const updatedParameters = { ...localParameters };
    let hasChanges = false;
    
    Object.keys(newParameters).forEach(key => {
      if (!modifiedParameters.has(key)) {
        updatedParameters[key] = newParameters[key];
        hasChanges = true;
      }
    });
    
    if (hasChanges) {
      setLocalParameters(updatedParameters);
    }
  }, [localParameters, modifiedParameters]);

  const resetParametersToParent = useCallback((newParameters: Record<string, any>) => {
    setLocalParameters(newParameters);
    setModifiedParameters(new Set());
  }, [indicatorId]);

  return {
    localParameters,
    updateParameter,
    syncWithParentParameters,
    resetParametersToParent,
    isParameterModified: (parameterName: string) => modifiedParameters.has(parameterName)
  };
};