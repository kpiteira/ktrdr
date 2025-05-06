import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../../src/app/Sidebar';
import { ThemeProvider } from '../../src/app/ThemeProvider';
import * as routesModule from '../../src/app/routes';

// Mock the useUIStore hook
jest.mock('../../src/app/hooks/useUIStore', () => ({
  useUIStore: () => ({
    sidebarOpen: true,
    toggleSidebar: jest.fn()
  })
}));

describe('Sidebar', () => {
  test('renders navigation items from routes', () => {
    // Create a spy on the routes import to check if it's being used
    const routesSpy = jest.spyOn(routesModule, 'routes', 'get').mockReturnValue([
      {
        id: 'home',
        label: 'Home',
        path: '/home',
      },
      {
        id: 'symbols',
        label: 'Symbols',
        path: '/symbols',
      }
    ]);

    render(
      <ThemeProvider>
        <MemoryRouter>
          <Sidebar />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Verify the routes are being used
    expect(routesSpy).toHaveBeenCalled();
    
    // Check if navigation items are rendered
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Symbols')).toBeInTheDocument();
  });

  test('highlights active route based on location', () => {
    jest.spyOn(routesModule, 'routes', 'get').mockReturnValue([
      {
        id: 'home',
        label: 'Home',
        path: '/home',
      },
      {
        id: 'symbols',
        label: 'Symbols',
        path: '/symbols',
      }
    ]);

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/symbols']}>
          <Sidebar />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Get all menu items
    const homeLink = screen.getByText('Home').closest('a');
    const symbolsLink = screen.getByText('Symbols').closest('a');
    
    // The symbols link should have the active class
    expect(symbolsLink?.parentElement).toHaveClass('active');
    expect(homeLink?.parentElement).not.toHaveClass('active');
  });

  test('calls toggleSidebar when close button is clicked', () => {
    const mockToggleSidebar = jest.fn();
    
    // Override the mock to provide our test function
    jest.mock('../../src/app/hooks/useUIStore', () => ({
      useUIStore: () => ({
        sidebarOpen: true,
        toggleSidebar: mockToggleSidebar
      })
    }));

    render(
      <ThemeProvider>
        <MemoryRouter>
          <Sidebar />
        </MemoryRouter>
      </ThemeProvider>
    );

    // Click the close button
    const closeButton = screen.getByLabelText('Close sidebar');
    fireEvent.click(closeButton);
    
    // The mock function should have been called
    expect(mockToggleSidebar).toHaveBeenCalled();
  });
});