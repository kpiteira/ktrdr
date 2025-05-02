# KTRDR API Client Integration Guide

This document provides code examples for integrating with the KTRDR API in various programming languages.

## 1. Python Integration

### 1.1 Basic Client

```python
import requests
import json
from typing import Dict, Any, Optional, List

class KTRDRClient:
    """Simple Python client for the KTRDR API."""
    
    def __init__(self, base_url: str = "http://localhost:8000/api/v1", api_key: Optional[str] = None):
        """Initialize the client with base URL and optional API key."""
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response, raising exceptions for errors."""
        try:
            data = response.json()
            
            if not data.get("success", False):
                error = data.get("error", {})
                code = error.get("code", "UNKNOWN_ERROR")
                message = error.get("message", "Unknown error occurred")
                details = error.get("details", {})
                
                raise Exception(f"API Error {code}: {message} - {details}")
                
            return data.get("data", {})
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON response: {response.text}")
    
    def get_symbols(self) -> List[Dict[str, Any]]:
        """Get available trading symbols."""
        response = requests.get(f"{self.base_url}/symbols", headers=self.headers)
        return self._handle_response(response)
    
    def get_timeframes(self) -> List[Dict[str, Any]]:
        """Get available timeframes."""
        response = requests.get(f"{self.base_url}/timeframes", headers=self.headers)
        return self._handle_response(response)
    
    def load_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 1000
    ) -> Dict[str, Any]:
        """Load market data for a symbol and timeframe."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "page": page,
            "page_size": page_size
        }
        
        if start_date:
            payload["start_date"] = start_date
            
        if end_date:
            payload["end_date"] = end_date
        
        response = requests.post(
            f"{self.base_url}/data/load", 
            headers=self.headers,
            json=payload
        )
        
        return self._handle_response(response)
    
    def calculate_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicators: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate indicators for a symbol and timeframe."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators
        }
        
        if start_date:
            payload["start_date"] = start_date
            
        if end_date:
            payload["end_date"] = end_date
        
        response = requests.post(
            f"{self.base_url}/indicators/calculate",
            headers=self.headers,
            json=payload
        )
        
        return self._handle_response(response)
    
    def generate_chart(
        self,
        symbol: str,
        timeframe: str,
        indicators: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate chart configuration."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe
        }
        
        if indicators:
            payload["indicators"] = indicators
            
        if options:
            payload["options"] = options
            
        if start_date:
            payload["start_date"] = start_date
            
        if end_date:
            payload["end_date"] = end_date
        
        response = requests.post(
            f"{self.base_url}/charts/render",
            headers=self.headers,
            json=payload
        )
        
        return self._handle_response(response)
```

### 1.2 Usage Example

```python
# Initialize the client
client = KTRDRClient(base_url="http://localhost:8000/api/v1")

# Get available symbols and timeframes
symbols = client.get_symbols()
timeframes = client.get_timeframes()

print(f"Available symbols: {len(symbols)}")
print(f"Available timeframes: {[tf['id'] for tf in timeframes]}")

# Load data for a symbol
data = client.load_data(
    symbol="AAPL",
    timeframe="1d",
    start_date="2023-01-01",
    end_date="2023-01-31"
)

print(f"Loaded {len(data['dates'])} data points for AAPL")

# Calculate indicators
indicators_result = client.calculate_indicators(
    symbol="AAPL",
    timeframe="1d",
    indicators=[
        {
            "id": "RSIIndicator",
            "parameters": {"period": 14, "source": "close"},
            "output_name": "rsi_14"
        },
        {
            "id": "SimpleMovingAverage",
            "parameters": {"period": 20, "source": "close"},
            "output_name": "sma_20"
        }
    ],
    start_date="2023-01-01",
    end_date="2023-01-31"
)

print(f"Calculated indicators for {len(indicators_result['dates'])} data points")

# Generate chart configuration
chart_config = client.generate_chart(
    symbol="AAPL",
    timeframe="1d",
    indicators=[
        {
            "id": "SimpleMovingAverage",
            "parameters": {"period": 20, "source": "close"},
            "output_name": "SMA 20",
            "color": "#2962FF"
        },
        {
            "id": "RSIIndicator",
            "parameters": {"period": 14, "source": "close"},
            "output_name": "RSI 14",
            "color": "#FF6D00",
            "panel": "separate"
        }
    ],
    options={
        "theme": "dark",
        "height": 600,
        "show_volume": True,
        "multi_panel": True
    },
    start_date="2023-01-01",
    end_date="2023-01-31"
)

print("Generated chart configuration")
```

