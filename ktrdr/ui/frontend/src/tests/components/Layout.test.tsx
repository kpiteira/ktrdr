import React from 'react';
import { render, screen } from '@testing-library/react';
import { Layout } from '../../app/Layout';

// Mock the components and providers used by Layout
jest.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }: { children: React.ReactNode }) => <div data-testid="browser-router">{children}</div>,
}));

jest.mock('../../app/ThemeProvider', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <div data-testid="theme-provider">{children}</div>,
}));

jest.mock('../../app/MainLayout', () => ({
  MainLayout: ({ children }: { children: React.ReactNode }) => <div data-testid="main-layout">{children}</div>,
}));

jest.mock('../../app/Router', () => ({
  __esModule: true,
  default: () => <div data-testid="router">Router Content</div>,
}));

jest.mock('../../components/common', () => ({
  NotificationProvider: ({ children }: { children: React.ReactNode }) => <div data-testid="notification-provider">{children}</div>,
  NotificationContainer: () => <div data-testid="notification-container">Notifications</div>,
  DevModeIndicator: () => <div data-testid="dev-mode-indicator">Dev Mode</div>,
}));

describe('Layout Component', () => {
  test('renders with all required providers and components', () => {
    render(<Layout />);
    
    // Check if all the main components are rendered
    expect(screen.getByTestId('browser-router')).toBeInTheDocument();
    expect(screen.getByTestId('theme-provider')).toBeInTheDocument();
    expect(screen.getByTestId('notification-provider')).toBeInTheDocument();
    expect(screen.getByTestId('main-layout')).toBeInTheDocument();
    expect(screen.getByTestId('router')).toBeInTheDocument();
    expect(screen.getByTestId('notification-container')).toBeInTheDocument();
    expect(screen.getByTestId('dev-mode-indicator')).toBeInTheDocument();
  });

  test('renders children when provided', () => {
    render(
      <Layout>
        <div data-testid="child-content">Child Content</div>
      </Layout>
    );
    
    expect(screen.getByTestId('child-content')).toBeInTheDocument();
    expect(screen.getByText('Child Content')).toBeInTheDocument();
  });
});