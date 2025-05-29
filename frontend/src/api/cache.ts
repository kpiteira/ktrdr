/**
 * Cache implementation for API responses
 * Provides in-memory caching with TTL and manual invalidation
 */

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

/**
 * Simple in-memory cache with TTL support
 */
export class ApiCache {
  private cache: Map<string, CacheEntry<any>>;
  private defaultTtl: number;
  private maxEntries: number;

  /**
   * Create a new API cache
   * @param defaultTtl Default time-to-live in milliseconds (default: 5 minutes)
   * @param maxEntries Maximum number of cache entries (default: 100)
   */
  constructor(defaultTtl: number = 5 * 60 * 1000, maxEntries: number = 100) {
    this.cache = new Map();
    this.defaultTtl = defaultTtl;
    this.maxEntries = maxEntries;
  }

  /**
   * Generate a cache key from a request
   * @param endpoint API endpoint
   * @param params Request parameters
   * @returns Cache key string
   */
  generateKey(endpoint: string, params?: Record<string, any>): string {
    if (!params) {
      return endpoint;
    }
    
    // Sort keys for consistent cache keys regardless of object property order
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((obj: Record<string, any>, key) => {
        if (params[key] !== undefined) {
          obj[key] = params[key];
        }
        return obj;
      }, {});
    
    return `${endpoint}:${JSON.stringify(sortedParams)}`;
  }

  /**
   * Get an item from the cache
   * @param key Cache key
   * @param ttl Time-to-live in milliseconds (overrides default)
   * @returns Cached data or undefined if not found or expired
   */
  get<T>(key: string, ttl?: number): T | undefined {
    const entry = this.cache.get(key);
    
    if (!entry) {
      return undefined;
    }
    
    const now = Date.now();
    const maxAge = ttl ?? this.defaultTtl;
    
    // Check if entry has expired
    if (now - entry.timestamp > maxAge) {
      this.cache.delete(key);
      return undefined;
    }
    
    return entry.data;
  }

  /**
   * Store an item in the cache
   * @param key Cache key
   * @param data Data to cache
   */
  set<T>(key: string, data: T): void {
    // Enforce cache size limit with LRU approach (delete oldest entries first)
    if (this.cache.size >= this.maxEntries) {
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }
    
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  /**
   * Delete an item from the cache
   * @param key Cache key
   */
  delete(key: string): void {
    this.cache.delete(key);
  }

  /**
   * Clear all entries from the cache
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Delete all cache entries that match a prefix
   * @param prefix Key prefix to match
   */
  invalidateByPrefix(prefix: string): void {
    for (const key of this.cache.keys()) {
      if (key.startsWith(prefix)) {
        this.cache.delete(key);
      }
    }
  }
}

// Create a singleton instance for use throughout the application
export const apiCache = new ApiCache();