# KTRDR API Performance Recommendations

This document provides recommendations and best practices for optimizing performance when using the KTRDR API.

## 1. Data Transfer Optimization

### 1.1 Request Sizing

The volume of data transferred significantly impacts API performance. To optimize:

1. **Minimize Date Ranges**:
   - Request only the data you need
   - Split large historical requests into smaller chunks
   - Example:
     ```python
     # Instead of a single large request
     # data = client.load_data("AAPL", "1d", "2010-01-01", "2023-01-01")
     
     # Use quarterly chunks for better performance
     quarters = [
         ("2022-01-01", "2022-03-31"),
         ("2022-04-01", "2022-06-30"),
         ("2022-07-01", "2022-09-30"),
         ("2022-10-01", "2022-12-31")
     ]
     
     all_data = []
     for start_date, end_date in quarters:
         chunk = client.load_data("AAPL", "1d", start_date, end_date)
         all_data.append(chunk)
     
     # Combine data as needed
     ```

2. **Use Pagination**:
   - For large datasets, use pagination parameters
   - Typical optimal page size: 500-1000 items
   - Example:
     ```python
     # Request with pagination
     all_data = []
     page = 1
     page_size = 1000
     
     while True:
         response = client.load_data(
             "AAPL", "1d", "2022-01-01", "2022-12-31",
             page=page, page_size=page_size
         )
         
         all_data.extend(response["data"])
         
         if not response["metadata"]["has_next"]:
             break
             
         page += 1
     ```

3. **Binary Data Format**:
   - Use binary format for large data transfers when available
   - The `/api/v1/data/load/binary` endpoint supports MessagePack format
   - Example:
     ```python
     import requests
     import msgpack
     
     response = requests.post(
         "http://localhost:8000/api/v1/data/load/binary",
         headers={"Accept": "application/x-msgpack"},
         json={"symbol": "AAPL", "timeframe": "1d"}
     )
     
     # Parse MessagePack response
     data = msgpack.unpackb(response.content)
     ```

### 1.2 Data Compression

Enable compression to reduce bandwidth usage:

1. **Request Compression**:
   - Add appropriate headers to enable compression
   - Example:
     ```python
     headers = {
         "Content-Type": "application/json",
         "Accept-Encoding": "gzip, deflate"
     }
     
     response = requests.get(url, headers=headers)
     # Response will be automatically decompressed by requests
     ```

2. **Batch Requests**:
   - Combine multiple operations into a single request when possible
   - Example:
     ```python
     # Instead of multiple indicator calculations
     indicators = [
         {"id": "RSIIndicator", "parameters": {"period": 14}},
         {"id": "SimpleMovingAverage", "parameters": {"period": 20}},
         {"id": "BollingerBands", "parameters": {"window": 20, "window_dev": 2}}
     ]
     
     # Use a single request
     result = client.calculate_indicators("AAPL", "1d", indicators)
     ```

## 2. Client-Side Optimization

### 2.1 Connection Management

1. **Connection Pooling**:
   - Reuse HTTP connections for multiple requests
   - Example in Python:
     ```python
     import requests
     
     # Create a session for connection pooling
     session = requests.Session()
     
     # Use session for all requests
     response1 = session.get("http://localhost:8000/api/v1/symbols")
     response2 = session.get("http://localhost:8000/api/v1/timeframes")
     
     # Close session when done
     session.close()
     ```

   - Example in JavaScript:
     ```javascript
     // Modern browsers automatically pool connections
     // Just ensure you're not creating new AbortControllers unnecessarily
     
     const controller = new AbortController();
     const signal = controller.signal;
     
     // Use same controller for related requests
     fetch(url1, { signal })
     fetch(url2, { signal })
     ```

