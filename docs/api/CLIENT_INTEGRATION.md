# KTRDR API Client Integration Guide

This document provides examples and guidelines for integrating client applications with the KTRDR API.

## 1. Client Integration Patterns

When integrating with the KTRDR API, we recommend following these patterns:

1. **API Client Libraries**: Create a dedicated client library for your language
2. **Error Handling**: Implement comprehensive error handling for all API responses
3. **Retry Logic**: Add retry logic with backoff for transient failures
4. **Data Transformation**: Transform API responses to application-specific models
5. **Connection Pooling**: Reuse HTTP connections for improved performance

## 2. Python Integration Examples

### 2.1 Basic Python Request with Requests Library

```python
import requests
import json

# Base configuration
api_base_url = "http://localhost:8000/api/v1"
headers = {
    "Content-Type": "application/json",
    "User-Agent": "KTRDR-Client/1.0"
}

# Example: Get available symbols
def get_symbols():
    response = requests.get(f"{api_base_url}/symbols", headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success", False):
            return result.get("data", [])
        else:
            error = result.get("error", {})
            print(f"API Error: {error.get('message')}")
            return []
    else:
        print(f"HTTP Error: {response.status_code}")
        return []

# Example: Load OHLCV data
def load_data(symbol, timeframe, start_date=None, end_date=None):
    payload = {
        "symbol": symbol,
        "timeframe": timeframe
    }
    
    if start_date:
        payload["start_date"] = start_date
    
    if end_date:
        payload["end_date"] = end_date
    
    response = requests.post(
        f"{api_base_url}/data/load",
        headers=headers,
        data=json.dumps(payload)
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success", False):
            return result.get("data", {})
        else:
            error = result.get("error", {})
            print(f"API Error: {error.get('message')}")
            return {}
    else:
        print(f"HTTP Error: {response.status_code}")
        return {}

# Example: Calculate indicators
def calculate_indicators(symbol, timeframe, indicators, start_date=None, end_date=None):
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
        f"{api_base_url}/indicators/calculate",
        headers=headers,
        data=json.dumps(payload)
    )
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success", False):
            return result.get("data", {})
        else:
            error = result.get("error", {})
            print(f"API Error: {error.get('message')}")
            return {}
    else:
        print(f"HTTP Error: {response.status_code}")
        return {}

# Usage example
if __name__ == "__main__":
    # Get symbols
    symbols = get_symbols()
    print(f"Available symbols: {symbols}")
    
    # Load data for AAPL
    data = load_data("AAPL", "1d", "2023-01-01", "2023-01-31")
    print(f"Loaded {len(data.get('dates', []))} days of data for AAPL")
    
    # Calculate RSI and SMA
    indicators = [
        {
            "id": "RSIIndicator",
            "parameters": {
                "period": 14,
                "source": "close"
            }
        },
        {
            "id": "SimpleMovingAverage",
            "parameters": {
                "period": 20,
                "source": "close"
            }
        }
    ]
    
    indicator_data = calculate_indicators("AAPL", "1d", indicators, "2023-01-01", "2023-01-31")
    print(f"Calculated indicators: {list(indicator_data.get('indicators', {}).keys())}")
```

### 2.2 Python Client Library

