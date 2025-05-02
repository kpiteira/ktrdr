# KTRDR API Troubleshooting Guide

This document provides solutions for common issues encountered when using the KTRDR API.

## 1. Connection Issues

### Issue: Cannot Connect to API Server

**Symptoms**:
- Connection refused error
- Timeout error
- Network unreachable error

**Possible Causes**:
1. API server is not running
2. Incorrect hostname or port
3. Network connectivity issues
4. Firewall blocking connection

**Solutions**:
1. Verify the API server is running:
   ```bash
   # Check if the server process is running
   ps aux | grep uvicorn
   
   # Restart the API server if needed
   ./scripts/run_api_server.py
   ```

2. Check your API URL:
   - Default development URL is `http://localhost:8000/api/v1`
   - Verify hostname and port are correct

3. Test basic connectivity:
   ```bash
   # Test with curl
   curl -v http://localhost:8000/api/v1/health
   
   # Or with wget
   wget -O- http://localhost:8000/api/v1/health
   ```

4. Check firewall settings:
   ```bash
   # Check if port is open
   sudo lsof -i:8000
   
   # For macOS
   sudo pfctl -s rules | grep 8000
   ```

### Issue: SSL Certificate Errors

**Symptoms**:
- SSL certificate verification error
- Insecure connection warning

**Solutions**:
1. Ensure you're using HTTPS correctly for production servers
2. For development with self-signed certificates:
   ```python
   # Python - disable verification only for testing
   import requests
   response = requests.get("https://localhost:8000/api/v1/health", verify=False)
   
   # JavaScript - disable verification only for testing
   // Not recommended for production
   process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
   ```

3. For production, ensure your SSL certificates are valid:
   ```bash
   # Check certificate validity
   openssl s_client -connect api.example.com:443 -servername api.example.com
   ```

## 2. Authentication Issues

### Issue: Authentication Failed

**Symptoms**:
- 401 Unauthorized response
- "Invalid API key" error message

**Solutions**:
1. Verify your API key:
   ```python
   # Python example
   headers = {
       "Content-Type": "application/json",
       "X-API-Key": "your-api-key"  # Check if this is correct
   }
   ```

2. Check if the API key has expired or been revoked (contact administrator)

3. Ensure API key is being sent correctly:
   ```bash
   # Test with curl
   curl -v -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/symbols
   ```

## 3. Request Format Issues

### Issue: Validation Error (422 Status Code)

**Symptoms**:
- 422 Unprocessable Entity response
- Detailed validation error message

