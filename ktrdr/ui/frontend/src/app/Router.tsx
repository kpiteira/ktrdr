import { Routes, Route } from 'react-router-dom';
import { allRoutes } from './routes';

/**
 * Router component that defines all application routes
 * Uses the centralized routes definition
 */
export const Router = () => {
  return (
    <Routes>
      {allRoutes.map(route => (
        <Route 
          key={route.path}
          path={route.path}
          element={route.element}
        />
      ))}
    </Routes>
  );
};

export default Router;