```python
# ktrdr_client.py
import requests
import json
import time
from typing import Dict, List, Any, Optional, Union

class KTRDRApiError(Exception):
    """Exception raised for KTRDR API errors."""
    
    def __init__(self, code: str, message: str, details: Dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")

class KTRDRApiClient:
    """KTRDR API client library."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the KTRDR API client.
        
        Args:
            base_url: Base URL of the API (e.g., "http://localhost:8000/api/v1")
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        
        # Set up headers
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "KTRDR-Python-Client/1.0"
        }
        
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def _handle_response(self, response: requests.Response) -> Dict:
        """
        Handle API response and extract data or raise exceptions.
        
        Args:
            response: The HTTP response from the API
            
        Returns:
            Parsed response data if successful
            
        Raises:
            KTRDRApiError: If the API returns an error
            HTTPError: For HTTP-level errors
        """
        # Raise HTTP errors
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        # Check for API errors
        if not result.get("success", False):
            error = result.get("error", {})
            raise KTRDRApiError(
                code=error.get("code", "UNKNOWN_ERROR"),
                message=error.get("message", "Unknown error occurred"),
                details=error.get("details", {})
            )
        
        # Return the data
        return result.get("data", {})
    
    def _make_request(self, method: str, path: str, params: Dict = None, 
                      data: Dict = None, max_retries: int = 3) -> Dict:
        """
        Make an HTTP request to the API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            params: Query parameters
            data: Request body data
            max_retries: Maximum number of retries for transient failures
            
        Returns:
            Parsed response data
            
        Raises:
            KTRDRApiError: For API-level errors
            Exception: For other errors after max retries
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, params=params, headers=self.headers)
                elif method.upper() == "POST":
                    response = self.session.post(
                        url, 
                        params=params, 
                        headers=self.headers,
                        data=json.dumps(data) if data else None
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                return self._handle_response(response)
                
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                # Retry transient errors with backoff
                retry_count += 1
                if retry_count >= max_retries:
                    raise
                
                # Exponential backoff
                backoff_time = 0.5 * (2 ** retry_count)
                print(f"Request failed, retrying in {backoff_time:.2f} seconds: {str(e)}")
                time.sleep(backoff_time)
            
            except Exception:
                # Don't retry other exceptions
                raise
    
    # Data endpoints
    def get_symbols(self) -> List[Dict]:
        """Get list of available trading symbols."""
        return self._make_request("GET", "symbols")
    
    def get_timeframes(self) -> List[Dict]:
        """Get list of available timeframes."""
        return self._make_request("GET", "timeframes")
    
    def load_data(self, symbol: str, timeframe: str, start_date: Optional[str] = None, 
                  end_date: Optional[str] = None) -> Dict:
        """
        Load OHLCV data for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1d", "1h")
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            
        Returns:
            OHLCV data with dates, values, and metadata
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe
        }
        
        if start_date:
            data["start_date"] = start_date
            
        if end_date:
            data["end_date"] = end_date
        
        return self._make_request("POST", "data/load", data=data)
    
    def get_data_range(self, symbol: str, timeframe: str) -> Dict:
        """
        Get available date range for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1d", "1h")
            
        Returns:
            Date range information with start_date, end_date, and point_count
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe
        }
        
        return self._make_request("POST", "data/range", data=data)
    
    # Indicator endpoints
    def get_indicators(self) -> List[Dict]:
        """Get list of available technical indicators."""
        return self._make_request("GET", "indicators")
    
    def calculate_indicators(self, symbol: str, timeframe: str, indicators: List[Dict],
                            start_date: Optional[str] = None, 
                            end_date: Optional[str] = None) -> Dict:
        """
        Calculate technical indicators for a symbol and timeframe.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1d", "1h")
            indicators: List of indicator configurations
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            
        Returns:
            Indicator values with dates and metadata
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators
        }
        
        if start_date:
            data["start_date"] = start_date
            
        if end_date:
            data["end_date"] = end_date
        
        return self._make_request("POST", "indicators/calculate", data=data)
    
    # Fuzzy logic endpoints
    def get_fuzzy_indicators(self) -> List[Dict]:
        """Get list of available fuzzy indicators."""
        return self._make_request("GET", "fuzzy/indicators")
    
    def get_fuzzy_sets(self, indicator: str) -> Dict:
        """
        Get fuzzy sets for a specific indicator.
        
        Args:
            indicator: Indicator name (e.g., "rsi")
            
        Returns:
            Fuzzy sets configuration
        """
        return self._make_request("GET", f"fuzzy/sets/{indicator}")
    
    def evaluate_fuzzy(self, indicator: str, values: List[float], 
                      dates: Optional[List[str]] = None) -> Dict:
        """
        Apply fuzzy membership functions to indicator values.
        
        Args:
            indicator: Indicator name (e.g., "rsi")
            values: List of indicator values
            dates: Optional list of dates
            
        Returns:
            Fuzzy membership values
        """
        data = {
            "indicator": indicator,
            "values": values
        }
        
        if dates:
            data["dates"] = dates
        
        return self._make_request("POST", "fuzzy/evaluate", data=data)
    
    def fuzzify_data(self, symbol: str, timeframe: str, indicators: List[Dict],
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> Dict:
        """
        Load data, calculate indicators, and apply fuzzy membership functions.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            timeframe: Timeframe (e.g., "1d", "1h")
            indicators: List of indicator configurations
            start_date: Optional start date (ISO format)
            end_date: Optional end date (ISO format)
            
        Returns:
            Fuzzy membership values with dates and metadata
        """
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators
        }
        
        if start_date:
            data["start_date"] = start_date
            
        if end_date:
            data["end_date"] = end_date
        
        return self._make_request("POST", "fuzzy/data", data=data)

# Usage example
if __name__ == "__main__":
    # Initialize client
    client = KTRDRApiClient("http://localhost:8000/api/v1")
    
    try:
        # Get symbols
        symbols = client.get_symbols()
        print(f"Available symbols: {symbols}")
        
        # Load data for AAPL
        data = client.load_data("AAPL", "1d", "2023-01-01", "2023-01-31")
        print(f"Loaded {len(data.get('dates', []))} days of data for AAPL")
        
        # Calculate RSI and SMA
        indicators = [
            {
                "id": "RSIIndicator",
                "parameters": {
                    "period": 14,
                    "source": "close"
                }
            },
            {
                "id": "SimpleMovingAverage",
                "parameters": {
                    "period": 20,
                    "source": "close"
                }
            }
        ]
        
        indicator_data = client.calculate_indicators("AAPL", "1d", indicators, "2023-01-01", "2023-01-31")
        print(f"Calculated indicators: {list(indicator_data.get('indicators', {}).keys())}")
        
        # Get fuzzy sets for RSI
        fuzzy_sets = client.get_fuzzy_sets("rsi")
        print(f"RSI fuzzy sets: {list(fuzzy_sets.keys())}")
        
        # Fuzzify RSI values
        fuzzy_indicators = [
            {
                "name": "rsi",
                "source_column": "close"
            }
        ]
        
        fuzzy_data = client.fuzzify_data("AAPL", "1d", fuzzy_indicators, "2023-01-01", "2023-01-31")
        print(f"Fuzzified RSI: {list(fuzzy_data.get('indicators', {}).get('rsi', {}).keys())}")
        
    except KTRDRApiError as e:
        print(f"API Error ({e.code}): {e.message}")
        if e.details:
            print(f"Details: {e.details}")
    
    except requests.exceptions.RequestException as e:
        print(f"HTTP Error: {str(e)}")
    
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
```

