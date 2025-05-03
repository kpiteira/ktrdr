/**
 * Core API client implementation
 * Provides a centralized client for making API requests with error handling and retries
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { config } from '../config';
import { KTRDRApiError } from './errors';
import { ApiResponse } from './types';
import { apiCache } from './cache';

/**
 * Retry configuration
 */
interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffFactor: number;
  retryableStatusCodes: number[];
}

/**
 * Request options
 */
export interface RequestOptions {
  forceRefresh?: boolean;
  cacheTtl?: number;
  retry?: boolean | Partial<RetryConfig>;
}

/**
 * Default retry configuration
 */
const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelayMs: 300,
  maxDelayMs: 3000,
  backoffFactor: 2,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504]
};

/**
 * Core API client for making requests to the KTRDR API
 */
export class ApiClient {
  private axiosInstance: AxiosInstance;
  private retryConfig: RetryConfig;
  private apiPrefix: string;

  /**
   * Create a new API client
   */
  constructor() {
    this.retryConfig = DEFAULT_RETRY_CONFIG;
    this.apiPrefix = config.api.prefix;
    
    // Log API configuration for debugging
    console.log('API Client Configuration:', {
      baseURL: config.api.baseUrl,
      apiPrefix: this.apiPrefix
    });
    
    // Create Axios instance with default configuration
    this.axiosInstance = axios.create({
      baseURL: config.api.baseUrl,
      timeout: config.api.defaultTimeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    });
    
    // Add request interceptor for logging and authentication
    this.axiosInstance.interceptors.request.use(
      (config) => {
        // Add authentication token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers['Authorization'] = `Bearer ${token}`;
        }
        
        // Add trace ID for request tracking
        config.headers['X-Request-ID'] = this.generateRequestId();
        
        // Log outgoing request for debugging
        console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, 
          { params: config.params, data: config.data });
        
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    // Add response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => {
        // Log successful response for debugging
        console.log(`API Response: ${response.status} ${response.config.url}`, 
          { data: response.data });
        return response;
      },
      (error: AxiosError) => {
        console.error('API Error:', error);
        return Promise.reject(this.handleAxiosError(error));
      }
    );
  }
  
  /**
   * Generate a unique request ID
   */
  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
  }
  
  /**
   * Handle Axios errors and convert to KTRDRApiError
   */
  private handleAxiosError(error: AxiosError): KTRDRApiError {
    if (error.response) {
      // The request was made and the server responded with an error status
      const responseData = error.response.data as any;
      
      // If server returned a structured error in the expected format
      if (responseData && responseData.error) {
        return KTRDRApiError.fromApiError(responseData.error);
      }
      
      // Server responded but with an unexpected format
      return new KTRDRApiError(
        `HTTP_${error.response.status}`,
        `Request failed with status code ${error.response.status}`,
        { statusText: error.response.statusText }
      );
    } else if (error.request) {
      // The request was made but no response was received
      if (error.code === 'ECONNABORTED') {
        return KTRDRApiError.timeoutError();
      }
      
      return new KTRDRApiError(
        'REQUEST_ERROR',
        'No response received from server',
        { details: error.message }
      );
    } else {
      // Something happened in setting up the request that triggered an Error
      return KTRDRApiError.networkError(error);
    }
  }
  
  /**
   * Process API response and extract data
   */
  private processResponse<T>(response: AxiosResponse): T {
    const data = response.data as ApiResponse<T>;
    
    if (!data.success) {
      if (data.error) {
        throw KTRDRApiError.fromApiError(data.error);
      }
      throw KTRDRApiError.unexpectedResponseError();
    }
    
    if (data.data === undefined) {
      throw KTRDRApiError.unexpectedResponseError();
    }
    
    return data.data;
  }
  
  /**
   * Perform exponential backoff delay
   */
  private async delay(retryCount: number): Promise<void> {
    const delayMs = Math.min(
      this.retryConfig.initialDelayMs * Math.pow(this.retryConfig.backoffFactor, retryCount),
      this.retryConfig.maxDelayMs
    );
    
    return new Promise(resolve => setTimeout(resolve, delayMs));
  }
  
  /**
   * Check if a request should be retried based on error
   */
  private shouldRetry(error: unknown, retryCount: number, retryConfig: RetryConfig): boolean {
    if (retryCount >= retryConfig.maxRetries) {
      return false;
    }
    
    if (error instanceof KTRDRApiError) {
      if (error.code === 'NETWORK_ERROR' || error.code === 'TIMEOUT_ERROR') {
        return true;
      }
      
      // Check for specific HTTP status codes
      if (error.code.startsWith('HTTP_')) {
        const statusCode = parseInt(error.code.substring(5), 10);
        return retryConfig.retryableStatusCodes.includes(statusCode);
      }
    }
    
    return false;
  }
  
  /**
   * Make a request with retry and caching
   */
  private async requestWithRetry<T>(
    method: string,
    url: string,
    config: AxiosRequestConfig = {},
    options: RequestOptions = {}
  ): Promise<T> {
    const cacheKey = apiCache.generateKey(
      url,
      { method, ...config.params, ...config.data }
    );
    
    // Check cache if not forcing refresh
    if (!options.forceRefresh) {
      const cachedData = apiCache.get<T>(cacheKey, options.cacheTtl);
      if (cachedData) {
        return cachedData;
      }
    }
    
    // Determine retry configuration
    let retryEnabled = options.retry !== undefined ? options.retry : true;
    let retryConfig = { ...this.retryConfig };
    
    if (typeof options.retry === 'object') {
      retryConfig = { ...retryConfig, ...options.retry };
    }
    
    // Execute request with retry logic
    let retryCount = 0;
    
    while (true) {
      try {
        const response = await this.axiosInstance.request<ApiResponse<T>>({
          method,
          url,
          ...config
        });
        
        const data = this.processResponse<T>(response);
        
        // Cache successful response
        apiCache.set(cacheKey, data);
        
        return data;
      } catch (error) {
        const shouldRetry = retryEnabled && this.shouldRetry(error, retryCount, retryConfig);
        
        if (!shouldRetry) {
          throw error;
        }
        
        retryCount++;
        await this.delay(retryCount);
      }
    }
  }
  
  /**
   * Perform a GET request
   */
  async get<T>(
    url: string,
    params?: Record<string, any>,
    options?: RequestOptions
  ): Promise<T> {
    // Ensure url starts with API prefix
    const fullUrl = this.ensureApiPrefix(url);
    return this.requestWithRetry<T>('GET', fullUrl, { params }, options);
  }
  
  /**
   * Perform a POST request
   */
  async post<T>(
    url: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    // Ensure url starts with API prefix
    const fullUrl = this.ensureApiPrefix(url);
    return this.requestWithRetry<T>('POST', fullUrl, { data }, options);
  }
  
  /**
   * Perform a PUT request
   */
  async put<T>(
    url: string,
    data?: any,
    options?: RequestOptions
  ): Promise<T> {
    // Ensure url starts with API prefix
    const fullUrl = this.ensureApiPrefix(url);
    return this.requestWithRetry<T>('PUT', fullUrl, { data }, options);
  }
  
  /**
   * Perform a DELETE request
   */
  async delete<T>(
    url: string,
    params?: Record<string, any>,
    options?: RequestOptions
  ): Promise<T> {
    // Ensure url starts with API prefix
    const fullUrl = this.ensureApiPrefix(url);
    return this.requestWithRetry<T>('DELETE', fullUrl, { params }, options);
  }
  
  /**
   * Ensure the URL has the API prefix
   */
  private ensureApiPrefix(url: string): string {
    if (url.startsWith('/')) {
      // Remove leading slash from URL if it exists
      url = url.substring(1);
    }
    
    // Return the URL with the API prefix
    return `${this.apiPrefix}/${url}`;
  }
}

// Create a singleton instance for use throughout the application
export const apiClient = new ApiClient();