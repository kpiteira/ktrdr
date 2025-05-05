import { Routes, Route, Navigate } from 'react-router-dom';
import { 
  SymbolsPage, 
  ChartPage, 
  StrategiesPage,
  DataSelectionPage 
} from '../pages';
// Import DataTransformPage directly to avoid TypeScript module resolution issues
import DataTransformPage from '../pages/DataTransformPage';

/**
 * Router component that defines all application routes
 */
export const Router = () => {
  return (
    <Routes>
      <Route path="/symbols" element={<SymbolsPage />} />
      <Route path="/chart" element={<ChartPage />} />
      <Route path="/data-transform" element={<DataTransformPage />} />
      <Route path="/strategies" element={<StrategiesPage />} />
      <Route path="/data-selection" element={<DataSelectionPage />} />
      <Route path="/" element={<Navigate to="/symbols" replace />} />
    </Routes>
  );
};

export default Router;