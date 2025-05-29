import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { config } from '../config';
import { createLogger } from '../utils/logger';

// Create logger for API client
const logger = createLogger('API');

// When in development, we'll use relative URLs to leverage the Vite dev server proxy
const useRelativeUrls = import.meta.env.DEV;

// Create an axios instance with default configuration
const axiosInstance = axios.create({
  // In development with a proxy, use relative URLs instead of absolute URLs with hostnames
  baseURL: useRelativeUrls ? '' : config.api.baseUrl,
  timeout: config.api.timeout || 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for API calls
axiosInstance.interceptors.request.use(
  (config) => {
    // Log at INFO level - browser will show this when INFO is enabled
    logger.info(`Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for API calls
axiosInstance.interceptors.response.use(
  (response) => {
    // Log successful responses at INFO level for visibility
    logger.info(`Response (${response.status}): ${response.config.method?.toUpperCase()} ${response.config.url}`);
    return response;
  },
  (error) => {
    logger.error('Request failed:', error.message);
    if (error.config) {
      logger.error(`Failed request details: ${error.config.method?.toUpperCase()} ${error.config.baseURL}${error.config.url}`);
    }
    return Promise.reject(error);
  }
);

interface ApiOptions {
  signal?: AbortSignal;
  cacheTtl?: number;
}

/**
 * API client for making HTTP requests to the backend
 */
class ApiClient {
  private apiPrefix: string;

  constructor() {
    this.apiPrefix = config.api.prefix || '/api/v1';
    
    // Ensure API prefix starts with a slash and doesn't end with one
    if (!this.apiPrefix.startsWith('/')) {
      this.apiPrefix = '/' + this.apiPrefix;
    }
    if (this.apiPrefix.endsWith('/')) {
      this.apiPrefix = this.apiPrefix.slice(0, -1);
    }
  }

  /**
   * Create a correct path with the API prefix
   */
  private getFullPath(endpoint: string): string {
    // If endpoint already includes the prefix, don't add it again
    if (endpoint.startsWith(this.apiPrefix)) {
      return endpoint;
    }
    
    // Remove leading slash from endpoint if present
    if (endpoint.startsWith('/')) {
      endpoint = endpoint.slice(1);
    }
    
    // Combine the API prefix with the cleaned endpoint
    return `${this.apiPrefix}/${endpoint}`;
  }

  /**
   * Make a GET request to the API
   * @param endpoint The API endpoint
   * @param params Query parameters
   * @param options Additional request options
   * @returns The response data
   */
  async get<T = any>(endpoint: string, params?: any, options?: ApiOptions): Promise<T> {
    const requestConfig: AxiosRequestConfig = {
      params,
      signal: options?.signal,
    };

    try {
      const fullPath = this.getFullPath(endpoint);
      const response: AxiosResponse<T> = await axiosInstance.get(fullPath, requestConfig);
      return response.data;
    } catch (error) {
      logger.error(`GET ${endpoint} failed:`, error);
      throw error;
    }
  }

  /**
   * Make a POST request to the API
   * @param endpoint The API endpoint
   * @param data Request body data
   * @param options Additional request options
   * @returns The response data
   */
  async post<T = any>(endpoint: string, data?: any, options?: ApiOptions): Promise<T> {
    const requestConfig: AxiosRequestConfig = {
      signal: options?.signal,
    };

    try {
      const fullPath = this.getFullPath(endpoint);
      const response: AxiosResponse<T> = await axiosInstance.post(fullPath, data, requestConfig);
      return response.data;
    } catch (error) {
      logger.error(`POST ${endpoint} failed:`, error);
      throw error;
    }
  }
}

// Export a singleton instance
export const apiClient = new ApiClient();