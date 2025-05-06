import React, { useRef, useEffect } from 'react';
import { Header } from '../../app/Header';
import { Sidebar } from '../../app/Sidebar';
import { useTheme } from '../../app/ThemeProvider';
import { useAppSelector, useAppDispatch } from '../../hooks';
import { toggleSidebar } from '../../app/store/uiSlice';

// Create a static flag to track if we're already inside a MainLayout
// This prevents nested MainLayout components from causing duplicates
let isMainLayoutRendered = false;

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { theme } = useTheme();
  const sidebarOpen = useAppSelector(state => state.ui.sidebarOpen);
  const dispatch = useAppDispatch();
  const mainContentRef = useRef<HTMLDivElement>(null);
  
  // Flag to determine if this is a nested instance
  const isNested = useRef(isMainLayoutRendered);

  // Set the flag when this component is mounted
  useEffect(() => {
    if (!isMainLayoutRendered) {
      isMainLayoutRendered = true;
      // Reset the flag when the top-level instance unmounts
      return () => {
        isMainLayoutRendered = false;
      };
    }
  }, []);

  const toggleSidebarHandler = () => {
    dispatch(toggleSidebar());
  };

  // Use a more gentle approach to prevent infinite growth without breaking the layout
  useEffect(() => {
    // Don't use ResizeObserver as it might be too aggressive
    // Instead, add a one-time max-width style to limit growth while keeping interface visible
    
    if (mainContentRef.current) {
      // Get the window width as a safe maximum
      const safeMaxWidth = window.innerWidth;
      
      // Set a reasonable max-width that prevents infinite growth but allows normal layout
      mainContentRef.current.style.maxWidth = `${safeMaxWidth}px`;
      
      console.log('[MainLayout] Setting safe max width:', safeMaxWidth);
    }
    
    // Handle window resize events to update the max-width if needed
    const handleResize = () => {
      if (mainContentRef.current) {
        const safeMaxWidth = window.innerWidth;
        mainContentRef.current.style.maxWidth = `${safeMaxWidth}px`;
      }
    };
    
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // If this is a nested instance, just render the children directly
  // This prevents duplicate headers and sidebars
  if (isNested.current) {
    console.log('[MainLayout] Detected nested layout, rendering children only');
    return <>{children}</>;
  }

  // Otherwise render the full layout
  return (
    <div className={`main-layout ${theme === 'dark' ? 'theme-dark' : 'theme-light'}`}>
      <Header onMenuToggle={toggleSidebarHandler} />
      <div className="layout-container">
        <Sidebar />
        <main 
          ref={mainContentRef}
          className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}
          style={{ 
            width: '100%',
            boxSizing: 'border-box',
            // Less aggressive contain value that won't break normal layout
            contain: 'paint'
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};