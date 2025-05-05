import { useDispatch, useSelector } from 'react-redux';
import { RootState, AppDispatch } from '../store';
import { setTheme, toggleSidebar, setCurrentView, updateChartSettings, ThemeMode } from '../store/uiSlice';

/**
 * Hook for accessing and managing UI state
 */
export const useUI = () => {
  const dispatch = useDispatch<AppDispatch>();
  const {
    theme,
    sidebarOpen,
    currentView,
    chartSettings
  } = useSelector((state: RootState) => state.ui);

  const setThemeMode = (newTheme: ThemeMode) => {
    dispatch(setTheme(newTheme));
  };

  const toggleSidebarVisibility = () => {
    dispatch(toggleSidebar());
  };

  const setView = (view: string) => {
    dispatch(setCurrentView(view));
  };

  const updateChartConfig = (settings: Partial<typeof chartSettings>) => {
    dispatch(updateChartSettings(settings));
  };

  return {
    theme,
    sidebarOpen,
    currentView,
    chartSettings,
    setTheme: setThemeMode,
    toggleSidebar: toggleSidebarVisibility,
    setCurrentView: setView,
    updateChartSettings: updateChartConfig
  };
};