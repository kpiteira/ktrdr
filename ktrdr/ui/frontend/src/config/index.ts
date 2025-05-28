/**
 * Application configuration
 * Central configuration file for the KTRDR frontend application
 */

// Environment-specific configurations
const environments = {
  development: {
    api: {
      baseUrl: 'http://localhost:8000',  // Adjust if your backend runs on a different port
      prefix: '/api/v1'
    }
  },
  production: {
    api: {
      baseUrl: window.location.origin,  // Use same origin in production
      prefix: '/api/v1'
    }
  },
  test: {
    api: {
      baseUrl: 'http://localhost:8000',
      prefix: '/api/v1'
    }
  }
};

// Determine current environment
const currentEnv = process.env.NODE_ENV || 'development';

/**
 * Global configuration object
 */
export const config = {
  // Environment
  environment: currentEnv,
  isDevelopment: currentEnv === 'development',
  isProduction: currentEnv === 'production',
  isTest: currentEnv === 'test',
  
  // Application information
  app: {
    name: 'KTRDR Trading Platform',
    version: '0.1.0',
    description: 'Advanced trading platform for technical analysis and algo trading'
  },
  
  // API configuration
  api: {
    // Combine base URL and prefix for full API base URL
    baseUrl: environments[currentEnv as keyof typeof environments].api.baseUrl,
    prefix: environments[currentEnv as keyof typeof environments].api.prefix,
    
    // Timeouts
    defaultTimeout: 30000,  // 30 seconds
    
    // Cache settings
    defaultCacheTtl: 60 * 1000,  // 1 minute
  },
  
  // Feature flags
  features: {
    enableDevTools: currentEnv === 'development',
    enableApiMocks: false,
    enablePerformanceMonitoring: currentEnv === 'production'
  }
};

// Add a debug log to verify config values

// Export as default and named export to ensure it can be imported either way
export default config;