2. **Persistent Connections**:
   - Set appropriate keep-alive settings
   - Example:
     ```python
     import requests
     from requests.adapters import HTTPAdapter
     
     session = requests.Session()
     
     # Configure longer keep-alive
     adapter = HTTPAdapter(
         pool_connections=10,
         pool_maxsize=100,
         max_retries=3,
         pool_block=False
     )
     
     session.mount('http://', adapter)
     session.mount('https://', adapter)
     ```

### 2.2 Caching

Implement client-side caching for frequently accessed data:

1. **Simple In-Memory Cache**:
   ```python
   import time
   
   # Simple cache implementation
   cache = {}
   
   def get_cached_data(key, ttl=300):
       """Get data from cache if still valid."""
       if key in cache:
           entry = cache[key]
           if time.time() - entry['timestamp'] < ttl:
               return entry['data']
       return None
   
   def set_cached_data(key, data):
       """Store data in cache."""
       cache[key] = {
           'data': data,
           'timestamp': time.time()
       }
   
   # Usage example
   def get_symbols(force_refresh=False):
       cache_key = "symbols"
       
       if not force_refresh:
           cached = get_cached_data(cache_key)
           if cached:
               return cached
       
       # Cache miss or forced refresh
       symbols = client.get_symbols()
       set_cached_data(cache_key, symbols)
       return symbols
   ```

2. **Cache Static Data**:
   - Cache symbols, timeframes, indicator definitions
   - These rarely change and are good candidates for longer cache TTLs
   - Example:
     ```python
     # Cache symbols for 1 hour (3600 seconds)
     symbols = get_cached_data("symbols", ttl=3600)
     if not symbols:
         symbols = client.get_symbols()
         set_cached_data("symbols", symbols)
     
     # Cache timeframes for 1 day (86400 seconds)
     timeframes = get_cached_data("timeframes", ttl=86400)
     if not timeframes:
         timeframes = client.get_timeframes()
         set_cached_data("timeframes", timeframes)
     ```

3. **Cache Configuration**:
   - Configure cache size limits to prevent memory issues
   - Implement a cache eviction policy (LRU is recommended)
   - Consider persistent caching for offline usage

### 2.3 Parallel Processing

For multiple independent requests, use parallel processing:

1. **Asynchronous Requests**:
   - Python with aiohttp:
     ```python
     import aiohttp
     import asyncio
     
     async def fetch_data(session, symbol, timeframe):
         url = f"http://localhost:8000/api/v1/data/load"
         payload = {"symbol": symbol, "timeframe": timeframe}
         
         async with session.post(url, json=payload) as response:
             return await response.json()
     
     async def fetch_multiple_symbols():
         symbols = ["AAPL", "MSFT", "GOOG", "AMZN"]
         timeframe = "1d"
         
         async with aiohttp.ClientSession() as session:
             tasks = []
             for symbol in symbols:
                 task = asyncio.create_task(fetch_data(session, symbol, timeframe))
                 tasks.append(task)
             
             return await asyncio.gather(*tasks)
     
     # Run the async function
     results = asyncio.run(fetch_multiple_symbols())
     ```

   - JavaScript with Promise.all:
     ```javascript
     async function fetchMultipleSymbols() {
         const symbols = ["AAPL", "MSFT", "GOOG", "AMZN"];
         const timeframe = "1d";
         const url = "http://localhost:8000/api/v1/data/load";
         
         const fetchPromises = symbols.map(symbol => {
             return fetch(url, {
                 method: 'POST',
                 headers: {'Content-Type': 'application/json'},
                 body: JSON.stringify({symbol, timeframe})
             }).then(response => response.json());
         });
         
         return Promise.all(fetchPromises);
     }
     
     // Use the function
     fetchMultipleSymbols().then(results => {
         console.log("All data loaded:", results);
     });
     ```