**Example Error**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "symbol": "Symbol is required",
      "timeframe": "Timeframe must be one of ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M']"
    }
  }
}
```

**Solutions**:
1. Check request payload structure:
   ```python
   # Correct payload structure
   payload = {
       "symbol": "AAPL",       # Required
       "timeframe": "1d",      # Required, must be valid timeframe
       "start_date": "2023-01-01T00:00:00",  # Optional, ISO format
       "end_date": "2023-01-31T23:59:59"     # Optional, ISO format
   }
   ```

2. Verify date formats (use ISO 8601):
   ```python
   # Python example
   from datetime import datetime
   
   # Generate ISO format date
   iso_date = datetime.now().isoformat()
   # Or specific date
   from datetime import datetime
   iso_date = datetime(2023, 1, 1).isoformat()
   ```

3. Check valid timeframes:
   - Valid timeframes: `'1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M'`

## 4. Data Related Issues

### Issue: Data Not Found

**Symptoms**:
- 404 Not Found response
- DATA-NotFound error code

**Example Error**:
```json
{
  "success": false,
  "error": {
    "code": "DATA-NotFound",
    "message": "No data available for UNKNOWN (1d)",
    "details": {
      "symbol": "UNKNOWN",
      "timeframe": "1d"
    }
  }
}
```

**Solutions**:
1. Check if symbol exists:
   ```python
   # First, get list of available symbols
   symbols = client.get_symbols()
   print(f"Available symbols: {symbols}")
   
   # Then use a valid symbol from the list
   ```

2. Check data availability range:
   ```python
   # Get available date range for a symbol
   range_info = client.get_data_range("AAPL", "1d")
   print(f"Available data range: {range_info['start_date']} to {range_info['end_date']}")
   
   # Ensure your date range is within available data
   ```

3. Check for case sensitivity:
   - Symbols are typically case-sensitive (e.g., "AAPL" not "aapl")

### Issue: Invalid Indicator Parameters

**Symptoms**:
- 400 Bad Request response
- CONFIG-UnknownIndicator or CONFIG-InvalidParameter error code

**Example Error**:
```json
{
  "success": false,
  "error": {
    "code": "CONFIG-InvalidParameter",
    "message": "Invalid parameters for RSIIndicator",
    "details": {
      "period": "Period must be between 2 and 100"
    }
  }
}
```

**Solutions**:
1. Get list of available indicators with valid parameters:
   ```python
   # Get indicator metadata
   indicators = client.get_indicators()
   
   # Find specific indicator parameters
   for indicator in indicators:
       if indicator["id"] == "RSIIndicator":
           print(f"Valid parameters for RSI: {indicator['parameters']}")
   ```

2. Ensure parameter types are correct:
   ```python
   # Correct parameter types
   indicators = [
       {
           "id": "RSIIndicator",
           "parameters": {
               "period": 14,     # Integer, not string
               "source": "close"  # String
           }
       }
   ]
   ```

## 5. Performance Issues

### Issue: Slow Response Times

**Symptoms**:
- API requests take a long time to complete
- Timeout errors

**Solutions**:
1. Use pagination for large datasets:
   ```python
   # Use pagination parameters
   data = client.load_data(
       symbol="AAPL",
       timeframe="1d",
       start_date="2020-01-01",
       end_date="2022-12-31",
       page=1,
       page_size=1000
   )
   ```

2. Reduce date range for requests:
   ```python
   # Split large date ranges into smaller chunks
   chunks = []
   start = "2020-01-01"
   end = "2020-03-31"
   
   while start < "2022-12-31":
       data = client.load_data("AAPL", "1d", start, end)
       chunks.append(data)
       
       # Move to next quarter
       start = end
       end = next_quarter_end(end)
   ```

3. Use binary format for large data transfers:
   ```python
   # Request binary format for efficiency
   response = requests.post(
       f"{api_base_url}/data/load/binary",
       headers={"Accept": "application/x-msgpack"},
       json=payload
   )
   
   # Parse MessagePack response
   import msgpack
   data = msgpack.unpackb(response.content)
   ```

4. Enable gzip compression:
   ```python
   # Request with compression
   headers = {
       "Content-Type": "application/json",
       "Accept-Encoding": "gzip, deflate"
   }
   ```

## 6. Fuzzy Logic Issues

### Issue: Fuzzy Engine Not Initialized

**Symptoms**:
- 400 Bad Request response
- CONFIG-FuzzyEngineNotInitialized error code

**Example Error**:
```json
{
  "success": false,
  "error": {
    "code": "CONFIG-FuzzyEngineNotInitialized",
    "message": "Fuzzy engine not initialized",
    "details": {}
  }
}
```

**Solutions**:
1. Check available fuzzy indicators:
   ```python
   # Get available fuzzy indicators
   fuzzy_indicators = client.get_fuzzy_indicators()
   print(f"Available fuzzy indicators: {fuzzy_indicators}")
   ```

2. Ensure fuzzy sets are configured:
   ```python
   # Check fuzzy sets for a specific indicator
   fuzzy_sets = client.get_fuzzy_sets("rsi")
   print(f"RSI fuzzy sets: {fuzzy_sets}")
   ```

### Issue: Unknown Fuzzy Indicator

**Symptoms**:
- 400 Bad Request response
- CONFIG-UnknownFuzzyIndicator error code

**Solutions**:
1. Use only configured fuzzy indicators:
   ```python
   # Get list of available fuzzy indicators first
   fuzzy_indicators = client.get_fuzzy_indicators()
   indicator_ids = [ind["id"] for ind in fuzzy_indicators]
   
   # Then use only available indicators
   if "rsi" in indicator_ids:
       # Use RSI indicator
       pass
   ```

## 7. Request/Response Format Issues

### Issue: Invalid JSON Format

**Symptoms**:
- 400 Bad Request response
- "Invalid JSON" error message

**Solutions**:
1. Validate JSON format:
   ```python
   # Python example
   import json
   
   # Validate JSON before sending
   try:
       json.dumps(payload)  # This will fail if payload is not JSON serializable
   except Exception as e:
       print(f"Invalid JSON: {e}")
   
   # Send valid JSON
   response = requests.post(url, json=payload)  # Use json parameter, not data
   ```

2. Check for JSON formatting issues:
   - Missing quotes around keys
   - Trailing commas
   - Invalid values (NaN, Infinity)

### Issue: Content-Type Issues

**Symptoms**:
- 415 Unsupported Media Type response
- "Unsupported Media Type" error message

**Solutions**:
1. Set correct Content-Type header:
   ```python
   # Set Content-Type header
   headers = {
       "Content-Type": "application/json"
   }
   ```

2. Use correct request method:
   ```python
   # For GET requests with query parameters
   response = requests.get(url, params=query_params)
   
   # For POST requests with JSON body
   response = requests.post(url, json=payload)
   ```

## 8. General Troubleshooting Steps

### Step 1: Check API Status

```bash
# Get health check
curl http://localhost:8000/api/v1/health
```

### Step 2: Enable Verbose Logging

```python
# Python requests with verbose logging
import requests
import logging