### 1.3 Advanced Python Client

This more sophisticated client adds caching, error handling, and asynchronous requests:

```python
import requests
import json
import time
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Callable
from functools import wraps

class KTRDRAdvancedClient:
    """Advanced Python client for the KTRDR API with caching and async support."""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8000/api/v1", 
        api_key: Optional[str] = None,
        cache_ttl: int = 300,  # 5 minutes default cache TTL
        max_retries: int = 3
    ):
        """Initialize the client with base URL, API key, and options."""
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if api_key:
            self.headers["X-API-Key"] = api_key
            
        self.cache = {}
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        
    def _generate_cache_key(self, *args, **kwargs) -> str:
        """Generate a cache key from function arguments."""
        key_parts = list(args)
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return ":".join(str(part) for part in key_parts)
    
    def cached(self, ttl: Optional[int] = None):
        """Decorator to cache function results."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Skip cache if force_refresh is True
                force_refresh = kwargs.pop("force_refresh", False)
                
                if not force_refresh:
                    # Generate cache key
                    cache_key = f"{func.__name__}:{self._generate_cache_key(*args, **kwargs)}"
                    
                    # Check cache
                    if cache_key in self.cache:
                        entry = self.cache[cache_key]
                        if time.time() - entry["timestamp"] < (ttl or self.cache_ttl):
                            return entry["data"]
                
                # Cache miss or forced refresh
                result = func(*args, **kwargs)
                
                # Store in cache
                cache_key = f"{func.__name__}:{self._generate_cache_key(*args, **kwargs)}"
                self.cache[cache_key] = {
                    "data": result,
                    "timestamp": time.time()
                }
                
                return result
            return wrapper
        return decorator
    
    def retry(self, max_retries: Optional[int] = None):
        """Decorator to retry on failure with exponential backoff."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                retries = 0
                max_retry_count = max_retries or self.max_retries
                
                while True:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        retries += 1
                        if retries > max_retry_count:
                            raise
                        
                        # Exponential backoff
                        delay = min(0.5 * (2 ** (retries - 1)), 8)
                        print(f"Retrying {func.__name__} in {delay:.2f} seconds...")
                        time.sleep(delay)
            return wrapper
        return decorator
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response, raising exceptions for errors."""
        try:
            data = response.json()
            
            if not data.get("success", False):
                error = data.get("error", {})
                code = error.get("code", "UNKNOWN_ERROR")
                message = error.get("message", "Unknown error occurred")
                details = error.get("details", {})
                
                raise KTRDRApiError(code, message, details)
                
            return data.get("data", {})
        except json.JSONDecodeError:
            raise KTRDRApiError("INVALID_RESPONSE", "Invalid JSON response", 
                               {"response_text": response.text})
    
    @cached(ttl=3600)  # Cache for 1 hour
    @retry()
    def get_symbols(self) -> List[Dict[str, Any]]:
        """Get available trading symbols."""
        response = requests.get(f"{self.base_url}/symbols", headers=self.headers)
        return self._handle_response(response)
    
    @cached(ttl=86400)  # Cache for 1 day
    @retry()
    def get_timeframes(self) -> List[Dict[str, Any]]:
        """Get available timeframes."""
        response = requests.get(f"{self.base_url}/timeframes", headers=self.headers)
        return self._handle_response(response)
    
    @cached()
    @retry()
    def load_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 1000
    ) -> Dict[str, Any]:
        """Load market data for a symbol and timeframe."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "page": page,
            "page_size": page_size
        }
        
        if start_date:
            payload["start_date"] = start_date
            
        if end_date:
            payload["end_date"] = end_date
        
        response = requests.post(
            f"{self.base_url}/data/load", 
            headers=self.headers,
            json=payload
        )
        
        return self._handle_response(response)
    
    @cached()
    @retry()
    def calculate_indicators(
        self,
        symbol: str,
        timeframe: str,
        indicators: List[Dict[str, Any]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate indicators for a symbol and timeframe."""
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators
        }
        
        if start_date:
            payload["start_date"] = start_date
            
        if end_date:
            payload["end_date"] = end_date
        
        response = requests.post(
            f"{self.base_url}/indicators/calculate",
            headers=self.headers,
            json=payload
        )
        
        return self._handle_response(response)
    
    async def load_multiple_symbols_async(
        self, 
        symbols: List[str], 
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        concurrency_limit: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """Load data for multiple symbols concurrently with a concurrency limit."""
        results = {}
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        async def fetch_symbol(symbol):
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    headers = dict(self.headers)
                    payload = {
                        "symbol": symbol,
                        "timeframe": timeframe
                    }
                    
                    if start_date:
                        payload["start_date"] = start_date
                        
                    if end_date:
                        payload["end_date"] = end_date
                    
                    async with session.post(
                        f"{self.base_url}/data/load",
                        headers=headers,
                        json=payload
                    ) as response:
                        data = await response.json()
                        
                        if not data.get("success", False):
                            error = data.get("error", {})
                            print(f"Error fetching {symbol}: {error}")
                            return symbol, None
                        
                        return symbol, data.get("data", {})
        
        tasks = [fetch_symbol(symbol) for symbol in symbols]
        for completed_task in asyncio.as_completed(tasks):
            symbol, data = await completed_task
            if data:
                results[symbol] = data
                
        return results


class KTRDRApiError(Exception):
    """Custom error class for KTRDR API errors."""
    
    def __init__(self, code: str, message: str, details: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")
```

