import React from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useTheme } from './ThemeProvider';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { toggleSidebar } from '@/store/slices/uiSlice';

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const { theme } = useTheme();
  const sidebarOpen = useAppSelector(state => state.ui.sidebarOpen);
  const dispatch = useAppDispatch();

  const toggleSidebarHandler = () => {
    dispatch(toggleSidebar());
  };

  return (
    <div className={`main-layout ${theme === 'dark' ? 'theme-dark' : 'theme-light'}`}>
      <Header onMenuToggle={toggleSidebarHandler} />
      <div className="layout-container">
        <Sidebar />
        <main className={`main-content ${sidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
          {children}
        </main>
      </div>
    </div>
  );
};