2. **Concurrent Request Limits**:
   - Don't make too many concurrent requests (can trigger rate limiting)
   - Recommended: 4-8 concurrent requests maximum
   - Example with limiting concurrency:
     ```python
     import asyncio
     from aiohttp import ClientSession
     from asyncio import Semaphore
     
     async def fetch_with_limit(session, semaphore, symbol, timeframe):
         async with semaphore:  # Limit concurrency
             url = f"http://localhost:8000/api/v1/data/load"
             payload = {"symbol": symbol, "timeframe": timeframe}
             
             async with session.post(url, json=payload) as response:
                 return await response.json()
     
     async def fetch_multiple_symbols_limited():
         symbols = ["AAPL", "MSFT", "GOOG", "AMZN", "FB", "TSLA", "NFLX", "BABA"]
         timeframe = "1d"
         
         # Limit to 4 concurrent requests
         semaphore = Semaphore(4)
         
         async with ClientSession() as session:
             tasks = []
             for symbol in symbols:
                 task = asyncio.create_task(
                     fetch_with_limit(session, semaphore, symbol, timeframe)
                 )
                 tasks.append(task)
             
             return await asyncio.gather(*tasks)
     ```

## 3. Request Efficiency

### 3.1 Data Selection Optimization

1. **Select Only Required Fields**:
   - Some endpoints support field selection parameters
   - Example:
     ```python
     # Request only specific fields
     response = client.load_data(
         "AAPL", "1d",
         include_fields=["dates", "close", "volume"]  # Only get date, close, volume
     )
     ```

2. **Optimize Indicator Calculations**:
   - Request only needed indicators with appropriate precision
   - Example:
     ```python
     # Request with decimal precision to reduce data size
     indicators = [
         {
             "id": "RSIIndicator",
             "parameters": {"period": 14},
             "precision": 2  # Round to 2 decimal places
         }
     ]
     ```

3. **Date Range Queries**:
   - Use the data range endpoint to determine available data
   - Then request only relevant date ranges
   - Example:
     ```python
     # First check available data range
     range_info = client.get_data_range("AAPL", "1d")
     
     # Then request only within available range
     start_date = max(desired_start, range_info["start_date"])
     end_date = min(desired_end, range_info["end_date"])
     
     data = client.load_data("AAPL", "1d", start_date, end_date)
     ```

### 3.2 Batching and Chunking

1. **Indicator Batching**:
   - Batch indicator calculations in a single request
   - Better than multiple separate requests
   - Example:
     ```python
     # Process multiple indicators in one request
     indicators = [
         {"id": "RSIIndicator", "parameters": {"period": 14}},
         {"id": "SimpleMovingAverage", "parameters": {"period": 20}},
         {"id": "BollingerBands", "parameters": {"window": 20}}
     ]
     
     data = client.calculate_indicators("AAPL", "1d", indicators)
     ```

2. **Symbol Chunking**:
   - Process symbols in reasonable-sized chunks
   - Example:
     ```python
     # All symbols
     all_symbols = ["AAPL", "MSFT", "GOOG", ..., "TSLA"]  # Could be 100+ symbols
     
     # Process in chunks of 10
     chunk_size = 10
     results = {}
     
     for i in range(0, len(all_symbols), chunk_size):
         chunk = all_symbols[i:i+chunk_size]
         # Process this chunk
         for symbol in chunk:
             results[symbol] = client.load_data(symbol, "1d")
     ```

## 4. Advanced Optimization Techniques

### 4.1 Client-Side Data Processing

1. **Stream Processing**:
   - Process data as it arrives rather than waiting for all data
   - Example with Python generators:
     ```python
     def process_data_stream(symbol, timeframe, start_date, end_date):
         # Split into monthly chunks
         current = start_date
         while current < end_date:
             # Calculate next month
             next_month = calculate_next_month(current)
             next_date = min(next_month, end_date)
             
             # Get data for this month
             chunk = client.load_data(symbol, timeframe, current, next_date)
             
             # Process incrementally
             yield chunk
             
             # Move to next month
             current = next_date
     
     # Usage example
     for data_chunk in process_data_stream("AAPL", "1d", "2022-01-01", "2022-12-31"):
         # Process each chunk as it arrives
         process_chunk(data_chunk)
     ```