### 1.4 Advanced Client Usage

```python
import asyncio
from datetime import datetime, timedelta

# Initialize the client
client = KTRDRAdvancedClient(base_url="http://localhost:8000/api/v1")

# Get available symbols (cached for 1 hour)
symbols = client.get_symbols()
print(f"Available symbols: {len(symbols)}")

# Get symbols with forced refresh (bypass cache)
symbols_refresh = client.get_symbols(force_refresh=True)
print(f"Refreshed symbols: {len(symbols_refresh)}")

# Load data with retry on failure
try:
    data = client.load_data(
        symbol="AAPL",
        timeframe="1d",
        start_date="2023-01-01",
        end_date="2023-01-31"
    )
    print(f"Loaded {len(data['dates'])} data points for AAPL")
except KTRDRApiError as e:
    print(f"API error: {e.code} - {e.message}")

# Async example - load data for multiple symbols
async def load_multiple():
    symbols_to_load = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]
    results = await client.load_multiple_symbols_async(
        symbols=symbols_to_load,
        timeframe="1d",
        start_date="2023-01-01",
        end_date="2023-01-31",
        concurrency_limit=3  # Only 3 concurrent requests
    )
    
    for symbol, data in results.items():
        print(f"Loaded {len(data['dates'])} data points for {symbol}")

# Run the async function
asyncio.run(load_multiple())
```

## 2. JavaScript Integration

### 2.1 Basic Client

```javascript
/**
 * Basic JavaScript client for the KTRDR API
 */
class KTRDRClient {
  /**
   * Initialize the client
   * @param {string} baseUrl - Base API URL
   * @param {string} apiKey - Optional API key
   */
  constructor(baseUrl = 'http://localhost:8000/api/v1', apiKey = null) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    this.headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };
    
    if (apiKey) {
      this.headers['X-API-Key'] = apiKey;
    }
  }
  
  /**
   * Handle API response
   * @param {Response} response - Fetch response object
   * @returns {Promise<Object>} - API data
   */
  async _handleResponse(response) {
    const data = await response.json();
    
    if (!data.success) {
      const error = data.error || {};
      const code = error.code || 'UNKNOWN_ERROR';
      const message = error.message || 'Unknown error occurred';
      const details = error.details || {};
      
      throw new Error(`API Error ${code}: ${message} - ${JSON.stringify(details)}`);
    }
    
    return data.data || {};
  }
  
  /**
   * Get available trading symbols
   * @returns {Promise<Array>} - List of symbols
   */
  async getSymbols() {
    const response = await fetch(`${this.baseUrl}/symbols`, {
      method: 'GET',
      headers: this.headers
    });
    
    return this._handleResponse(response);
  }
  
  /**
   * Get available timeframes
   * @returns {Promise<Array>} - List of timeframes
   */
  async getTimeframes() {
    const response = await fetch(`${this.baseUrl}/timeframes`, {
      method: 'GET',
      headers: this.headers
    });
    
    return this._handleResponse(response);
  }
  
  /**
   * Load market data for a symbol and timeframe
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - OHLCV data
   */
  async loadData({
    symbol,
    timeframe,
    startDate = null,
    endDate = null,
    page = 1,
    pageSize = 1000
  }) {
    const payload = {
      symbol,
      timeframe,
      page,
      page_size: pageSize
    };
    
    if (startDate) {
      payload.start_date = startDate;
    }
    
    if (endDate) {
      payload.end_date = endDate;
    }
    
    const response = await fetch(`${this.baseUrl}/data/load`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload)
    });
    
    return this._handleResponse(response);
  }
  
  /**
   * Calculate indicators for a symbol and timeframe
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Indicator data
   */
  async calculateIndicators({
    symbol,
    timeframe,
    indicators,
    startDate = null,
    endDate = null
  }) {
    const payload = {
      symbol,
      timeframe,
      indicators
    };
    
    if (startDate) {
      payload.start_date = startDate;
    }
    
    if (endDate) {
      payload.end_date = endDate;
    }
    
    const response = await fetch(`${this.baseUrl}/indicators/calculate`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload)
    });
    
    return this._handleResponse(response);
  }
  
  /**
   * Generate chart configuration
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Chart configuration
   */
  async generateChart({
    symbol,
    timeframe,
    indicators = null,
    options = null,
    startDate = null,
    endDate = null
  }) {
    const payload = {
      symbol,
      timeframe
    };
    
    if (indicators) {
      payload.indicators = indicators;
    }
    
    if (options) {
      payload.options = options;
    }
    
    if (startDate) {
      payload.start_date = startDate;
    }
    
    if (endDate) {
      payload.end_date = endDate;
    }
    
    const response = await fetch(`${this.baseUrl}/charts/render`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload)
    });
    
    return this._handleResponse(response);
  }
}
```

