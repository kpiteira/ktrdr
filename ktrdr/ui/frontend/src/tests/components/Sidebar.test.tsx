import React from 'react';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '../../app/Sidebar';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, test, expect } from 'vitest';

// Mock the hooks used by Sidebar
vi.mock('../../app/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light' }),
}));

vi.mock('../../app/hooks/useUIStore', () => ({
  useUIStore: () => ({
    sidebarOpen: true,
    toggleSidebar: vi.fn(),
  }),
}));

// Mock react-router-dom with a more complete mock
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => ({ pathname: '/symbols' }),
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate" data-to={to}>Navigate to {to}</div>,
  };
});

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