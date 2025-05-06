import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { HomePage } from '../features/home/HomePage';

// Import existing pages
import DataSelectionPage from '../pages/DataSelectionPage';
import ChartPage from '../pages/ChartPage';
import SymbolsPage from '../pages/SymbolsPage';
import DataTransformPage from '../pages/DataTransformPage';
import StrategiesPage from '../pages/StrategiesPage';

/**
 * Router component that renders routes for the application
 * The BrowserRouter is already provided in the Layout component
 */
export const Router: React.FC = () => {
  return (
    <Routes>
      {/* Default route redirects to home */}
      <Route path="/" element={<Navigate to="/home" replace />} />
      
      {/* Home route */}
      <Route path="/home" element={<HomePage />} />
      
      {/* Connect existing pages from the application */}
      <Route path="/symbols" element={<SymbolsPage />} />
      <Route path="/charts" element={<ChartPage />} />
      <Route path="/data-selection" element={<DataSelectionPage />} />
      <Route path="/data-transform" element={<DataTransformPage />} />
      <Route path="/strategies" element={<StrategiesPage />} />
      
      {/* Catch-all route for 404 */}
      <Route path="*" element={
        <div className="p-6">
          <h1 className="text-2xl font-bold mb-4">Page Not Found</h1>
          <p>The page you requested does not exist.</p>
        </div>
      } />
    </Routes>
  );
};

export default Router;