### 2.2 Usage Example

```javascript
// Initialize the client
const client = new KTRDRClient('http://localhost:8000/api/v1');

async function main() {
  try {
    // Get available symbols and timeframes
    const symbols = await client.getSymbols();
    const timeframes = await client.getTimeframes();
    
    console.log(`Available symbols: ${symbols.length}`);
    console.log(`Available timeframes: ${timeframes.map(tf => tf.id).join(', ')}`);
    
    // Load data for a symbol
    const data = await client.loadData({
      symbol: 'AAPL',
      timeframe: '1d',
      startDate: '2023-01-01',
      endDate: '2023-01-31'
    });
    
    console.log(`Loaded ${data.dates.length} data points for AAPL`);
    
    // Calculate indicators
    const indicatorsResult = await client.calculateIndicators({
      symbol: 'AAPL',
      timeframe: '1d',
      indicators: [
        {
          id: 'RSIIndicator',
          parameters: { period: 14, source: 'close' },
          output_name: 'rsi_14'
        },
        {
          id: 'SimpleMovingAverage',
          parameters: { period: 20, source: 'close' },
          output_name: 'sma_20'
        }
      ],
      startDate: '2023-01-01',
      endDate: '2023-01-31'
    });
    
    console.log(`Calculated indicators for ${indicatorsResult.dates.length} data points`);
    
    // Generate chart configuration
    const chartConfig = await client.generateChart({
      symbol: 'AAPL',
      timeframe: '1d',
      indicators: [
        {
          id: 'SimpleMovingAverage',
          parameters: { period: 20, source: 'close' },
          output_name: 'SMA 20',
          color: '#2962FF'
        },
        {
          id: 'RSIIndicator',
          parameters: { period: 14, source: 'close' },
          output_name: 'RSI 14',
          color: '#FF6D00',
          panel: 'separate'
        }
      ],
      options: {
        theme: 'dark',
        height: 600,
        show_volume: true,
        multi_panel: true
      },
      startDate: '2023-01-01',
      endDate: '2023-01-31'
    });
    
    console.log('Generated chart configuration');
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

main();
```

### 2.3 Advanced JavaScript Client

