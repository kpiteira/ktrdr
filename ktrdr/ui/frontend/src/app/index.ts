/**
 * App module exports
 * Centralizes exports of all app-level components
 */

export { default as Layout } from './Layout';
export { default as Router } from './Router';
export { default as MainLayout } from './MainLayout';
export { default as Header } from './Header';
export { default as Sidebar } from './Sidebar';

import { ThemeProvider, useTheme } from './ThemeProvider';
import { useUI } from './hooks/useUI';

export {
  ThemeProvider,
  useTheme,
  useUI
};