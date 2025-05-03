/**
 * Application configuration
 * Central configuration file for the KTRDR frontend application
 */

// Environment-specific configurations (without the /api/v1 in baseUrl to avoid duplication)
const environments = {
  development: {
    api: {
      baseUrl: 'http://localhost:8000',
      prefix: '/api/v1'
    }
  },
  production: {
    api: {
      baseUrl: typeof window !== 'undefined' ? window.location.origin : '',
      prefix: '/api/v1'
    }
  },
  test: {
    api: {
      baseUrl: 'http://localhost:8000',
      prefix: '/api/v1'
    }
  },
  docker: {
    api: {
      baseUrl: 'http://backend:8000',
      prefix: '/api/v1'
    }
  }
};

// Get current environment from Vite
const currentEnv = import.meta.env.MODE || 'development';

// Detect Docker environment from environment variable 
const isDockerEnv = import.meta.env.VITE_DOCKER_ENV === 'true' || 
               (import.meta.env.VITE_API_BASE_URL && 
                import.meta.env.VITE_API_BASE_URL.includes('backend'));

// Choose environment configuration
const envConfig = isDockerEnv ? environments.docker : environments[currentEnv as keyof typeof environments];

// Use environment variable if provided
let apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

// If no environment variable, use the environment config
if (!apiBaseUrl) {
  apiBaseUrl = envConfig?.api?.baseUrl || environments.development.api.baseUrl;
}

// Process apiBaseUrl to remove /api/v1 if present to avoid duplication
if (apiBaseUrl && apiBaseUrl.endsWith('/api/v1')) {
  apiBaseUrl = apiBaseUrl.slice(0, -7); // Remove '/api/v1'
}

// For browsers, check if we need to use proxy instead of direct backend connection
// This addresses the issue where browser JS can't resolve "backend" hostname in Docker
if (typeof window !== 'undefined') {
  // If we're in a browser and the hostname is "backend", check if can be reached
  if (apiBaseUrl.includes('backend:8000')) {
    // For convenience in browser dev environments, auto-switch to localhost
    // when hostname = localhost
    if (window.location.hostname === 'localhost') {
      apiBaseUrl = 'http://localhost:8000';
    }
  }
}

// API configuration
const apiConfig = {
  baseUrl: apiBaseUrl,
  prefix: '/api/v1',
  timeout: 15000,
  defaultCacheTtl: 60 * 1000  // 1 minute
};

// Feature flags
const featureFlags = {
  enableDebugMode: import.meta.env.VITE_DEBUG_MODE === 'true' || import.meta.env.DEV,
  enableDevTools: import.meta.env.DEV, // Alias for consistency with existing components
  enableMockAPI: import.meta.env.VITE_MOCK_API === 'true' || false,
  enableApiMocks: import.meta.env.VITE_MOCK_API === 'true' || false, // Alias for compatibility
  enablePerformanceMonitoring: import.meta.env.PROD
};

// Environment detection
const environmentConfig = {
  environment: currentEnv,
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
  isTest: currentEnv === 'test',
  isDocker: isDockerEnv
};

// App information
const appInfo = {
  name: 'KTRDR Trading Platform',
  version: '0.1.0',
  description: 'Advanced trading platform for technical analysis and algo trading'
};

// Export the combined configuration
export const config = {
  app: appInfo,
  api: apiConfig,
  features: featureFlags,
  env: environmentConfig
};

// Export as default as well to ensure both import styles work
export default config;