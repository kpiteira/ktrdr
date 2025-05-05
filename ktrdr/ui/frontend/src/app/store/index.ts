import { configureStore, Middleware } from '@reduxjs/toolkit';
import uiReducer from './uiSlice';
import chartingReducer from '../../features/charting/store/chartingSlice';
import indicatorReducer from '../../features/charting/store/indicatorSlice';
import symbolsReducer from '../../features/symbols/store/symbolsSlice';

// Custom error handling middleware
const errorMiddleware: Middleware = () => (next) => (action: any) => {
  try {
    return next(action);
  } catch (error) {
    console.error('Error in redux action:', error);
    // You could also dispatch an action to track errors in state
    return next({
      type: 'ERROR_OCCURRED',
      error: error instanceof Error ? error.message : 'Unknown error',
      originalAction: action.type,
    });
  }
};

// Configure store with all reducers and middleware
export const store = configureStore({
  reducer: {
    ui: uiReducer,
    charting: chartingReducer,
    indicators: indicatorReducer,
    symbols: symbolsReducer,
  },
  middleware: (getDefaultMiddleware) => {
    const middleware = getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types in serializableCheck
        ignoredActions: ['ERROR_OCCURRED'],
      },
    });

    // Add development-only middleware
    if (import.meta.env.DEV || import.meta.env.VITE_DEBUG_MODE === 'true') {
      // Add console middleware in development - using console.debug for Verbose level
      middleware.push(() => (next) => (action) => {
        // Use console.debug which maps to Verbose level in Chrome DevTools
        console.debug('Action:', action);
        const result = next(action);
        console.debug('State after action:', store.getState());
        return result;
      });
    }

    // Add custom middleware
    middleware.push(errorMiddleware);

    return middleware;
  },
  devTools: import.meta.env.DEV || import.meta.env.VITE_DEBUG_MODE === 'true',
});

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;