import React from 'react';
import { useTheme } from './ThemeProvider';
import { config } from '@/config';
import { useAppDispatch } from '@/store/hooks';
import { toggleSidebar } from '@/store/slices/uiSlice';

// Info level logging for configuration
console.log('Config loaded in Header:', config);

// Fallback values for app information if missing in config
const appName = config.app?.name || 'KTRDR Trading Platform';
const appVersion = config.app?.version || '0.1.0';

interface HeaderProps {
  onMenuToggle?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle }) => {
  const { theme, toggleTheme } = useTheme();
  const dispatch = useAppDispatch();

  const handleMenuToggle = () => {
    if (onMenuToggle) {
      onMenuToggle();
    } else {
      dispatch(toggleSidebar());
    }
  };

  return (
    <header className={`header ${theme === 'dark' ? 'header-dark' : 'header-light'}`}>
      <div className="header-left">
        <button className="menu-toggle" onClick={handleMenuToggle} aria-label="Toggle sidebar">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 18H21V16H3V18ZM3 13H21V11H3V13ZM3 6V8H21V6H3Z" fill="currentColor" />
          </svg>
        </button>
        <h1 className="app-title">{appName}</h1>
      </div>
      <div className="header-right">
        <span className="app-version">v{appVersion}</span>
        <button 
          className="theme-toggle" 
          onClick={toggleTheme} 
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 23C18.0751 23 23 18.0751 23 12C23 5.92487 18.0751 1 12 1C5.92487 1 1 5.92487 1 12C1 18.0751 5.92487 23 12 23ZM17 15C17.476 15 17.9408 14.9525 18.3901 14.862C17.296 17.3011 14.8464 19 12 19C8.13401 19 5 15.866 5 12C5 8.13401 8.13401 5 12 5C14.8464 5 17.296 6.69893 18.3901 9.13803C17.9408 9.04746 17.476 9 17 9C13.6863 9 11 11.6863 11 15C11 18.3137 13.6863 21 17 21C20.3137 21 23 18.3137 23 15H17Z" fill="currentColor" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 17C14.7614 17 17 14.7614 17 12C17 9.23858 14.7614 7 12 7C9.23858 7 7 9.23858 7 12C7 14.7614 9.23858 17 12 17ZM12 20C8.13401 20 5 16.866 5 13H1C1 19.0751 5.92487 24 12 24C18.0751 24 23 19.0751 23 13H19C19 16.866 15.866 20 12 20Z" fill="currentColor" />
            </svg>
          )}
        </button>
      </div>
    </header>
  );
};