import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAppSelector, useAppDispatch } from '../hooks';
import { setTheme } from './store/uiSlice';

// Define theme modes
type ThemeMode = 'light' | 'dark';

// Define theme context type
interface ThemeContextType {
  theme: ThemeMode;
  toggleTheme: () => void;
}

// Create the theme context with default values
const ThemeContext = createContext<ThemeContextType>({
  theme: 'light',
  toggleTheme: () => {},
});

// Custom hook to use the theme context
export const useTheme = () => useContext(ThemeContext);

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  // Use Redux for theme state
  const themeFromRedux = useAppSelector(state => state.ui.theme);
  const dispatch = useAppDispatch();
  
  // Initialize theme from localStorage or system preference
  const [theme, setLocalTheme] = useState<ThemeMode>(() => {
    // First try to use redux state
    if (themeFromRedux) {
      return themeFromRedux;
    }
    
    // Then try localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme && (savedTheme === 'dark' || savedTheme === 'light')) {
      return savedTheme as ThemeMode;
    }
    
    // Finally check system preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  // Sync local state with Redux
  useEffect(() => {
    if (theme !== themeFromRedux) {
      dispatch(setTheme(theme));
    }
  }, [theme, themeFromRedux, dispatch]);

  // Update localStorage when theme changes
  useEffect(() => {
    localStorage.setItem('theme', theme);
    
    // Apply theme to document
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // Toggle between light and dark mode
  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setLocalTheme(newTheme);
    dispatch(setTheme(newTheme));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};