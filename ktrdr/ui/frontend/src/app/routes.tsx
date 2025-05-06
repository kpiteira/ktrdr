import React from 'react';
import { 
  SymbolsPage, 
  ChartPage, 
  StrategiesPage,
  DataSelectionPage 
} from '../pages';
import DataTransformPage from '../pages/DataTransformPage';
import { Navigate } from 'react-router-dom';

/**
 * Central definition of application routes
 * Used by both Router.tsx and Sidebar.tsx to keep navigation DRY
 */

// SVG icons for the sidebar navigation
const icons = {
  symbols: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M9 5H7V7H5V9H7V11H9V9H11V7H9V5zM19 11h-2V9h-2v2h-2v2h2v2h2v-2h2v-2zM21 3H3C1.9 3 1 3.9 1 5v14c0 1.1 0.9 2 2 2h18c1.1 0 2-0.9 2-2V5c0-1.1-0.9-2-2-2zm0 16.01H3V4.99h18v14.02z" fill="currentColor" />
    </svg>
  ),
  chart: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3.5 18.49L9.5 12.48L13.5 16.48L22 6.92001L20.59 5.51001L13.5 13.48L9.5 9.48001L2 16.99L3.5 18.49Z" fill="currentColor" />
    </svg>
  ),
  dataTransform: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM9 17H7V10H9V17ZM13 17H11V7H13V17ZM17 17H15V13H17V17Z" fill="currentColor" />
    </svg>
  ),
  strategies: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M15.9 18.45l6-6-6-6-1.4 1.4 3.6 3.6H2v2h16.1l-3.6 3.6 1.4 1.4zM20 6h2v12h-2z" fill="currentColor" />
    </svg>
  ),
  dataSelection: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z" fill="currentColor" />
    </svg>
  )
};

// Application routes used for both routing and navigation
export const routes = [
  { 
    id: 'symbols',
    path: '/symbols', 
    label: 'Symbols',
    element: <SymbolsPage />,
    icon: icons.symbols
  },
  { 
    id: 'chart',
    path: '/chart', 
    label: 'Chart',
    element: <ChartPage />,
    icon: icons.chart
  },
  { 
    id: 'data-transform',
    path: '/data-transform', 
    label: 'Data Transform',
    element: <DataTransformPage />,
    icon: icons.dataTransform
  },
  { 
    id: 'strategies',
    path: '/strategies', 
    label: 'Strategies',
    element: <StrategiesPage />,
    icon: icons.strategies
  },
  { 
    id: 'data-selection',
    path: '/data-selection', 
    label: 'Data Selection',
    element: <DataSelectionPage />,
    icon: icons.dataSelection
  }
];

// Special routes (like redirects) that don't appear in navigation
export const specialRoutes = [
  {
    path: '/',
    element: <Navigate to="/symbols" replace />
  }
];

// Complete routes including both navigation routes and special routes
export const allRoutes = [...routes, ...specialRoutes];