## 3. JavaScript Integration Examples

### 3.1 Basic JavaScript with Fetch API

```javascript
// Base configuration
const API_BASE_URL = "http://localhost:8000/api/v1";
const headers = {
    "Content-Type": "application/json",
    "User-Agent": "KTRDR-Client/1.0"
};

// Error handling utility
function handleApiError(result) {
    if (!result.success) {
        const error = result.error || {};
        throw new Error(`API Error (${error.code}): ${error.message}`);
    }
    return result.data;
}

// Example: Get available symbols
async function getSymbols() {
    try {
        const response = await fetch(`${API_BASE_URL}/symbols`, { headers });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        return handleApiError(result);
    } catch (error) {
        console.error("Error fetching symbols:", error);
        return [];
    }
}

// Example: Load OHLCV data
async function loadData(symbol, timeframe, startDate = null, endDate = null) {
    try {
        const payload = {
            symbol,
            timeframe
        };
        
        if (startDate) {
            payload.start_date = startDate;
        }
        
        if (endDate) {
            payload.end_date = endDate;
        }
        
        const response = await fetch(`${API_BASE_URL}/data/load`, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        return handleApiError(result);
    } catch (error) {
        console.error("Error loading data:", error);
        return {};
    }
}

// Example: Calculate indicators
async function calculateIndicators(symbol, timeframe, indicators, startDate = null, endDate = null) {
    try {
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
        
        const response = await fetch(`${API_BASE_URL}/indicators/calculate`, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        return handleApiError(result);
    } catch (error) {
        console.error("Error calculating indicators:", error);
        return {};
    }
}

// Usage example
async function runDemo() {
    try {
        // Get symbols
        const symbols = await getSymbols();
        console.log("Available symbols:", symbols);
        
        // Load data for AAPL
        const data = await loadData("AAPL", "1d", "2023-01-01", "2023-01-31");
        console.log(`Loaded ${data.dates.length} days of data for AAPL`);
        
        // Calculate RSI and SMA
        const indicators = [
            {
                id: "RSIIndicator",
                parameters: {
                    period: 14,
                    source: "close"
                }
            },
            {
                id: "SimpleMovingAverage",
                parameters: {
                    period: 20,
                    source: "close"
                }
            }
        ];
        
        const indicatorData = await calculateIndicators("AAPL", "1d", indicators, "2023-01-01", "2023-01-31");
        console.log("Calculated indicators:", Object.keys(indicatorData.indicators));
    } catch (error) {
        console.error("Demo failed:", error);
    }
}

// Run the demo
runDemo();
```