# Enable logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)

# Now make requests
response = requests.get(url)
```

### Step 3: Examine Response Headers

```python
# Print response headers
response = requests.get(url)
print("Response Headers:")
for header, value in response.headers.items():
    print(f"{header}: {value}")
```

### Step 4: Check Request ID for Support

Every API response includes a request ID in the `X-Request-ID` header. 
Provide this ID when requesting support:

```python
# Get request ID for support
response = requests.get(url)
request_id = response.headers.get("X-Request-ID")
print(f"Request ID for support: {request_id}")
```

## 9. Common Error Codes Reference

| Error Code | HTTP Status | Description | Solution |
|------------|-------------|-------------|----------|
| VALIDATION_ERROR | 422 | Invalid request parameters | Check request payload against API documentation |
| DATA-NotFound | 404 | Requested data not found | Verify symbol, timeframe, and date range |
| DATA-LoadError | 400 | Error loading data | Check data source and parameters |
| CONFIG-UnknownIndicator | 400 | Unknown indicator ID | Use only available indicators |
| CONFIG-InvalidParameter | 400 | Invalid indicator parameter | Check parameter types and ranges |
| PROC-CalculationFailed | 500 | Error during calculation | Check for valid input data |
| CONFIG-FuzzyEngineNotInitialized | 400 | Fuzzy engine not initialized | Ensure fuzzy engine is properly configured |
| CONFIG-UnknownFuzzyIndicator | 400 | Unknown fuzzy indicator | Use only available fuzzy indicators |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error | Contact support with request ID |

## 10. Getting Help

If you encounter issues that aren't covered in this guide:

1. Check the API logs for detailed error information:
   ```bash
   # View API logs
   cat logs/ktrdr.log
   ```

2. Contact support with:
   - Request ID (from X-Request-ID header)
   - Exact error message and code
   - Request payload
   - Steps to reproduce the issue

3. Join the community forum at [community.ktrdr.com](https://community.ktrdr.com) for help from other developers