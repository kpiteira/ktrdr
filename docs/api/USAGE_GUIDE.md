# KTRDR API Usage Guide

This guide provides common patterns and best practices for using the KTRDR API effectively.

## Table of Contents

- [Authentication](#authentication)
- [Data Retrieval Patterns](#data-retrieval-patterns)
- [Indicator Calculation Patterns](#indicator-calculation-patterns)
- [Fuzzy Logic Patterns](#fuzzy-logic-patterns)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)

## Authentication

Currently, the API doesn't require authentication, but it's designed to support API keys in future versions. When authentication is implemented, you'll need to include your API key in the `X-API-Key` header:

```python
import requests

headers = {
    "X-API-Key": "your-api-key-here",
    "Content-Type": "application/json"
}

response = requests.get("http://localhost:8000/api/v1/symbols", headers=headers)
```

## Data Retrieval Patterns

### Pattern 1: Check Available Data Before Loading

Before retrieving large amounts of data, it's a good practice to check the available date range first:

```python
import requests
import json

# 1. Check available date range
range_request = {
    "symbol": "AAPL",
    "timeframe": "1d"
}

range_response = requests.post(
    "http://localhost:8000/api/v1/data/range",
    json=range_request
)

range_data = range_response.json()
if range_data["success"]:
    start_date = range_data["data"]["start_date"]
    end_date = range_data["data"]["end_date"]
    print(f"Available data: {start_date} to {end_date}")
    
    # 2. Load only the data you need
    load_request = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "start_date": "2023-01-01T00:00:00",  # Adjust based on available data
        "end_date": "2023-01-31T23:59:59",    # Adjust based on available data
        "include_metadata": True
    }
    
    load_response = requests.post(
        "http://localhost:8000/api/v1/data/load",
        json=load_request
    )
    
    data = load_response.json()
    if data["success"]:
        print(f"Loaded {len(data['data']['dates'])} data points")
else:
    print(f"Error: {range_data['error']['message']}")
```

### Pattern 2: Iterative Data Loading with Pagination

For very large datasets, load data in chunks:

```python
import requests
import json
from datetime import datetime, timedelta

def load_data_in_chunks(symbol, timeframe, chunk_size_days=30):
    # 1. Get available date range
    range_request = {"symbol": symbol, "timeframe": timeframe}
    range_response = requests.post(
        "http://localhost:8000/api/v1/data/range", 
        json=range_request
    ).json()
    
    if not range_response["success"]:
        return None
    
    start_date = datetime.fromisoformat(range_response["data"]["start_date"])
    end_date = datetime.fromisoformat(range_response["data"]["end_date"])
    
    # 2. Initialize result container
    all_dates = []
    all_ohlcv = []
    
    # 3. Load data in chunks
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=chunk_size_days), end_date)
        
        load_request = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
            "include_metadata": False
        }
        
        load_response = requests.post(
            "http://localhost:8000/api/v1/data/load",
            json=load_request
        ).json()
        
        if load_response["success"]:
            all_dates.extend(load_response["data"]["dates"])
            all_ohlcv.extend(load_response["data"]["ohlcv"])
            print(f"Loaded chunk: {current_start.date()} to {current_end.date()}")
        else:
            print(f"Error loading chunk: {load_response['error']['message']}")
            
        current_start = current_end + timedelta(days=1)
    
    return {"dates": all_dates, "ohlcv": all_ohlcv}

# Example usage
apple_data = load_data_in_chunks("AAPL", "1d")
```

## Indicator Calculation Patterns

### Pattern 1: Discover and Calculate Multiple Indicators

First discover available indicators, then calculate multiple indicators in a single request:

```python
import requests
import json

# 1. Get available indicators
indicators_response = requests.get("http://localhost:8000/api/v1/indicators")
indicators = indicators_response.json()

if indicators["success"]:
    available_indicators = {i["id"]: i for i in indicators["data"]}
    print(f"Available indicators: {list(available_indicators.keys())}")
    
    # 2. Calculate multiple indicators in one request
    calc_request = {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "id": "RSIIndicator",
                "parameters": {
                    "period": 14,
                    "source": "close"
                },
                "output_name": "RSI_14"
            },
            {
                "id": "SimpleMovingAverage",
                "parameters": {
                    "period": 20,
                    "source": "close"
                },
                "output_name": "SMA_20"
            }
        ],
        "start_date": "2023-01-01T00:00:00",
        "end_date": "2023-03-31T23:59:59"
    }
    
    calc_response = requests.post(
        "http://localhost:8000/api/v1/indicators/calculate",
        json=calc_request
    )
    
    result = calc_response.json()
    if result["success"]:
        print(f"Calculated {len(result['indicators'])} indicators")
        # Process the data
    else:
        print(f"Error: {result['error']['message']}")
```

### Pattern 2: Paginated Indicator Results

For large datasets, use pagination to retrieve results in manageable chunks:

```python
import requests
import json

def get_paginated_indicators(request_data, page_size=1000):
    all_dates = []
    all_indicators = {}
    
    # Initialize with page 1
    page = 1
    has_more = True
    
    while has_more:
        # Add pagination parameters
        response = requests.post(
            "http://localhost:8000/api/v1/indicators/calculate",
            params={"page": page, "page_size": page_size},
            json=request_data
        ).json()
        
        if response["success"]:
            # Collect data from this page
            all_dates.extend(response["dates"])
            
            # Merge indicator values
            for ind_name, ind_values in response["indicators"].items():
                if ind_name not in all_indicators:
                    all_indicators[ind_name] = []
                all_indicators[ind_name].extend(ind_values)
            
            # Check if there are more pages
            has_more = response["metadata"]["has_next"]
            page += 1
            
            print(f"Loaded page {page-1} with {len(response['dates'])} points")
        else:
            print(f"Error: {response['error']['message']}")
            has_more = False
    
    return {
        "dates": all_dates,
        "indicators": all_indicators,
        "metadata": response.get("metadata", {})
    }
```

## Fuzzy Logic Patterns

### Pattern 1: Discover and Apply Fuzzy Sets

First discover available fuzzy indicators and their sets, then apply them to indicator values:

```python
import requests
import json

# 1. Get available fuzzy indicators
fuzzy_indicators_response = requests.get("http://localhost:8000/api/v1/fuzzy/indicators")
fuzzy_indicators = fuzzy_indicators_response.json()

if fuzzy_indicators["success"]:
    # 2. Get details about a specific fuzzy indicator (e.g., RSI)
    indicator_id = "rsi"  # Example: choose one from the list
    
    fuzzy_sets_response = requests.get(f"http://localhost:8000/api/v1/fuzzy/sets/{indicator_id}")
    fuzzy_sets = fuzzy_sets_response.json()
    
    if fuzzy_sets["success"]:
        print(f"Fuzzy sets for {indicator_id}: {list(fuzzy_sets['data'].keys())}")
        
        # 3. Calculate RSI indicator values
        rsi_request = {
            "symbol": "AAPL",
            "timeframe": "1d",
            "indicators": [
                {
                    "id": "RSIIndicator",
                    "parameters": {"period": 14, "source": "close"},
                }
            ],
            "start_date": "2023-01-01T00:00:00",
            "end_date": "2023-01-31T23:59:59"
        }
        
        rsi_response = requests.post(
            "http://localhost:8000/api/v1/indicators/calculate",
            json=rsi_request
        ).json()
        
        if rsi_response["success"]:
            # 4. Apply fuzzy sets to the RSI values
            rsi_values = rsi_response["indicators"]["RSIIndicator"]
            
            fuzzy_request = {
                "indicator": indicator_id,
                "values": rsi_values,
                "dates": rsi_response["dates"]
            }
            
            fuzzy_response = requests.post(
                "http://localhost:8000/api/v1/fuzzy/evaluate",
                json=fuzzy_request
            ).json()
            
            if fuzzy_response["success"]:
                # Process fuzzy membership values
                print("RSI fuzzy membership degrees:")
                for set_name, values in fuzzy_response["data"]["values"].items():
                    print(f"  {set_name}: {values[:5]}...")  # Show first 5 values
```

### Pattern 2: One-Step Fuzzy Calculation

For convenience, calculate and fuzzify in a single request:

```python
import requests
import json

# Calculate and fuzzify in one step
fuzzy_data_request = {
    "symbol": "AAPL",
    "timeframe": "1d",
    "indicators": [
        {
            "name": "rsi",
            "source_column": "close"
        }
    ],
    "start_date": "2023-01-01T00:00:00",
    "end_date": "2023-01-31T23:59:59"
}

fuzzy_data_response = requests.post(
    "http://localhost:8000/api/v1/fuzzy/data",
    json=fuzzy_data_request
).json()

if fuzzy_data_response["success"]:
    # Process the combined data and fuzzy results
    dates = fuzzy_data_response["data"]["dates"]
    rsi_fuzzy = fuzzy_data_response["data"]["indicators"]["rsi"]
    
    # Extract membership degrees
    low_values = rsi_fuzzy["rsi_low"]
    medium_values = rsi_fuzzy["rsi_medium"]
    high_values = rsi_fuzzy["rsi_high"]
    
    # Do something with the membership degrees
    for i in range(min(5, len(dates))):  # Show first 5 points
        print(f"{dates[i]}: Low={low_values[i]:.2f}, Medium={medium_values[i]:.2f}, High={high_values[i]:.2f}")
```

## Error Handling

### Pattern 1: Graceful Error Handling

Always check the success flag and handle errors appropriately:

```python
import requests
import json

def handle_api_response(response):
    try:
        data = response.json()
        
        if data.get("success") is True:
            return {"success": True, "data": data.get("data", {})}
        else:
            error = data.get("error", {})
            error_code = error.get("code", "UNKNOWN_ERROR")
            error_message = error.get("message", "Unknown error occurred")
            error_details = error.get("details", {})
            
            print(f"API Error: {error_code} - {error_message}")
            if error_details:
                print(f"Details: {error_details}")
                
            return {"success": False, "error": error}
    except ValueError:
        print(f"Invalid JSON response: {response.text}")
        return {"success": False, "error": {"code": "INVALID_RESPONSE", "message": "Invalid JSON response"}}
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        return {"success": False, "error": {"code": "PROCESSING_ERROR", "message": str(e)}}

# Example usage
response = requests.post("http://localhost:8000/api/v1/data/load", json={"symbol": "UNKNOWN"})
result = handle_api_response(response)

if result["success"]:
    # Process the data
    print("Successfully retrieved data")
else:
    # Handle different error types
    error_code = result["error"].get("code", "")
    
    if error_code == "DATA-NotFound":
        print("The requested data was not found. Please check the symbol and timeframe.")
    elif error_code == "VALIDATION_ERROR":
        print("The request parameters are invalid. Please check your input.")
    else:
        print("An error occurred. Please try again later.")
```

### Pattern 2: Retry with Backoff

For transient errors, implement a retry mechanism with exponential backoff:

```python
import requests
import json
import time
import random

def api_request_with_retry(url, method="GET", json_data=None, max_retries=3, base_delay=1, max_delay=60):
    retries = 0
    last_error = None
    
    while retries < max_retries:
        try:
            if method.upper() == "GET":
                response = requests.get(url)
            elif method.upper() == "POST":
                response = requests.post(url, json=json_data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            result = response.json()
            
            # If successful, return immediately
            if result.get("success") is True:
                return result
            
            # Check for non-transient errors
            error_code = result.get("error", {}).get("code", "")
            if error_code in ["VALIDATION_ERROR", "DATA-NotFound", "CONFIG-UnknownIndicator"]:
                # These are not transient, so don't retry
                return result
            
            last_error = result
            
        except (requests.RequestException, ValueError) as e:
            last_error = {"success": False, "error": {"code": "REQUEST_ERROR", "message": str(e)}}
            
        # Calculate backoff delay with jitter
        delay = min(base_delay * (2 ** retries) + random.uniform(0, 1), max_delay)
        print(f"Retry {retries+1}/{max_retries} after {delay:.2f}s...")
        time.sleep(delay)
        retries += 1
    
    # If we get here, all retries failed
    return last_error or {"success": False, "error": {"code": "MAX_RETRIES", "message": "Maximum retries reached"}}
```

## Performance Optimization

### Pattern 1: Parallel Data Processing

For processing multiple symbols, use parallel requests:

```python
import requests
import json
import concurrent.futures
from datetime import datetime, timedelta

def get_indicator_for_symbol(symbol, indicator_id, timeframe="1d", days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    request = {
        "symbol": symbol,
        "timeframe": timeframe,
        "indicators": [
            {
                "id": indicator_id,
                "parameters": {"period": 14, "source": "close"},
            }
        ],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
    
    response = requests.post(
        "http://localhost:8000/api/v1/indicators/calculate",
        json=request
    ).json()
    
    if response["success"]:
        return {
            "symbol": symbol,
            "data": {
                "dates": response["dates"],
                "values": response["indicators"][indicator_id]
            }
        }
    else:
        print(f"Error for {symbol}: {response['error']['message']}")
        return {"symbol": symbol, "error": response["error"]}

# Process multiple symbols in parallel
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
indicator = "RSIIndicator"

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    # Submit all tasks
    future_to_symbol = {
        executor.submit(get_indicator_for_symbol, symbol, indicator): symbol
        for symbol in symbols
    }
    
    # Process results as they complete
    results = {}
    for future in concurrent.futures.as_completed(future_to_symbol):
        symbol = future_to_symbol[future]
        try:
            result = future.result()
            results[symbol] = result
            print(f"Completed {symbol}")
        except Exception as e:
            print(f"Error processing {symbol}: {str(e)}")
            results[symbol] = {"symbol": symbol, "error": str(e)}
```

### Pattern 2: Caching Common Data

Cache frequently used data to reduce API calls:

```python
import requests
import json
import time
from functools import lru_cache

# Cache indicator metadata for 1 hour
@lru_cache(maxsize=1)
def get_indicators_with_ttl():
    # Store timestamp with the data for TTL
    timestamp = time.time()
    response = requests.get("http://localhost:8000/api/v1/indicators").json()
    return (timestamp, response)

def get_indicators(max_age_seconds=3600):
    # Get cached data with timestamp
    timestamp, indicators = get_indicators_with_ttl()
    
    # Check if cache is stale
    if time.time() - timestamp > max_age_seconds:
        # Clear the cache to force refresh on next call
        get_indicators_with_ttl.cache_clear()
        # Get fresh data
        timestamp, indicators = get_indicators_with_ttl()
    
    return indicators

# Using the cached function
indicators = get_indicators()
print(f"Found {len(indicators['data'])} indicators")

# This will use the cached copy
indicators_again = get_indicators()
print("Retrieved from cache")
```

These patterns should help you efficiently integrate the KTRDR API into your applications.