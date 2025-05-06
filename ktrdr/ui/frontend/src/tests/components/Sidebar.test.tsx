import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../../app/Sidebar';
import { MemoryRouter } from 'react-router-dom';

// Mock the hooks used by Sidebar
jest.mock('../../app/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light' }),
}));

jest.mock('../../app/hooks/useUIStore', () => ({
  useUIStore: () => ({
    sidebarOpen: true,
    toggleSidebar: jest.fn(),
  }),
}));

// Mock useLocation from react-router-dom
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: () => ({ pathname: '/symbols' }),
}));

describe('Sidebar Component', () => {
  test('renders sidebar with menu items', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );
    
    // Check if the sidebar title is rendered
    expect(screen.getByText('KTRDR')).toBeInTheDocument();
    
    // Check for main menu items
    expect(screen.getByText('Symbols')).toBeInTheDocument();
    expect(screen.getByText('Chart')).toBeInTheDocument();
    expect(screen.getByText('Data Transform')).toBeInTheDocument();
    expect(screen.getByText('Strategies')).toBeInTheDocument();
    expect(screen.getByText('Data Selection')).toBeInTheDocument();
  });

  test('adds active class to active menu item', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );
    
    // Since we mocked useLocation to return pathname: '/symbols'
    // The Symbols menu item should have the active class
    const symbolsItem = screen.getByText('Symbols').closest('.menu-item');
    expect(symbolsItem).toHaveClass('active');
    
    // Other items should not have the active class
    const chartItem = screen.getByText('Chart').closest('.menu-item');
    expect(chartItem).not.toHaveClass('active');
  });
});