```javascript
/**
 * Advanced JavaScript client for the KTRDR API
 * with caching, retry, and advanced features
 */
class KTRDRAdvancedClient {
  /**
   * Initialize the client
   * @param {Object} options - Client options
   */
  constructor({
    baseUrl = 'http://localhost:8000/api/v1',
    apiKey = null,
    cacheTtl = 300, // 5 minutes default cache TTL
    maxRetries = 3
  } = {}) {
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    this.headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };
    
    if (apiKey) {
      this.headers['X-API-Key'] = apiKey;
    }
    
    this.cache = new Map();
    this.cacheTtl = cacheTtl;
    this.maxRetries = maxRetries;
  }
  
  /**
   * Generate a cache key from arguments
   * @param {string} prefix - Key prefix
   * @param {Object} args - Arguments to include in key
   * @returns {string} - Cache key
   */
  _generateCacheKey(prefix, args) {
    return `${prefix}:${JSON.stringify(args)}`;
  }
  
  /**
   * Get item from cache if valid
   * @param {string} key - Cache key
   * @param {number} ttl - TTL override
   * @returns {any} - Cached data or null
   */
  _getFromCache(key, ttl = null) {
    if (this.cache.has(key)) {
      const entry = this.cache.get(key);
      const now = Date.now();
      const validTtl = ttl || this.cacheTtl;
      
      if (now - entry.timestamp < validTtl * 1000) {
        return entry.data;
      }
    }
    
    return null;
  }
  
  /**
   * Store item in cache
   * @param {string} key - Cache key
   * @param {any} data - Data to cache
   */
  _storeInCache(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }
  
  /**
   * Handle API response
   * @param {Response} response - Fetch response object
   * @returns {Promise<Object>} - API data
   */
  async _handleResponse(response) {
    const data = await response.json();
    
    if (!data.success) {
      const error = data.error || {};
      const code = error.code || 'UNKNOWN_ERROR';
      const message = error.message || 'Unknown error occurred';
      const details = error.details || {};
      
      throw new KTRDRApiError(code, message, details);
    }
    
    return data.data || {};
  }
  
  /**
   * Retry a function with exponential backoff
   * @param {Function} fn - Function to retry
   * @param {number} maxRetries - Maximum number of retries
   * @returns {Promise<any>} - Function result
   */
  async _retry(fn, maxRetries = null) {
    const maxRetryCount = maxRetries || this.maxRetries;
    let retries = 0;
    
    while (true) {
      try {
        return await fn();
      } catch (err) {
        retries++;
        if (retries > maxRetryCount) {
          throw err;
        }
        
        // Exponential backoff
        const delay = Math.min(500 * Math.pow(2, retries - 1), 8000);
        console.log(`Retrying in ${delay/1000} seconds...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  
  /**
   * Get available trading symbols
   * @param {Object} options - Request options
   * @returns {Promise<Array>} - List of symbols
   */
  async getSymbols({ forceRefresh = false, cacheTtl = 3600 } = {}) {
    const cacheKey = this._generateCacheKey('symbols', {});
    
    if (!forceRefresh) {
      const cached = this._getFromCache(cacheKey, cacheTtl);
      if (cached) return cached;
    }
    
    const result = await this._retry(async () => {
      const response = await fetch(`${this.baseUrl}/symbols`, {
        method: 'GET',
        headers: this.headers
      });
      
      return this._handleResponse(response);
    });
    
    this._storeInCache(cacheKey, result);
    return result;
  }
  
  /**
   * Get available timeframes
   * @param {Object} options - Request options
   * @returns {Promise<Array>} - List of timeframes
   */
  async getTimeframes({ forceRefresh = false, cacheTtl = 86400 } = {}) {
    const cacheKey = this._generateCacheKey('timeframes', {});
    
    if (!forceRefresh) {
      const cached = this._getFromCache(cacheKey, cacheTtl);
      if (cached) return cached;
    }
    
    const result = await this._retry(async () => {
      const response = await fetch(`${this.baseUrl}/timeframes`, {
        method: 'GET',
        headers: this.headers
      });
      
      return this._handleResponse(response);
    });
    
    this._storeInCache(cacheKey, result);
    return result;
  }
  
  /**
   * Load market data for a symbol and timeframe
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - OHLCV data
   */
  async loadData({
    symbol,
    timeframe,
    startDate = null,
    endDate = null,
    page = 1,
    pageSize = 1000,
    forceRefresh = false
  }) {
    const args = { symbol, timeframe, startDate, endDate, page, pageSize };
    const cacheKey = this._generateCacheKey('loadData', args);
    
    if (!forceRefresh) {
      const cached = this._getFromCache(cacheKey);
      if (cached) return cached;
    }
    
    const payload = {
      symbol,
      timeframe,
      page,
      page_size: pageSize
    };
    
    if (startDate) {
      payload.start_date = startDate;
    }
    
    if (endDate) {
      payload.end_date = endDate;
    }
    
    const result = await this._retry(async () => {
      const response = await fetch(`${this.baseUrl}/data/load`, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(payload)
      });
      
      return this._handleResponse(response);
    });
    
    this._storeInCache(cacheKey, result);
    return result;
  }
  
  /**
   * Load data for multiple symbols in parallel
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Map of symbol to data
   */
  async loadMultipleSymbols({
    symbols,
    timeframe,
    startDate = null,
    endDate = null,
    concurrencyLimit = 5,
    forceRefresh = false
  }) {
    // Function to process a chunk of symbols
    const processChunk = async (chunk) => {
      const promises = chunk.map(symbol => 
        this.loadData({
          symbol,
          timeframe,
          startDate,
          endDate,
          forceRefresh
        }).then(data => ({ symbol, data }))
          .catch(err => {
            console.error(`Error loading data for ${symbol}:`, err);
            return { symbol, data: null };
          })
      );
      
      return Promise.all(promises);
    };
    
    // Split symbols into chunks based on concurrency limit
    const chunks = [];
    for (let i = 0; i < symbols.length; i += concurrencyLimit) {
      chunks.push(symbols.slice(i, i + concurrencyLimit));
    }
    
    // Process chunks sequentially
    const results = {};
    for (const chunk of chunks) {
      const chunkResults = await processChunk(chunk);
      chunkResults.forEach(({ symbol, data }) => {
        if (data !== null) {
          results[symbol] = data;
        }
      });
    }
    
    return results;
  }
  
  /**
   * Calculate indicators for a symbol and timeframe
   * @param {Object} params - Request parameters
   * @returns {Promise<Object>} - Indicator data
   */
  async calculateIndicators({
    symbol,
    timeframe,
    indicators,
    startDate = null,
    endDate = null,
    forceRefresh = false
  }) {
    const args = { symbol, timeframe, indicators, startDate, endDate };
    const cacheKey = this._generateCacheKey('calculateIndicators', args);
    
    if (!forceRefresh) {
      const cached = this._getFromCache(cacheKey);
      if (cached) return cached;
    }
    
    const payload = {
      symbol,
      timeframe,
      indicators
    };
    
    if (startDate) {
      payload.start_date = startDate;
    }
    
    if (endDate) {
      payload.end_date = endDate;
    }
    
    const result = await this._retry(async () => {
      const response = await fetch(`${this.baseUrl}/indicators/calculate`, {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(payload)
      });
      
      return this._handleResponse(response);
    });
    
    this._storeInCache(cacheKey, result);
    return result;
  }
}