### 3.2 TypeScript Client Library

```typescript
// ktrdr-client.ts

// API Response types
interface ApiResponse<T> {
    success: boolean;
    data?: T;
    error?: ApiError;
}

interface ApiError {
    code: string;
    message: string;
    details?: Record<string, any>;
}

// Data types
interface SymbolInfo {
    symbol: string;
    name: string;
    exchange: string;
    type: string;
    currency: string;
}

interface TimeframeInfo {
    id: string;
    name: string;
    seconds: number;
    description: string;
}

interface OHLCVData {
    dates: string[];
    ohlcv: number[][];
    metadata: {
        symbol: string;
        timeframe: string;
        start_date: string;
        end_date: string;
        point_count: number;
        source: string;
    };
}

interface DataRangeInfo {
    symbol: string;
    timeframe: string;
    start_date: string;
    end_date: string;
    point_count: number;
}

// Indicator types
interface IndicatorParameter {
    name: string;
    type: string;
    description: string;
    default: any;
    min_value?: number;
    max_value?: number;
    options?: string[];
}

interface IndicatorInfo {
    id: string;
    name: string;
    description: string;
    type: string;
    parameters: IndicatorParameter[];
}

interface IndicatorConfig {
    id: string;
    parameters: Record<string, any>;
    output_name?: string;
}

interface IndicatorData {
    dates: string[];
    indicators: Record<string, number[]>;
    metadata: {
        symbol: string;
        timeframe: string;
        start_date: string;
        end_date: string;
        points: number;
        total_items: number;
        total_pages: number;
        current_page: number;
        page_size: number;
        has_next: boolean;
        has_prev: boolean;
    };
}

// Fuzzy types
interface FuzzyIndicatorInfo {
    id: string;
    name: string;
    fuzzy_sets: string[];
    output_columns: string[];
}

interface FuzzySetConfig {
    type: string;
    parameters: number[] | Record<string, any>;
}

interface FuzzyIndicatorConfig {
    name: string;
    source_column: string;
    parameters?: Record<string, any>;
    fuzzy_sets?: Record<string, FuzzySetConfig>;
}

interface FuzzyEvaluateData {
    indicator: string;
    fuzzy_sets: string[];
    values: Record<string, number[]>;
    points: number;
}

interface FuzzyData {
    symbol: string;
    timeframe: string;
    dates: string[];
    indicators: Record<string, Record<string, number[]>>;
    metadata: {
        start_date: string;
        end_date: string;
        points: number;
    };
}

// Custom error class
class KTRDRApiError extends Error {
    code: string;
    details?: Record<string, any>;
    
    constructor(code: string, message: string, details?: Record<string, any>) {
        super(message);
        this.name = "KTRDRApiError";
        this.code = code;
        this.details = details;
    }
}

// Retry configuration
interface RetryConfig {
    maxRetries: number;
    initialDelay: number;
    maxDelay: number;
    backoffFactor: number;
}

// API Client class
class KTRDRApiClient {
    private baseUrl: string;
    private headers: Record<string, string>;
    private retryConfig: RetryConfig;
    
    constructor(
        baseUrl: string, 
        apiKey?: string, 
        retryConfig?: Partial<RetryConfig>
    ) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
        
        this.headers = {
            "Content-Type": "application/json",
            "User-Agent": "KTRDR-TypeScript-Client/1.0"
        };
        
        if (apiKey) {
            this.headers["X-API-Key"] = apiKey;
        }
        
        this.retryConfig = {
            maxRetries: retryConfig?.maxRetries ?? 3,
            initialDelay: retryConfig?.initialDelay ?? 500,
            maxDelay: retryConfig?.maxDelay ?? 5000,
            backoffFactor: retryConfig?.backoffFactor ?? 2
        };
    }
    
    // Helper method to handle API responses
    private async handleResponse<T>(response: Response): Promise<T> {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result: ApiResponse<T> = await response.json();
        
        if (!result.success) {
            const error = result.error || { code: "UNKNOWN_ERROR", message: "Unknown error occurred" };
            throw new KTRDRApiError(error.code, error.message, error.details);
        }
        
        return result.data as T;
    }
    
    // Helper method for making requests with retry logic
    private async makeRequest<T>(
        method: string,
        path: string,
        data?: any
    ): Promise<T> {
        const url = `${this.baseUrl}/${path.startsWith("/") ? path.substring(1) : path}`;
        let retries = 0;
        let delay = this.retryConfig.initialDelay;
        
        while (true) {
            try {
                const options: RequestInit = {
                    method,
                    headers: this.headers
                };
                
                if (data && method !== "GET") {
                    options.body = JSON.stringify(data);
                }
                
                const response = await fetch(url, options);
                return await this.handleResponse<T>(response);
            } catch (error) {
                if (
                    retries >= this.retryConfig.maxRetries ||
                    error instanceof KTRDRApiError
                ) {
                    // Don't retry API-level errors or if max retries reached
                    throw error;
                }
                
                retries++;
                // Wait with exponential backoff
                await new Promise(resolve => setTimeout(resolve, delay));
                delay = Math.min(delay * this.retryConfig.backoffFactor, this.retryConfig.maxDelay);
            }
        }
    }
    
    // Data endpoints
    async getSymbols(): Promise<SymbolInfo[]> {
        return this.makeRequest<SymbolInfo[]>("GET", "symbols");
    }
    
    async getTimeframes(): Promise<TimeframeInfo[]> {
        return this.makeRequest<TimeframeInfo[]>("GET", "timeframes");
    }
    
    async loadData(
        symbol: string,
        timeframe: string,
        startDate?: string,
        endDate?: string
    ): Promise<OHLCVData> {
        const data: any = {
            symbol,
            timeframe
        };
        
        if (startDate) data.start_date = startDate;
        if (endDate) data.end_date = endDate;
        
        return this.makeRequest<OHLCVData>("POST", "data/load", data);
    }
    
    async getDataRange(
        symbol: string,
        timeframe: string
    ): Promise<DataRangeInfo> {
        const data = {
            symbol,
            timeframe
        };
        
        return this.makeRequest<DataRangeInfo>("POST", "data/range", data);
    }
    
    // Indicator endpoints
    async getIndicators(): Promise<IndicatorInfo[]> {
        return this.makeRequest<IndicatorInfo[]>("GET", "indicators");
    }
    
    async calculateIndicators(
        symbol: string,
        timeframe: string,
        indicators: IndicatorConfig[],
        startDate?: string,
        endDate?: string
    ): Promise<IndicatorData> {
        const data: any = {
            symbol,
            timeframe,
            indicators
        };
        
        if (startDate) data.start_date = startDate;
        if (endDate) data.end_date = endDate;
        
        return this.makeRequest<IndicatorData>("POST", "indicators/calculate", data);
    }
    
    // Fuzzy logic endpoints
    async getFuzzyIndicators(): Promise<FuzzyIndicatorInfo[]> {
        return this.makeRequest<FuzzyIndicatorInfo[]>("GET", "fuzzy/indicators");
    }
    
    async getFuzzySets(indicator: string): Promise<Record<string, FuzzySetConfig>> {
        return this.makeRequest<Record<string, FuzzySetConfig>>("GET", `fuzzy/sets/${indicator}`);
    }
    
    async evaluateFuzzy(
        indicator: string,
        values: number[],
        dates?: string[]
    ): Promise<FuzzyEvaluateData> {
        const data: any = {
            indicator,
            values
        };
        
        if (dates) data.dates = dates;
        
        return this.makeRequest<FuzzyEvaluateData>("POST", "fuzzy/evaluate", data);
    }
    
    async fuzzifyData(
        symbol: string,
        timeframe: string,
        indicators: FuzzyIndicatorConfig[],
        startDate?: string,
        endDate?: string
    ): Promise<FuzzyData> {
        const data: any = {
            symbol,
            timeframe,
            indicators
        };
        
        if (startDate) data.start_date = startDate;
        if (endDate) data.end_date = endDate;
        
        return this.makeRequest<FuzzyData>("POST", "fuzzy/data", data);
    }
}

// Usage example
async function main() {
    // Create client
    const client = new KTRDRApiClient("http://localhost:8000/api/v1");
    
    try {
        // Get symbols
        const symbols = await client.getSymbols();
        console.log("Available symbols:", symbols);
        
        // Load data
        const data = await client.loadData("AAPL", "1d", "2023-01-01", "2023-01-31");
        console.log(`Loaded ${data.dates.length} days of data for AAPL`);
        
        // Calculate indicators
        const indicators: IndicatorConfig[] = [
            {
                id: "RSIIndicator",
                parameters: {
                    period: 14,
                    source: "close"
                }
            },
            {
                id: "SimpleMovingAverage",
                parameters: {
                    period: 20,
                    source: "close"
                }
            }
        ];
        
        const indicatorData = await client.calculateIndicators(
            "AAPL", "1d", indicators, "2023-01-01", "2023-01-31"
        );
        console.log("Calculated indicators:", Object.keys(indicatorData.indicators));
        
        // Get fuzzy sets
        const fuzzySets = await client.getFuzzySets("rsi");
        console.log("RSI fuzzy sets:", Object.keys(fuzzySets));
        
        // Fuzzify data
        const fuzzyIndicators: FuzzyIndicatorConfig[] = [
            {
                name: "rsi",
                source_column: "close"
            }
        ];
        
        const fuzzyData = await client.fuzzifyData(
            "AAPL", "1d", fuzzyIndicators, "2023-01-01", "2023-01-31"
        );
        console.log("Fuzzified RSI:", Object.keys(fuzzyData.indicators.rsi));
        
    } catch (error) {
        if (error instanceof KTRDRApiError) {
            console.error(`API Error (${error.code}): ${error.message}`);
            if (error.details) {
                console.error("Details:", error.details);
            }
        } else {
            console.error("Error:", error);
        }
    }
}

// Run the example
main();
```

