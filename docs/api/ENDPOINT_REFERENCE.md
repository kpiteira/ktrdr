# KTRDR API Endpoint Reference

This document provides a comprehensive reference for all endpoints available in the KTRDR API.

## 1. API Overview

- **Base URL**: `http://localhost:8000/api/v1` (development)
- **Authentication**: API key via `X-API-Key` header (optional in development mode)
- **Response Format**: JSON with standard envelope structure
- **Content-Type**: `application/json` for requests and responses

### 1.1 Standard Response Envelope

All API responses follow a standard envelope format:

```json
{
  "success": true,  // Boolean indicating success or failure
  "data": {},       // Response data (when success is true)
  "error": {        // Error information (when success is false)
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}   // Additional error context
  }
}
```

### 1.2 API Versioning

The API uses URL-based versioning with the format `/api/v{version_number}/`:

- Current stable version: `/api/v1/`
- Development version: `/api/dev/`

## 2. Data Endpoints

### 2.1 Get Available Symbols

Returns a list of available trading symbols.

- **URL**: `/api/v1/symbols`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "exchange": "NASDAQ",
      "type": "stock",
      "currency": "USD"
    },
    {
      "symbol": "MSFT",
      "name": "Microsoft Corporation",
      "exchange": "NASDAQ",
      "type": "stock",
      "currency": "USD"
    }
  ]
}
```

### 2.2 Get Available Timeframes

Returns a list of supported timeframes.

- **URL**: `/api/v1/timeframes`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": [
    {
      "id": "1m",
      "name": "1 Minute",
      "seconds": 60,
      "description": "One-minute interval data"
    },
    {
      "id": "1h",
      "name": "1 Hour",
      "seconds": 3600,
      "description": "One-hour interval data"
    },
    {
      "id": "1d",
      "name": "1 Day",
      "seconds": 86400,
      "description": "Daily data"
    }
  ]
}
```

### 2.3 Load Market Data

Loads OHLCV data for a specific symbol and timeframe.

- **URL**: `/api/v1/data/load`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| symbol      | string | Yes      | Trading symbol (e.g., "AAPL")            |
| timeframe   | string | Yes      | Timeframe identifier (e.g., "1d")        |
| start_date  | string | No       | Start date (ISO 8601 format)             |
| end_date    | string | No       | End date (ISO 8601 format)               |
| page        | number | No       | Page number for pagination (default: 1)  |
| page_size   | number | No       | Items per page (default: 1000, max: 5000)|

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-31T23:59:59Z"
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "dates": [
      "2023-01-03T00:00:00Z",
      "2023-01-04T00:00:00Z",
      "2023-01-05T00:00:00Z"
    ],
    "ohlcv": [
      [125.07, 128.49, 124.17, 125.07, 75132846],
      [126.89, 128.66, 125.08, 127.26, 86456786],
      [127.13, 128.29, 125.85, 127.15, 71081874]
    ],
    "metadata": {
      "symbol": "AAPL",
      "timeframe": "1d",
      "start_date": "2023-01-03T00:00:00Z",
      "end_date": "2023-01-31T23:59:59Z",
      "point_count": 20,
      "source": "csv",
      "total_items": 20,
      "total_pages": 1,
      "current_page": 1,
      "page_size": 1000,
      "has_next": false,
      "has_prev": false
    }
  }
}
```

### 2.4 Get Data Range Information

Returns information about the available data range for a symbol and timeframe.

- **URL**: `/api/v1/data/range`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| symbol      | string | Yes      | Trading symbol (e.g., "AAPL")            |
| timeframe   | string | Yes      | Timeframe identifier (e.g., "1d")        |

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d"
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "start_date": "2000-01-03T00:00:00Z",
    "end_date": "2023-04-28T00:00:00Z",
    "point_count": 5839
  }
}
```

### 2.5 Binary Data Format (MessagePack)

Loads OHLCV data in binary MessagePack format for more efficient data transfer.

- **URL**: `/api/v1/data/load/binary`
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Accept**: `application/x-msgpack`