/**
 * Custom error class for KTRDR API errors
 */
class KTRDRApiError extends Error {
  /**
   * Create a new API error
   * @param {string} code - Error code
   * @param {string} message - Error message
   * @param {Object} details - Error details
   */
  constructor(code, message, details = {}) {
    super(`${code}: ${message}`);
    this.code = code;
    this.details = details;
    this.name = 'KTRDRApiError';
  }
}
```

### 2.4 Advanced Client Usage

```javascript
// Initialize the client
const client = new KTRDRAdvancedClient({
  baseUrl: 'http://localhost:8000/api/v1',
  cacheTtl: 300, // 5 minutes
  maxRetries: 3
});

async function main() {
  try {
    // Get available symbols with long cache TTL
    const symbols = await client.getSymbols({
      cacheTtl: 3600 // 1 hour
    });
    console.log(`Available symbols: ${symbols.length}`);
    
    // Get timeframes with forced refresh
    const timeframes = await client.getTimeframes({
      forceRefresh: true
    });
    console.log(`Available timeframes: ${timeframes.map(tf => tf.id).join(', ')}`);
    
    // Load data for multiple symbols with concurrency limit
    console.log('Loading data for multiple symbols...');
    const symbolsToLoad = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META'];
    const multiData = await client.loadMultipleSymbols({
      symbols: symbolsToLoad,
      timeframe: '1d',
      startDate: '2023-01-01',
      endDate: '2023-01-31',
      concurrencyLimit: 3 // Only 3 concurrent requests
    });
    
    // Display results
    Object.entries(multiData).forEach(([symbol, data]) => {
      console.log(`Loaded ${data.dates.length} data points for ${symbol}`);
    });
    
    // Calculate indicators with retry on failure
    const indicatorsResult = await client.calculateIndicators({
      symbol: 'AAPL',
      timeframe: '1d',
      indicators: [
        {
          id: 'RSIIndicator',
          parameters: { period: 14, source: 'close' },
          output_name: 'rsi_14'
        },
        {
          id: 'SimpleMovingAverage',
          parameters: { period: 20, source: 'close' },
          output_name: 'sma_20'
        }
      ],
      startDate: '2023-01-01',
      endDate: '2023-01-31'
    });
    
    console.log(`Calculated indicators for ${indicatorsResult.dates.length} data points`);
    
  } catch (error) {
    if (error instanceof KTRDRApiError) {
      console.error(`API Error (${error.code}):`, error.message);
      console.error('Details:', error.details);
    } else {
      console.error('Error:', error.message);
    }
  }
}

