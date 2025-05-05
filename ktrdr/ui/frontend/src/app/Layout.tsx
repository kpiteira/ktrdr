import { ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './ThemeProvider';
import { MainLayout } from './MainLayout';
import { NotificationProvider, NotificationContainer, DevModeIndicator } from '../components/common';
import Router from './Router';

interface LayoutProps {
  children?: ReactNode;
}

/**
 * Application layout component that wraps the entire app with necessary providers
 * and defines the overall structure (header, sidebar, content area)
 */
export const Layout = ({ children }: LayoutProps) => {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <NotificationProvider>
          <MainLayout>
            <Router />
            {children}
          </MainLayout>
          <NotificationContainer />
          <DevModeIndicator position="bottom-right" />
        </NotificationProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
};

export default Layout;