/**
 * Simple store creation utility for single source of truth state management.
 * This provides a minimal Redux-like pattern without the complexity.
 */

export type Listener<T> = (state: T) => void;
export type Updater<T> = (prev: T) => T;

export interface Store<T> {
  getState: () => T;
  setState: (updater: Updater<T>) => void;
  subscribe: (listener: Listener<T>) => () => void;
}

/**
 * Create a simple store with subscription capabilities.
 * 
 * @param initialState - The initial state of the store
 * @returns Store instance with getState, setState, and subscribe methods
 */
export function createStore<T>(initialState: T): Store<T> {
  let state = initialState;
  const listeners = new Set<Listener<T>>();
  
  return {
    getState: () => state,
    
    setState: (updater: Updater<T>) => {
      const newState = updater(state);
      // Only notify if state actually changed
      if (newState !== state) {
        state = newState;
        listeners.forEach(listener => listener(state));
      }
    },
    
    subscribe: (listener: Listener<T>) => {
      listeners.add(listener);
      // Return unsubscribe function
      return () => listeners.delete(listener);
    }
  };
}