**Request Parameters**: Same as `/api/v1/data/load`

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-31T23:59:59Z"
}
```

**Response**: Binary MessagePack data with the same structure as the JSON response from `/api/v1/data/load`

## 3. Indicator Endpoints

### 3.1 Get Available Indicators

Returns a list of available technical indicators.

- **URL**: `/api/v1/indicators`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": [
    {
      "id": "SimpleMovingAverage",
      "name": "Simple Moving Average",
      "description": "Simple Moving Average (SMA) calculation",
      "type": "overlay",
      "parameters": [
        {
          "name": "period",
          "type": "integer",
          "description": "Number of periods to average",
          "default": 20,
          "min_value": 2,
          "max_value": 500
        },
        {
          "name": "source",
          "type": "string",
          "description": "Price data to use",
          "default": "close",
          "options": ["open", "high", "low", "close", "volume"]
        }
      ]
    },
    {
      "id": "RSIIndicator",
      "name": "Relative Strength Index",
      "description": "Relative Strength Index (RSI) calculation",
      "type": "oscillator",
      "parameters": [
        {
          "name": "period",
          "type": "integer",
          "description": "RSI period",
          "default": 14,
          "min_value": 2,
          "max_value": 100
        },
        {
          "name": "source",
          "type": "string",
          "description": "Price data to use",
          "default": "close",
          "options": ["open", "high", "low", "close"]
        }
      ]
    }
  ]
}
```

### 3.2 Calculate Indicators

Calculates one or more technical indicators for a specific symbol and timeframe.

- **URL**: `/api/v1/indicators/calculate`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type     | Required | Description                              |
|-------------|----------|----------|------------------------------------------|
| symbol      | string   | Yes      | Trading symbol (e.g., "AAPL")            |
| timeframe   | string   | Yes      | Timeframe identifier (e.g., "1d")        |
| indicators  | array    | Yes      | Array of indicator configurations        |
| start_date  | string   | No       | Start date (ISO 8601 format)             |
| end_date    | string   | No       | End date (ISO 8601 format)               |
| page        | number   | No       | Page number for pagination (default: 1)  |
| page_size   | number   | No       | Items per page (default: 1000, max: 5000)|

**Indicator Configuration**:

| Parameter    | Type    | Required | Description                              |
|--------------|---------|----------|------------------------------------------|
| id           | string  | Yes      | Indicator ID (e.g., "RSIIndicator")      |
| parameters   | object  | Yes      | Parameter values for the indicator       |
| output_name  | string  | No       | Custom name for the indicator output     |
| precision    | number  | No       | Decimal precision for results            |

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-31T23:59:59Z",
  "indicators": [
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 14,
        "source": "close"
      },
      "output_name": "rsi_14"
    },
    {
      "id": "SimpleMovingAverage",
      "parameters": {
        "period": 20,
        "source": "close"
      },
      "output_name": "sma_20"
    }
  ]
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "dates": [
      "2023-01-03T00:00:00Z",
      "2023-01-04T00:00:00Z",
      "2023-01-05T00:00:00Z"
    ],
    "indicators": {
      "rsi_14": [58.21, 62.47, 61.89],
      "sma_20": [null, null, 126.83]
    },
    "metadata": {
      "symbol": "AAPL",
      "timeframe": "1d",
      "start_date": "2023-01-03T00:00:00Z",
      "end_date": "2023-01-31T23:59:59Z",
      "points": 20,
      "total_items": 20,
      "total_pages": 1,
      "current_page": 1,
      "page_size": 1000,
      "has_next": false,
      "has_prev": false
    }
  }
}
```

## 4. Fuzzy Logic Endpoints

### 4.1 Get Available Fuzzy Indicators

Returns a list of indicators that can be used with fuzzy logic.

- **URL**: `/api/v1/fuzzy/indicators`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": [
    {
      "id": "rsi",
      "name": "Relative Strength Index",
      "fuzzy_sets": ["low", "medium", "high"],
      "output_columns": ["low", "medium", "high"]
    },
    {
      "id": "macd",
      "name": "MACD",
      "fuzzy_sets": ["bullish", "neutral", "bearish"],
      "output_columns": ["bullish", "neutral", "bearish"]
    }
  ]
}
```

### 4.2 Get Fuzzy Sets

Returns the fuzzy membership function configuration for a specific indicator.

- **URL**: `/api/v1/fuzzy/sets/{indicator}`
- **Method**: `GET`
- **URL Parameters**:
  - `indicator`: Indicator ID (e.g., "rsi")

**Response Example**:
```json
{
  "success": true,
  "data": {
    "low": {
      "type": "trapezoid",
      "parameters": [0, 0, 30, 50]
    },
    "medium": {
      "type": "triangle",
      "parameters": [30, 50, 70]
    },
    "high": {
      "type": "trapezoid",
      "parameters": [50, 70, 100, 100]
    }
  }
}
```