2. **Local Computation**:
   - For simple calculations, download raw data and compute locally
   - Reduces server load and network traffic for repeated analysis
   - Example:
     ```python
     # Get raw OHLCV data
     data = client.load_data("AAPL", "1d")
     
     # Local simple calculations
     import numpy as np
     import pandas as pd
     
     # Convert to pandas
     df = pd.DataFrame(
         data["ohlcv"],
         columns=["open", "high", "low", "close", "volume"],
         index=pd.to_datetime(data["dates"])
     )
     
     # Local SMA calculation
     df["sma_20"] = df["close"].rolling(window=20).mean()
     
     # Local RSI calculation
     def calculate_rsi(series, period=14):
         delta = series.diff()
         gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
         loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
         rs = gain / loss
         return 100 - (100 / (1 + rs))
         
     df["rsi_14"] = calculate_rsi(df["close"], 14)
     ```

### 4.2 Background Processing

1. **Pre-fetch Common Data**:
   - Load commonly used data on application startup
   - Store in memory for instant access
   - Example:
     ```python
     # Application startup initialization
     class KTRDRApplication:
         def __init__(self):
             self.client = KTRDRApiClient("http://localhost:8000/api/v1")
             self.cache = {}
             
             # Pre-fetch common data
             self.initialize_cache()
             
         def initialize_cache(self):
             """Pre-fetch common data on startup."""
             self.cache["symbols"] = self.client.get_symbols()
             self.cache["timeframes"] = self.client.get_timeframes()
             self.cache["indicators"] = self.client.get_indicators()
             
             # Pre-fetch commonly used data for main symbols
             main_symbols = ["SPY", "QQQ", "AAPL", "MSFT"]
             for symbol in main_symbols:
                 self.cache[f"{symbol}_1d"] = self.client.load_data(symbol, "1d")
     ```

2. **Scheduled Updates**:
   - Set up background tasks to refresh data periodically
   - Example:
     ```python
     import threading
     import time
     
     class KTRDRApplication:
         def __init__(self):
             self.client = KTRDRApiClient("http://localhost:8000/api/v1")
             self.cache = {}
             
             # Start background updater
             self.start_background_updater()
             
         def update_cache(self):
             """Update cache with fresh data."""
             self.cache["symbols"] = self.client.get_symbols()
             # Update other cached data
             
         def start_background_updater(self):
             """Start background thread to update cache."""
             def updater():
                 while True:
                     try:
                         self.update_cache()
                     except Exception as e:
                         print(f"Error updating cache: {e}")
                     
                     # Wait for next update (hourly)
                     time.sleep(3600)
             
             # Start thread
             update_thread = threading.Thread(target=updater, daemon=True)
             update_thread.start()
     ```

### 4.3 Error Handling Optimization

1. **Retry with Backoff**:
   - Implement exponential backoff for transient errors
   - Example:
     ```python
     import time
     
     def retry_with_backoff(func, max_retries=3, initial_delay=0.5, max_delay=8):
         """Retry a function with exponential backoff."""
         retries = 0
         while True:
             try:
                 return func()
             except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                 retries += 1
                 if retries > max_retries:
                     raise
                 
                 delay = min(initial_delay * (2 ** (retries - 1)), max_delay)
                 print(f"Retrying in {delay:.2f} seconds...")
                 time.sleep(delay)
     
     # Usage
     data = retry_with_backoff(lambda: client.load_data("AAPL", "1d"))
     ```

2. **Circuit Breaker**:
   - Avoid overwhelming failing services
   - Example:
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
                 
     # Usage
     breaker = CircuitBreaker()
     try:
         data = breaker.execute(lambda: client.load_data("AAPL", "1d"))
     except Exception as e:
         print(f"Request failed: {e}")
     ```

## 5. Performance Monitoring

### 5.1 Request Timing

Monitor API performance to identify bottlenecks:

```python
import time

