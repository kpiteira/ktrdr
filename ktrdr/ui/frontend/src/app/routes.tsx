import React from 'react';
import { HomeIcon, ChartIcon, DataIcon, StrategyIcon } from './icons';

// Define the MenuItem type which is used by the Sidebar
export interface MenuItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  path?: string;
  items?: MenuItem[];
}

// Define the routes for sidebar navigation
export const routes: MenuItem[] = [
  {
    id: 'home',
    label: 'Home',
    path: '/home',
    icon: <HomeIcon />,
  },
  {
    id: 'symbols',
    label: 'Symbols',
    path: '/symbols',
    icon: <ChartIcon />,
  },
  {
    id: 'charts',
    label: 'Charts',
    path: '/charts',
    icon: <ChartIcon />,
  },
  {
    id: 'data-transform',
    label: 'Data Transformation',
    path: '/data-transform',
    icon: <DataIcon />,
  },
  {
    id: 'strategies',
    label: 'Strategies',
    path: '/strategies',
    icon: <StrategyIcon />,
  },
];

// Future tasks will add more routes
export default routes;