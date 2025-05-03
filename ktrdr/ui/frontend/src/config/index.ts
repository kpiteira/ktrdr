/**
 * Application configuration
 * Provides type-safe access to environment variables
 */

interface AppConfig {
  api: {
    baseUrl: string;
  };
  app: {
    name: string;
    version: string;
  };
  debug: boolean;
}

export const config: AppConfig = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  },
  app: {
    name: import.meta.env.VITE_APP_NAME || 'KTRDR Trading Platform',
    version: import.meta.env.VITE_APP_VERSION || '0.1.0',
  },
  debug: import.meta.env.VITE_DEBUG_MODE === 'true',
};

export default config;