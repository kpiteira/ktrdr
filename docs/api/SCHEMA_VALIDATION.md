# Schema Validation Examples

This document provides examples of schema validation for the KTRDR API, helping you understand the validation rules and error responses.

## Data Models Validation

### Symbol Validation

Symbol must be a non-empty string:

```json
// Valid
{
  "symbol": "AAPL",
  "timeframe": "1d"
}

// Invalid - Empty string
{
  "symbol": "",
  "timeframe": "1d"
}

// Invalid - Missing required field
{
  "timeframe": "1d"
}
```

### Timeframe Validation

Timeframe must be one of the supported values:

```json
// Valid
{
  "symbol": "AAPL",
  "timeframe": "1d"
}

// Invalid - Unsupported timeframe
{
  "symbol": "AAPL",
  "timeframe": "2d"
}

// Error Response
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "timeframe": "timeframe must be one of ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M']"
    }
  }
}
```

### Date Range Validation

Start and end dates must be valid ISO format datetime strings:

```json
// Valid
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00",
  "end_date": "2023-01-31T23:59:59"
}

// Invalid - Incorrect date format
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "01/01/2023",
  "end_date": "2023-01-31T23:59:59"
}

// Error Response
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "start_date": "start_date must be a valid ISO format datetime string"
    }
  }
}
```

## Indicator Models Validation

### Indicator ID Validation

Indicator ID must refer to a valid, registered indicator:

```json
// Valid
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 14,
        "source": "close"
      }
    }
  ]
}

// Invalid - Unknown indicator
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "id": "UnknownIndicator",
      "parameters": {
        "period": 14,
        "source": "close"
      }
    }
  ]
}

// Error Response
{
  "success": false,
  "error": {
    "code": "CONFIG-UnknownIndicator",
    "message": "Unknown indicator: UnknownIndicator",
    "details": {
      "indicator_id": "UnknownIndicator"
    }
  }
}
```

### Parameter Validation

Parameters must be valid types and within allowed ranges:

```json
// Valid
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 14,
        "source": "close"
      }
    }
  ]
}

// Invalid - Period out of range
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 0,  // Must be >= 2
        "source": "close"
      }
    }
  ]
}

// Invalid - Invalid source
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 14,
        "source": "invalid_source"  // Must be one of ["close", "open", "high", "low"]
      }
    }
  ]
}

// Error Response
{
  "success": false,
  "error": {
    "code": "CONFIG-InvalidParameter",
    "message": "Invalid parameter: source must be one of ['close', 'open', 'high', 'low']",
    "details": {
      "parameter": "source",
      "valid_values": ["close", "open", "high", "low"],
      "provided_value": "invalid_source"
    }
  }
}
```

## Fuzzy Models Validation

### Fuzzy Indicator Validation

Indicator must refer to a valid fuzzy indicator with configured fuzzy sets:

```json
// Valid
{
  "indicator": "rsi",
  "values": [30.5, 45.2, 68.7]
}

// Invalid - Unknown fuzzy indicator
{
  "indicator": "unknown_indicator",
  "values": [30.5, 45.2, 68.7]
}

// Error Response
{
  "success": false,
  "error": {
    "code": "CONFIG-UnknownFuzzyIndicator",
    "message": "Unknown fuzzy indicator: unknown_indicator",
    "details": {
      "indicator": "unknown_indicator"
    }
  }
}
```

### Values Validation

Values must be a non-empty array of numeric values:

```json
// Valid
{
  "indicator": "rsi",
  "values": [30.5, 45.2, 68.7]
}

// Invalid - Empty array
{
  "indicator": "rsi",
  "values": []
}

// Invalid - Non-numeric values
{
  "indicator": "rsi",
  "values": [30.5, "not-a-number", 68.7]
}

// Error Response
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "values": "values must be a non-empty array of numeric values"
    }
  }
}
```

## Common Validation Errors

### Missing Required Fields

```json
// Error Response
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Missing required field: symbol",
    "details": {}
  }
}
```

### Invalid JSON

```json
// Error Response
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid JSON in request body",
    "details": {
      "error": "Expecting property name enclosed in double quotes"
    }
  }
}
```

### Unsupported Content Type

```json
// Error Response when not using application/json
{
  "success": false,
  "error": {
    "code": "INVALID_CONTENT_TYPE",
    "message": "Content-Type must be application/json",
    "details": {}
  }
}
```

## Tips for Avoiding Validation Errors

1. **Check API Documentation**: Always refer to the API documentation for current parameter requirements
2. **Use Enumerated Values**: For parameters with a limited set of valid values (like timeframes), use the values provided in the documentation
3. **Verify Ranges**: Ensure numeric parameters fall within the allowed ranges
4. **Discover Before Use**: Use the metadata endpoints (like `/api/v1/indicators`) to discover valid values
5. **Handle Error Responses**: Always check the `success` flag in responses and handle errors appropriately
6. **Validate Client-Side**: When possible, validate inputs on the client side before sending them to the API