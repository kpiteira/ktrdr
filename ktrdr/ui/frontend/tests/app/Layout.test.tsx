import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { MainLayout } from '../../src/components/layouts/MainLayout';
import { ThemeProvider } from '../../src/app/ThemeProvider';
import { Provider } from 'react-redux';
import configureStore from 'redux-mock-store';

// Mock the Header and Sidebar components
jest.mock('../../src/app/Header', () => ({
  Header: () => <div data-testid="mock-header">Header</div>
}));

jest.mock('../../src/app/Sidebar', () => ({
  Sidebar: () => <div data-testid="mock-sidebar">Sidebar</div>
}));

// Create a mock store
const mockStore = configureStore([]);
const store = mockStore({
  ui: {
    sidebarOpen: true
  }
});

describe('MainLayout', () => {
  test('renders header, sidebar and main content', () => {
    render(
      <Provider store={store}>
        <ThemeProvider>
          <MemoryRouter>
            <MainLayout>
              <div data-testid="main-content">Main Content</div>
            </MainLayout>
          </MemoryRouter>
        </ThemeProvider>
      </Provider>
    );

    // Check if header and sidebar are rendered
    expect(screen.getByTestId('mock-header')).toBeInTheDocument();
    expect(screen.getByTestId('mock-sidebar')).toBeInTheDocument();
    
    // Check if main content is rendered
    expect(screen.getByTestId('main-content')).toBeInTheDocument();
    expect(screen.getByText('Main Content')).toBeInTheDocument();
  });

  test('handles nested layouts correctly', () => {
    // First render a MainLayout
    render(
      <Provider store={store}>
        <ThemeProvider>
          <MemoryRouter>
            <MainLayout>
              <div data-testid="outer-content">
                {/* Now render a nested MainLayout */}
                <MainLayout>
                  <div data-testid="inner-content">Nested Content</div>
                </MainLayout>
              </div>
            </MainLayout>
          </MemoryRouter>
        </ThemeProvider>
      </Provider>
    );

    // The header and sidebar should only be rendered once (from the outer layout)
    expect(screen.getAllByTestId('mock-header').length).toBe(1);
    expect(screen.getAllByTestId('mock-sidebar').length).toBe(1);
    
    // Both outer and inner content should be rendered
    expect(screen.getByTestId('outer-content')).toBeInTheDocument();
    expect(screen.getByTestId('inner-content')).toBeInTheDocument();
    expect(screen.getByText('Nested Content')).toBeInTheDocument();
  });
});