def timed_request(func, *args, **kwargs):
    """Measure execution time of a function."""
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    
    execution_time = end_time - start_time
    print(f"Request took {execution_time:.2f} seconds")
    
    return result, execution_time

# Usage example
data, request_time = timed_request(client.load_data, "AAPL", "1d")

# Track performance over time
performance_history = []
performance_history.append({
    "timestamp": time.time(),
    "operation": "load_data",
    "parameters": {"symbol": "AAPL", "timeframe": "1d"},
    "execution_time": request_time
})
```

### 5.2 Performance Logging

Implement comprehensive performance logging:

```python
import logging
import time
import json
from datetime import datetime

# Configure logger
logging.basicConfig(level=logging.INFO)
performance_logger = logging.getLogger("performance")

class PerformanceMonitor:
    def __init__(self, log_file=None):
        self.history = []
        self.log_file = log_file
        
    def log_request(self, operation, parameters, execution_time):
        """Log a request and its performance metrics."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "parameters": parameters,
            "execution_time": execution_time
        }
        
        self.history.append(entry)
        performance_logger.info(
            f"Operation: {operation}, Parameters: {json.dumps(parameters)}, "
            f"Time: {execution_time:.2f}s"
        )
        
        # Write to log file if specified
        if self.log_file:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
    
    def track_operation(self, operation, parameters=None):
        """Decorator to track operation performance."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log the operation
                self.log_request(operation, parameters or {}, execution_time)
                
                return result
            return wrapper
        return decorator

# Usage
monitor = PerformanceMonitor(log_file="api_performance.log")

@monitor.track_operation("load_data", {"symbol": "AAPL", "timeframe": "1d"})
def fetch_apple_data():
    return client.load_data("AAPL", "1d")

# Call the tracked function
data = fetch_apple_data()
```

### 5.3 Performance Analysis

Regularly analyze performance data to identify optimization opportunities:

```python
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def analyze_performance(log_file, days=7):
    """Analyze performance logs for the last N days."""
    # Load performance data
    df = pd.read_json(log_file, lines=True)
    
    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Filter for recent data
    cutoff = datetime.now() - timedelta(days=days)
    recent_df = df[df["timestamp"] > cutoff]
    
    # Group by operation
    grouped = recent_df.groupby("operation")
    
    # Calculate statistics
    stats = grouped["execution_time"].agg(["min", "max", "mean", "median", "count"])
    
    # Plot performance trends
    plt.figure(figsize=(12, 6))
    
    for operation, group in grouped:
        plt.plot(group["timestamp"], group["execution_time"], label=operation)
    
    plt.title(f"API Performance (Last {days} Days)")
    plt.xlabel("Date")
    plt.ylabel("Execution Time (seconds)")
    plt.legend()
    plt.grid(True)
    plt.savefig("api_performance.png")
    
    return stats

# Run analysis
performance_stats = analyze_performance("api_performance.log")
print(performance_stats)
```

## 6. Summary of Recommendations

1. **Optimize Data Transfer**:
   - Use appropriate date ranges and pagination
   - Enable compression
   - Consider binary formats for large transfers

2. **Connection Management**:
   - Implement connection pooling
   - Use persistent connections with proper keep-alive settings

3. **Implement Caching**:
   - Cache static and semi-static data
   - Implement TTL-based caching
   - Consider offline caching for mobile/desktop applications

4. **Optimize Request Patterns**:
   - Batch related requests
   - Process data in appropriate chunks
   - Implement parallel processing with concurrency limits

5. **Implement Advanced Techniques**:
   - Stream processing for large datasets
   - Local computation when appropriate
   - Background processing and pre-fetching

6. **Error Handling Optimization**:
   - Implement retry with backoff
   - Consider circuit breaker pattern
   - Log and analyze errors for patterns

7. **Monitor Performance**:
   - Track request timing
   - Implement comprehensive logging
   - Regularly analyze performance metrics