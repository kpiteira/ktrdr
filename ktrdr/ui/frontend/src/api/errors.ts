/**
 * Custom error class for KTRDR API errors
 * Provides structured error information for API failures
 */

import { ApiError } from './types';

export class KTRDRApiError extends Error {
  code: string;
  details?: Record<string, any>;

  /**
   * Create a new API error
   * @param code Error code
   * @param message Error message
   * @param details Additional error details
   */
  constructor(code: string, message: string, details?: Record<string, any>) {
    super(message);
    this.name = 'KTRDRApiError';
    this.code = code;
    this.details = details;
    
    // This is needed to make instanceof work correctly with custom errors
    Object.setPrototypeOf(this, KTRDRApiError.prototype);
  }

  /**
   * Create a KTRDRApiError from an ApiError object
   * @param error ApiError object from response
   */
  static fromApiError(error: ApiError): KTRDRApiError {
    return new KTRDRApiError(
      error.code,
      error.message,
      error.details
    );
  }

  /**
   * Create a general network error
   * @param originalError Original error object
   */
  static networkError(originalError: Error): KTRDRApiError {
    return new KTRDRApiError(
      'NETWORK_ERROR',
      `Network request failed: ${originalError.message}`,
      { originalError: originalError.message }
    );
  }

  /**
   * Create a timeout error
   */
  static timeoutError(): KTRDRApiError {
    return new KTRDRApiError(
      'TIMEOUT_ERROR',
      'Request timed out'
    );
  }

  /**
   * Create an error for unexpected response format
   */
  static unexpectedResponseError(): KTRDRApiError {
    return new KTRDRApiError(
      'INVALID_RESPONSE',
      'Received unexpected response format from server'
    );
  }
}