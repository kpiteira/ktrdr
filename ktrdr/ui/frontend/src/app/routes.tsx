import React from 'react';
import { RouteObject } from 'react-router-dom';
import { MainLayout } from './MainLayout';

// Lazy-loaded components
const HomePage = React.lazy(() => import('../features/home/HomePage'));
const SymbolListPage = React.lazy(() => import('../features/symbols/SymbolListPage'));
const ChartPage = React.lazy(() => import('../features/charting/ChartPage'));

// Define routes with React Router v6 format
export const routes: RouteObject[] = [
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        path: '/',
        element: <HomePage />,
      },
      {
        path: '/symbols',
        element: <SymbolListPage />,
      },
      {
        path: '/charts/:symbol',
        element: <ChartPage />,
      },
      // Add additional routes as needed
    ],
  },
];

export default routes;