## 4. Other Language Examples

### 4.1 Java Integration

```java
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

public class KtrdrApiExample {

    private static final String API_BASE_URL = "http://localhost:8000/api/v1";
    private static final ObjectMapper objectMapper = new ObjectMapper();
    private static final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    public static void main(String[] args) {
        try {
            // Get symbols
            var symbols = getSymbols();
            System.out.println("Available symbols: " + symbols);

            // Load OHLCV data
            var data = loadData("AAPL", "1d", "2023-01-01", "2023-01-31");
            System.out.println("Loaded data for AAPL: " + data);

        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> getSymbols() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .GET()
                .uri(URI.create(API_BASE_URL + "/symbols"))
                .header("Content-Type", "application/json")
                .header("User-Agent", "KTRDR-Java-Client/1.0")
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("HTTP error code: " + response.statusCode());
        }

        Map<String, Object> responseMap = objectMapper.readValue(response.body(), Map.class);

        if (!(Boolean) responseMap.get("success")) {
            Map<String, Object> error = (Map<String, Object>) responseMap.get("error");
            throw new IOException("API error: " + error.get("message"));
        }

        return (Map<String, Object>) responseMap.get("data");
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> loadData(String symbol, String timeframe, String startDate, String endDate)
            throws IOException, InterruptedException {
        
        Map<String, Object> requestData = new HashMap<>();
        requestData.put("symbol", symbol);
        requestData.put("timeframe", timeframe);
        
        if (startDate != null) {
            requestData.put("start_date", startDate);
        }
        
        if (endDate != null) {
            requestData.put("end_date", endDate);
        }

        String requestBody = objectMapper.writeValueAsString(requestData);

        HttpRequest request = HttpRequest.newBuilder()
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .uri(URI.create(API_BASE_URL + "/data/load"))
                .header("Content-Type", "application/json")
                .header("User-Agent", "KTRDR-Java-Client/1.0")
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("HTTP error code: " + response.statusCode());
        }

        Map<String, Object> responseMap = objectMapper.readValue(response.body(), Map.class);

        if (!(Boolean) responseMap.get("success")) {
            Map<String, Object> error = (Map<String, Object>) responseMap.get("error");
            throw new IOException("API error: " + error.get("message"));
        }

        return (Map<String, Object>) responseMap.get("data");
    }
}
```