main();
```

## 3. Postman Collection

For testing and exploration, you can use this Postman collection:

```json
{
  "info": {
    "_postman_id": "7a1c9b5e-2e1f-4e6d-9f3c-b8a2c5f3dd42",
    "name": "KTRDR API",
    "description": "Collection for working with the KTRDR API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Data Endpoints",
      "item": [
        {
          "name": "Get Symbols",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/symbols",
              "host": ["{{base_url}}"],
              "path": ["symbols"]
            },
            "description": "Get list of available trading symbols."
          },
          "response": []
        },
        {
          "name": "Get Timeframes",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/timeframes",
              "host": ["{{base_url}}"],
              "path": ["timeframes"]
            },
            "description": "Get list of available timeframes."
          },
          "response": []
        },
        {
          "name": "Load Data",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"symbol\": \"AAPL\",\n  \"timeframe\": \"1d\",\n  \"start_date\": \"2023-01-01T00:00:00Z\",\n  \"end_date\": \"2023-01-31T23:59:59Z\"\n}"
            },
            "url": {
              "raw": "{{base_url}}/data/load",
              "host": ["{{base_url}}"],
              "path": ["data", "load"]
            },
            "description": "Load OHLCV data for a specific symbol and timeframe."
          },
          "response": []
        }
      ],
      "description": "Endpoints for retrieving market data."
    },
    {
      "name": "Indicator Endpoints",
      "item": [
        {
          "name": "Get Indicators",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/indicators",
              "host": ["{{base_url}}"],
              "path": ["indicators"]
            },
            "description": "Get list of available technical indicators."
          },
          "response": []
        },
        {
          "name": "Calculate Indicators",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"symbol\": \"AAPL\",\n  \"timeframe\": \"1d\",\n  \"start_date\": \"2023-01-01T00:00:00Z\",\n  \"end_date\": \"2023-01-31T23:59:59Z\",\n  \"indicators\": [\n    {\n      \"id\": \"RSIIndicator\",\n      \"parameters\": {\n        \"period\": 14,\n        \"source\": \"close\"\n      },\n      \"output_name\": \"rsi_14\"\n    },\n    {\n      \"id\": \"SimpleMovingAverage\",\n      \"parameters\": {\n        \"period\": 20,\n        \"source\": \"close\"\n      },\n      \"output_name\": \"sma_20\"\n    }\n  ]\n}"
            },
            "url": {
              "raw": "{{base_url}}/indicators/calculate",
              "host": ["{{base_url}}"],
              "path": ["indicators", "calculate"]
            },
            "description": "Calculate technical indicators for a specific symbol and timeframe."
          },
          "response": []
        }
      ],
      "description": "Endpoints for working with technical indicators."
    },
    {
      "name": "Chart Endpoints",
      "item": [
        {
          "name": "Generate Chart",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"symbol\": \"AAPL\",\n  \"timeframe\": \"1d\",\n  \"start_date\": \"2023-01-01T00:00:00Z\",\n  \"end_date\": \"2023-01-31T23:59:59Z\",\n  \"indicators\": [\n    {\n      \"id\": \"SimpleMovingAverage\",\n      \"parameters\": {\n        \"period\": 20,\n        \"source\": \"close\"\n      },\n      \"output_name\": \"SMA 20\",\n      \"color\": \"#2962FF\"\n    },\n    {\n      \"id\": \"RSIIndicator\",\n      \"parameters\": {\n        \"period\": 14,\n        \"source\": \"close\"\n      },\n      \"output_name\": \"RSI 14\",\n      \"color\": \"#FF6D00\",\n      \"panel\": \"separate\"\n    }\n  ],\n  \"options\": {\n    \"theme\": \"dark\",\n    \"height\": 600,\n    \"show_volume\": true,\n    \"multi_panel\": true\n  }\n}"
            },
            "url": {
              "raw": "{{base_url}}/charts/render",
              "host": ["{{base_url}}"],
              "path": ["charts", "render"]
            },
            "description": "Generate chart configuration for rendering with lightweight-charts."
          },
          "response": []
        },
        {
          "name": "Get Chart Template",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/charts/template?theme=dark",
              "host": ["{{base_url}}"],
              "path": ["charts", "template"],
              "query": [
                {
                  "key": "theme",
                  "value": "dark"
                }
              ]
            },
            "description": "Get HTML template for rendering charts."
          },
          "response": []
        }
      ],
      "description": "Endpoints for chart generation."
    },
    {
      "name": "Fuzzy Logic Endpoints",
      "item": [
        {
          "name": "Get Fuzzy Indicators",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/fuzzy/indicators",
              "host": ["{{base_url}}"],
              "path": ["fuzzy", "indicators"]
            },
            "description": "Get list of indicators that can be used with fuzzy logic."
          },
          "response": []
        },
        {
          "name": "Get Fuzzy Sets",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/fuzzy/sets/rsi",
              "host": ["{{base_url}}"],
              "path": ["fuzzy", "sets", "rsi"]
            },
            "description": "Get fuzzy membership function configuration for a specific indicator."
          },
          "response": []
        },
        {
          "name": "Evaluate Fuzzy Membership",
          "request": {
            "method": "POST",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "body": {
              "mode": "raw",
              "raw": "{\n  \"indicator\": \"rsi\",\n  \"values\": [35, 45, 55, 65, 75],\n  \"dates\": [\n    \"2023-01-01T00:00:00Z\",\n    \"2023-01-02T00:00:00Z\",\n    \"2023-01-03T00:00:00Z\",\n    \"2023-01-04T00:00:00Z\",\n    \"2023-01-05T00:00:00Z\"\n  ]\n}"
            },
            "url": {
              "raw": "{{base_url}}/fuzzy/evaluate",
              "host": ["{{base_url}}"],
              "path": ["fuzzy", "evaluate"]
            },
            "description": "Apply fuzzy membership functions to a set of indicator values."
          },
          "response": []
        }
      ],
      "description": "Endpoints for working with fuzzy logic."
    },
    {
      "name": "System Endpoints",
      "item": [
        {
          "name": "Health Check",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/health",
              "host": ["{{base_url}}"],
              "path": ["health"]
            },
            "description": "Get information about the API status."
          },
          "response": []
        },
        {
          "name": "API Information",
          "request": {
            "method": "GET",
            "header": [
              {
                "key": "Content-Type",
                "value": "application/json"
              },
              {
                "key": "Accept",
                "value": "application/json"
              }
            ],
            "url": {
              "raw": "{{base_url}}/info",
              "host": ["{{base_url}}"],
              "path": ["info"]
            },
            "description": "Get information about the API including version and available endpoints."
          },
          "response": []
        }
      ],
      "description": "System endpoints for monitoring and information."
    }
  ],
  "event": [
    {
      "listen": "prerequest",
      "script": {
        "type": "text/javascript",
        "exec": [""]
      }
    },
    {
      "listen": "test",
      "script": {
        "type": "text/javascript",
        "exec": [""]
      }
    }
  ],
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000/api/v1",
      "type": "string"
    }
  ]
}
```

## 4. cURL Examples

Here are some common cURL commands for interacting with the API:

### 4.1 Get Symbols

```bash
curl -X GET "http://localhost:8000/api/v1/symbols" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json"
```

### 4.2 Get Timeframes

```bash
curl -X GET "http://localhost:8000/api/v1/timeframes" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json"
```

### 4.3 Load Data

```bash
curl -X POST "http://localhost:8000/api/v1/data/load" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -d '{
       "symbol": "AAPL",
       "timeframe": "1d",
       "start_date": "2023-01-01T00:00:00Z",
       "end_date": "2023-01-31T23:59:59Z"
     }'
