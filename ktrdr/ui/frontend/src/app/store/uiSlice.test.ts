import { describe, it, expect, beforeEach } from 'vitest';
import { configureStore } from '@reduxjs/toolkit';
import uiReducer, { 
  setTheme, 
  toggleSidebar, 
  setCurrentView,
  updateChartSettings, 
  ThemeMode 
} from '@/app/store/uiSlice';

describe('uiSlice', () => {
  let store: ReturnType<typeof configureStore>;

  beforeEach(() => {
    // Create a fresh store for each test
    store = configureStore({
      reducer: { ui: uiReducer }
    });
  });

  describe('Theme control', () => {
    it('should handle setTheme', () => {
      // Act - dispatch the action to set theme to dark
      store.dispatch(setTheme('dark'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.theme).toBe('dark');
      
      // Act - dispatch the action to set theme to light
      store.dispatch(setTheme('light'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.theme).toBe('light');
    });
  });

  describe('Sidebar control', () => {
    it('should handle toggleSidebar', () => {
      // Check initial state (should be open by default)
      expect(store.getState().ui.sidebarOpen).toBe(true);
      
      // Act - dispatch the action to toggle sidebar
      store.dispatch(toggleSidebar());
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.sidebarOpen).toBe(false);
      
      // Act - dispatch the action to toggle sidebar again
      store.dispatch(toggleSidebar());
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.sidebarOpen).toBe(true);
    });
  });

  describe('View control', () => {
    it('should handle setCurrentView', () => {
      // Act - dispatch the action to set current view
      store.dispatch(setCurrentView('analysis'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.currentView).toBe('analysis');
      
      // Act - dispatch the action to set another view
      store.dispatch(setCurrentView('trading'));
      
      // Assert - check that the state was updated correctly
      expect(store.getState().ui.currentView).toBe('trading');
    });
  });

  describe('Chart settings', () => {
    it('should handle updateChartSettings', () => {
      // Check initial state for chart settings
      expect(store.getState().ui.chartSettings).toEqual({
        height: 500,
        showVolume: true,
        showGridlines: true,
      });
      
      // Act - dispatch the action to update part of chart settings
      store.dispatch(updateChartSettings({ height: 600 }));
      
      // Assert - check that only the specified setting was updated
      expect(store.getState().ui.chartSettings).toEqual({
        height: 600,
        showVolume: true,
        showGridlines: true,
      });
      
      // Act - dispatch the action to update multiple settings
      store.dispatch(updateChartSettings({ 
        showVolume: false,
        showGridlines: false
      }));
      
      // Assert - check that multiple settings were updated
      expect(store.getState().ui.chartSettings).toEqual({
        height: 600,
        showVolume: false,
        showGridlines: false,
      });
    });
  });

  describe('Integration tests', () => {
    it('should handle multiple UI state changes', () => {
      // Act - dispatch multiple actions to change UI state
      store.dispatch(setTheme('dark'));
      store.dispatch(toggleSidebar());
      store.dispatch(setCurrentView('analysis'));
      store.dispatch(updateChartSettings({ height: 700 }));
      
      // Assert - check the final state after all actions
      const uiState = store.getState().ui;
      expect(uiState.theme).toBe('dark');
      expect(uiState.sidebarOpen).toBe(false);
      expect(uiState.currentView).toBe('analysis');
      expect(uiState.chartSettings.height).toBe(700);
    });
  });
});