### 4.2 C# Integration

```csharp
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace KtrdrApiClient
{
    public class KtrdrApiExample
    {
        private static readonly string ApiBaseUrl = "http://localhost:8000/api/v1";
        private static readonly HttpClient Client = new HttpClient();

        static async Task Main(string[] args)
        {
            // Configure client
            Client.DefaultRequestHeaders.Accept.Clear();
            Client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            Client.DefaultRequestHeaders.Add("User-Agent", "KTRDR-CSharp-Client/1.0");

            try
            {
                // Get symbols
                var symbols = await GetSymbols();
                Console.WriteLine($"Available symbols: {JsonSerializer.Serialize(symbols)}");

                // Load data
                var data = await LoadData("AAPL", "1d", "2023-01-01", "2023-01-31");
                Console.WriteLine($"Loaded data for AAPL: {JsonSerializer.Serialize(data)}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error: {ex.Message}");
            }
        }

        private static async Task<object> GetSymbols()
        {
            HttpResponseMessage response = await Client.GetAsync($"{ApiBaseUrl}/symbols");
            response.EnsureSuccessStatusCode();
            
            string responseBody = await response.Content.ReadAsStringAsync();
            using JsonDocument doc = JsonDocument.Parse(responseBody);
            
            JsonElement root = doc.RootElement;
            bool success = root.GetProperty("success").GetBoolean();
            
            if (!success)
            {
                var error = root.GetProperty("error");
                string message = error.GetProperty("message").GetString();
                throw new Exception($"API error: {message}");
            }
            
            return JsonSerializer.Deserialize<object>(root.GetProperty("data").ToString());
        }

        private static async Task<object> LoadData(string symbol, string timeframe, string startDate = null, string endDate = null)
        {
            var requestData = new Dictionary<string, string>
            {
                { "symbol", symbol },
                { "timeframe", timeframe }
            };
            
            if (startDate != null)
                requestData.Add("start_date", startDate);
                
            if (endDate != null)
                requestData.Add("end_date", endDate);
                
            var content = new StringContent(
                JsonSerializer.Serialize(requestData),
                Encoding.UTF8,
                "application/json");
                
            HttpResponseMessage response = await Client.PostAsync($"{ApiBaseUrl}/data/load", content);
            response.EnsureSuccessStatusCode();
            
            string responseBody = await response.Content.ReadAsStringAsync();
            using JsonDocument doc = JsonDocument.Parse(responseBody);
            
            JsonElement root = doc.RootElement;
            bool success = root.GetProperty("success").GetBoolean();
            
            if (!success)
            {
                var error = root.GetProperty("error");
                string message = error.GetProperty("message").GetString();
                throw new Exception($"API error: {message}");
            }
            
            return JsonSerializer.Deserialize<object>(root.GetProperty("data").ToString());
        }
    }
}
```