```

### 4.4 Calculate Indicators

```bash
curl -X POST "http://localhost:8000/api/v1/indicators/calculate" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -d '{
       "symbol": "AAPL",
       "timeframe": "1d",
       "start_date": "2023-01-01T00:00:00Z",
       "end_date": "2023-01-31T23:59:59Z",
       "indicators": [
         {
           "id": "RSIIndicator",
           "parameters": {"period": 14, "source": "close"},
           "output_name": "rsi_14"
         },
         {
           "id": "SimpleMovingAverage",
           "parameters": {"period": 20, "source": "close"},
           "output_name": "sma_20"
         }
       ]
     }'
```

### 4.5 Generate Chart

```bash
curl -X POST "http://localhost:8000/api/v1/charts/render" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -d '{
       "symbol": "AAPL",
       "timeframe": "1d",
       "start_date": "2023-01-01T00:00:00Z",
       "end_date": "2023-01-31T23:59:59Z",
       "indicators": [
         {
           "id": "SimpleMovingAverage",
           "parameters": {"period": 20, "source": "close"},
           "output_name": "SMA 20",
           "color": "#2962FF"
         },
         {
           "id": "RSIIndicator",
           "parameters": {"period": 14, "source": "close"},
           "output_name": "RSI 14",
           "color": "#FF6D00",
           "panel": "separate"
         }
       ],
       "options": {
         "theme": "dark",
         "height": 600,
         "show_volume": true,
         "multi_panel": true
       }
     }'
```