### 4.3 Evaluate Fuzzy Membership

Applies fuzzy membership functions to a set of indicator values.

- **URL**: `/api/v1/fuzzy/evaluate`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type     | Required | Description                              |
|-------------|----------|----------|------------------------------------------|
| indicator   | string   | Yes      | Fuzzy indicator ID (e.g., "rsi")         |
| values      | array    | Yes      | Array of indicator values                |
| dates       | array    | No       | Array of corresponding dates             |

**Request Example**:
```json
{
  "indicator": "rsi",
  "values": [35, 45, 55, 65, 75],
  "dates": [
    "2023-01-01T00:00:00Z",
    "2023-01-02T00:00:00Z",
    "2023-01-03T00:00:00Z",
    "2023-01-04T00:00:00Z",
    "2023-01-05T00:00:00Z"
  ]
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "indicator": "rsi",
    "fuzzy_sets": ["low", "medium", "high"],
    "values": {
      "low": [0.75, 0.25, 0, 0, 0],
      "medium": [0.25, 0.75, 1.0, 0.75, 0.25],
      "high": [0, 0, 0, 0.25, 0.75]
    },
    "points": 5
  }
}
```

### 4.4 Fuzzify Symbol Data

Loads data, calculates indicators, and applies fuzzy membership functions in a single operation.

- **URL**: `/api/v1/fuzzy/data`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type     | Required | Description                              |
|-------------|----------|----------|------------------------------------------|
| symbol      | string   | Yes      | Trading symbol (e.g., "AAPL")            |
| timeframe   | string   | Yes      | Timeframe identifier (e.g., "1d")        |
| indicators  | array    | Yes      | Array of fuzzy indicator configurations  |
| start_date  | string   | No       | Start date (ISO 8601 format)             |
| end_date    | string   | No       | End date (ISO 8601 format)               |

**Fuzzy Indicator Configuration**:

| Parameter      | Type    | Required | Description                              |
|----------------|---------|----------|------------------------------------------|
| name           | string  | Yes      | Fuzzy indicator name (e.g., "rsi")       |
| source_column  | string  | Yes      | Source data column (e.g., "close")       |
| parameters     | object  | No       | Parameter values for the indicator       |
| fuzzy_sets     | object  | No       | Custom fuzzy set configurations          |

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-10T23:59:59Z",
  "indicators": [
    {
      "name": "rsi",
      "source_column": "close",
      "parameters": {
        "period": 14
      }
    },
    {
      "name": "macd",
      "source_column": "close"
    }
  ]
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "dates": [
      "2023-01-03T00:00:00Z",
      "2023-01-04T00:00:00Z",
      "2023-01-05T00:00:00Z"
    ],
    "indicators": {
      "rsi": {
        "low": [0, 0, 0],
        "medium": [0.5, 0.1, 0.2],
        "high": [0.5, 0.9, 0.8]
      },
      "macd": {
        "bullish": [0.8, 0.7, 0.6],
        "neutral": [0.2, 0.3, 0.4],
        "bearish": [0, 0, 0]
      }
    },
    "metadata": {
      "start_date": "2023-01-03T00:00:00Z",
      "end_date": "2023-01-10T23:59:59Z",
      "points": 6
    }
  }
}
```

## 5. Chart Endpoints

### 5.1 Generate Chart

Generates a chart configuration for rendering with lightweight-charts.

- **URL**: `/api/v1/charts/render`
- **Method**: `POST`
- **Content-Type**: `application/json`

**Request Parameters**:

| Parameter   | Type     | Required | Description                              |
|-------------|----------|----------|------------------------------------------|
| symbol      | string   | Yes      | Trading symbol (e.g., "AAPL")            |
| timeframe   | string   | Yes      | Timeframe identifier (e.g., "1d")        |
| indicators  | array    | No       | Array of indicator configurations        |
| options     | object   | No       | Chart configuration options              |
| start_date  | string   | No       | Start date (ISO 8601 format)             |
| end_date    | string   | No       | End date (ISO 8601 format)               |

**Options Object**:

| Parameter     | Type     | Default | Description                              |
|---------------|----------|---------|------------------------------------------|
| theme         | string   | "dark"  | Chart theme ("dark" or "light")          |
| height        | number   | 500     | Chart height in pixels                   |
| width         | number   | null    | Chart width in pixels (null = responsive)|
| show_volume   | boolean  | true    | Whether to show volume histogram         |
| show_grid     | boolean  | true    | Whether to show grid lines               |
| crosshair     | string   | "normal"| Crosshair type ("normal" or "magnet")    |
| time_visible  | boolean  | true    | Whether to show time on the x-axis       |
| multi_panel   | boolean  | true    | Whether to use separate panels for oscillators|

**Request Example**:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-31T23:59:59Z",
  "indicators": [
    {
      "id": "SimpleMovingAverage",
      "parameters": {
        "period": 20,
        "source": "close"
      },
      "output_name": "SMA 20",
      "color": "#2962FF"
    },
    {
      "id": "RSIIndicator",
      "parameters": {
        "period": 14,
        "source": "close"
      },
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
}
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "chart_data": {
      "ohlcv": [...],  // OHLCV data in lightweight-charts format
      "indicators": {
        "SMA 20": [...],  // SMA values
        "RSI 14": [...]   // RSI values
      }
    },
    "config": {
      "theme": "dark",
      "height": 600,
      "show_volume": true,
      "multi_panel": true,
      "panels": [
        {
          "id": "main",
          "title": "AAPL - 1d",
          "height_ratio": 0.7,
          "series": [
            {"type": "candlestick", "name": "AAPL"},
            {"type": "line", "name": "SMA 20", "color": "#2962FF"}
          ]
        },
        {
          "id": "volume",
          "title": "Volume",
          "height_ratio": 0.15,
          "series": [
            {"type": "histogram", "name": "Volume"}
          ]
        },
        {
          "id": "rsi",
          "title": "RSI 14",
          "height_ratio": 0.15,
          "series": [
            {"type": "line", "name": "RSI 14", "color": "#FF6D00"}
          ],
          "overlays": [
            {"type": "line", "value": 70, "color": "#FF0000"},
            {"type": "line", "value": 30, "color": "#00FF00"}
          ]
        }
      ]
    }
  }
}
```