## 5. Client Integration Best Practices

### 5.1 Error Handling

Always implement proper error handling to distinguish between:

1. **Transport Errors**: Network issues, timeouts, connection failures
   - Implement retry logic with backoff for these errors
   - Log detailed transport error information

2. **API Errors**: Validation failures, data not found, processing errors
   - Parse the error response and extract error code, message, and details
   - Present meaningful error messages to users
   - Log API errors with contextual information

Example of comprehensive error handling:

```python
try:
    # Make API request
    result = client.load_data("AAPL", "1d")
except requests.exceptions.ConnectionError:
    # Handle transport error
    print("Connection error - server may be down or unreachable")
    log_transport_error("connection_error", "AAPL", "1d")
    # Implement retry with backoff
except requests.exceptions.Timeout:
    # Handle timeout
    print("Request timed out - server may be overloaded")
    log_transport_error("timeout", "AAPL", "1d")
    # Implement retry with backoff
except KTRDRApiError as e:
    # Handle API error
    if e.code == "DATA-NotFound":
        print(f"Data not found: {e.message}")
        # Handle specific error case
    elif e.code == "VALIDATION_ERROR":
        print(f"Invalid parameters: {e.details}")
        # Handle validation error
    else:
        print(f"API error: {e.message}")
        # Handle other API errors
except Exception as e:
    # Handle unexpected errors
    print(f"Unexpected error: {str(e)}")
    log_unexpected_error(e)
```

