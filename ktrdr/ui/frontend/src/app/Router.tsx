import React, { Suspense } from 'react';
import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { routes } from './routes';

/**
 * Router component that provides routing for the application
 * Uses React Router v6 with route configuration from routes.tsx
 */
export const Router: React.FC = () => {
  // Create router instance with routes
  const router = createBrowserRouter(routes);
  
  return (
    <Suspense fallback={<LoadingSpinner fullPage message="Loading..." />}>
      <RouterProvider router={router} />
    </Suspense>
  );
};

export default Router;