### 5.2 Get Chart HTML Template

Returns an HTML template that can be used to render charts.

- **URL**: `/api/v1/charts/template`
- **Method**: `GET`
- **Query Parameters**:
  - `theme` (optional): "dark" or "light" (default: "dark")

**Response Example**:
```json
{
  "success": true,
  "data": {
    "html": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>...",
    "version": "1.0.0"
  }
}
```

## 6. System Endpoints

### 6.1 Health Check

Returns information about the API status.

- **URL**: `/api/v1/health`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "1.0.5",
    "timestamp": "2023-05-01T12:34:56.789Z",
    "uptime": 3600
  }
}
```

### 6.2 API Information

Returns information about the API including version and available endpoints.

- **URL**: `/api/v1/info`
- **Method**: `GET`
- **Parameters**: None

**Response Example**:
```json
{
  "success": true,
  "data": {
    "name": "KTRDR API",
    "version": "1.0.5",
    "description": "Financial data and analysis API",
    "endpoints": [
      {"path": "/api/v1/symbols", "methods": ["GET"]},
      {"path": "/api/v1/timeframes", "methods": ["GET"]},
      {"path": "/api/v1/data/load", "methods": ["POST"]}
    ],
    "modules": [
      {"name": "data", "version": "1.0.3"},
      {"name": "indicators", "version": "1.0.4"},
      {"name": "fuzzy", "version": "1.0.2"}
    ]
  }
}
```

## 7. Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| VALIDATION_ERROR | 422 | Invalid request parameters |
| DATA-NotFound | 404 | Requested data not found |
| DATA-LoadError | 400 | Error loading data |
| CONFIG-UnknownIndicator | 400 | Unknown indicator ID |
| CONFIG-InvalidParameter | 400 | Invalid indicator parameter |
| PROC-CalculationFailed | 500 | Error during calculation |
| CONFIG-FuzzyEngineNotInitialized | 400 | Fuzzy engine not initialized |
| CONFIG-UnknownFuzzyIndicator | 400 | Unknown fuzzy indicator |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error |

## 8. Rate Limiting

The API implements rate limiting to ensure fair usage:

- Development mode: 100 requests per minute
- Production mode: Depends on API key tier

Rate limit headers are included in all responses:

- `X-RateLimit-Limit`: Maximum requests per minute
- `X-RateLimit-Remaining`: Remaining requests for the current period
- `X-RateLimit-Reset`: Time (in seconds) until rate limit reset

When a rate limit is exceeded, the API returns:

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please wait before making additional requests.",
    "details": {
      "limit": 100,
      "reset_in": 45
    }
  }
}
```