### 5.2 Performance Optimization

1. **Connection Pooling**: Reuse HTTP connections
   ```python
   # Python example with session
   session = requests.Session()
   # Use session for all requests
   response = session.get(url)
   ```

2. **Batch Processing**: Combine multiple requests when possible
   ```python
   # Instead of multiple indicator calculations
   client.calculate_indicators("AAPL", "1d", [
       {"id": "RSI", "parameters": {"period": 14}},
       {"id": "SMA", "parameters": {"period": 20}},
       {"id": "MACD", "parameters": {...}}
   ])
   ```

3. **Data Pagination**: Handle large datasets with pagination
   ```python
   # Handle paginated results
   page = 1
   page_size = 1000
   all_data = []
   
   while True:
       data = client.load_data("AAPL", "1d", page=page, page_size=page_size)
       all_data.extend(data["dates"])
       
       if not data["metadata"]["has_next"]:
           break
           
       page += 1
   ```

4. **Caching**: Implement client-side caching for frequently used data
   ```python
   # Simple cache implementation
   cache = {}
   
   def get_cached_data(key, ttl=300):
       if key in cache:
           entry = cache[key]
           if time.time() - entry['timestamp'] < ttl:
               return entry['data']
       return None
   
   def set_cached_data(key, data):
       cache[key] = {
           'data': data,
           'timestamp': time.time()
       }
   
   # Using the cache
   cache_key = f"symbols_{exchange}"
   data = get_cached_data(cache_key)
   
   if data is None:
       data = client.get_symbols(exchange)
       set_cached_data(cache_key, data)
   ```

### 5.3 Reliability

1. **Retry Logic**: Implement exponential backoff for transient failures
   ```python
   def retry_with_backoff(func, max_retries=3, initial_delay=0.5, max_delay=8):
       """Retry a function with exponential backoff."""
       retries = 0
       delay = initial_delay
       
       while True:
           try:
               return func()
           except (requests.exceptions.ConnectionError, 
                  requests.exceptions.Timeout) as e:
               retries += 1
               if retries > max_retries:
                   raise
               
               sleep_time = min(delay * (2 ** (retries - 1)), max_delay)
               print(f"Retrying in {sleep_time:.2f} seconds...")
               time.sleep(sleep_time)
   ```

2. **Circuit Breaker**: Prevent overwhelming failing services
   ```python
   class CircuitBreaker:
       def __init__(self, failure_threshold=5, recovery_timeout=30):
           self.failure_count = 0
           self.failure_threshold = failure_threshold
           self.recovery_timeout = recovery_timeout
           self.last_failure_time = 0
           self.open = False
           
       def execute(self, func):
           if self.open:
               if time.time() - self.last_failure_time > self.recovery_timeout:
                   # Try to recover
                   self.open = False
               else:
                   raise Exception("Circuit breaker is open")
                   
           try:
               result = func()
               # Success - reset count
               self.failure_count = 0
               return result
           except Exception as e:
               # Failure - increment count
               self.failure_count += 1
               self.last_failure_time = time.time()
               
               if self.failure_count >= self.failure_threshold:
                   self.open = True
                   
               raise
   ```

### 5.4 Security

1. **API Key Management**: Store API keys securely
   ```python
   # Load API key from environment variable
   api_key = os.environ.get("KTRDR_API_KEY")
   if not api_key:
       raise ValueError("KTRDR_API_KEY environment variable not set")
   
   client = KTRDRApiClient(base_url, api_key)
   ```

2. **HTTPS Verification**: Always verify SSL certificates
   ```python
   # Ensure proper certificate verification
   session = requests.Session()
   session.verify = True  # Default is True, but be explicit
   
   # Or provide a CA certificate bundle
   session.verify = "/path/to/cacert.pem"
   ```

3. **Input Validation**: Validate client-side inputs before sending to API
   ```python
   def validate_timeframe(timeframe):
       """Validate timeframe parameter."""
       valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
       if timeframe not in valid_timeframes:
           raise ValueError(f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}")
       return timeframe
   
   # Use validation in client methods
   timeframe = validate_timeframe(timeframe)
   ```