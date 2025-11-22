# KTRDR API Documentation

## Overview

The KTRDR API provides a RESTful interface for accessing KTRDR trading system functionality. The API is built with FastAPI and follows modern API design principles.

## Getting Started

### Installing Dependencies

Install all dependencies using uv:

```bash
# For production
uv sync --all-extras

# For development and testing
uv sync --all-extras --dev
```

### Running the API Server

There are multiple ways to run the API server:

#### 1. Using the provided script

```bash
# From the project root directory
./scripts/run_api_server.py
```

Command line options:
- `--host`: Host to bind the server (default: 127.0.0.1)
- `--port`: Port to bind the server (default: 8000)
- `--reload`: Enable auto-reload for development
- `--log-level`: Logging level (choices: debug, info, warning, error, critical)
- `--env`: Deployment environment (choices: development, staging, production)

Example:
```bash
./scripts/run_api_server.py --host 0.0.0.0 --port 8080 --log-level debug
```

#### 2. Using Python directly

```bash
# From the project root directory
python -m uvicorn ktrdr.api.main:app --reload
```

#### 3. Using the main module

```bash
# From the project root directory
python -m ktrdr.api.main
```

### API Documentation

Once the server is running, you can access the auto-generated API documentation:

- Swagger UI: http://127.0.0.1:8000/api/v1/docs
- ReDoc: http://127.0.0.1:8000/api/v1/redoc
- OpenAPI JSON: http://127.0.0.1:8000/api/v1/openapi.json

## Environment Variables

The API can be configured using environment variables. These can be set in your shell or in a `.env` file in the project root:

| Variable | Description | Default |
|----------|-------------|---------|
| KTRDR_API_TITLE | API title | "KTRDR API" |
| KTRDR_API_DESCRIPTION | API description | "REST API for KTRDR trading system" |
| KTRDR_API_VERSION | API version | "1.0.5" |
| KTRDR_API_HOST | Host to bind | "127.0.0.1" |
| KTRDR_API_PORT | Port to bind | 8000 |
| KTRDR_API_RELOAD | Enable auto-reload | True |
| KTRDR_API_LOG_LEVEL | Logging level | "INFO" |
| KTRDR_API_ENVIRONMENT | Deployment environment | "development" |
| KTRDR_API_API_PREFIX | API endpoint prefix | "/api/v1" |
| KTRDR_API_CORS_ORIGINS | Allowed CORS origins | ["*"] |

## API Structure and Endpoints

### Data Endpoints

The data endpoints provide access to market data, including price and volume information.

#### GET `/api/v1/symbols`

Returns a list of available trading symbols with metadata.

**Example Response:**
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
    }
  ]
}
```

#### GET `/api/v1/timeframes`

Returns a list of available timeframes for data loading.

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "1d",
      "name": "1 Day",
      "seconds": 86400,
      "description": "Daily data"
    }
  ]
}
```

#### POST `/api/v1/data/load`

Loads OHLCV (Open, High, Low, Close, Volume) data for a specified symbol and timeframe.

**Example Request:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00",
  "end_date": "2023-01-31T23:59:59",
  "include_metadata": true
}
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
    "ohlcv": [
      [125.07, 128.69, 124.17, 126.36, 88115055],
      [127.13, 128.96, 125.08, 126.96, 70790707],
      [127.13, 127.77, 124.76, 125.02, 80643157]
    ],
    "metadata": {
      "symbol": "AAPL",
      "timeframe": "1d",
      "start_date": "2023-01-03",
      "end_date": "2023-01-05",
      "point_count": 3,
      "source": "local_file"
    }
  }
}
```

#### POST `/api/v1/data/range`

Gets the available date range for a symbol and timeframe.

**Example Request:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1d"
}
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "start_date": "2020-01-02T00:00:00",
    "end_date": "2023-04-28T00:00:00",
    "point_count": 840
  }
}
```

### Indicator Endpoints

The indicator endpoints provide access to technical indicators and their calculations.

#### GET `/api/v1/indicators`

Lists all available technical indicators with their metadata, including parameters and default values.

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "RSIIndicator",
      "name": "Relative Strength Index",
      "description": "Momentum oscillator that measures the speed and change of price movements",
      "type": "momentum",
      "parameters": [
        {
          "name": "period",
          "type": "int",
          "description": "Lookback period",
          "default": 14,
          "min_value": 2,
          "max_value": 100,
          "options": null
        },
        {
          "name": "source",
          "type": "str",
          "description": "Source price data to use",
          "default": "close",
          "min_value": null,
          "max_value": null,
          "options": ["close", "open", "high", "low"]
        }
      ]
    }
  ]
}
```

#### POST `/api/v1/indicators/calculate`

Calculates indicator values for a given symbol and timeframe.

**Example Request:**
```json
{
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
  "end_date": "2023-01-31T23:59:59"
}
```

**Example Response:**
```json
{
  "success": true,
  "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
  "indicators": {
    "RSI_14": [48.35, 52.67, 46.89],
    "SMA_20": [126.25, 126.45, 126.32]
  },
  "metadata": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "start_date": "2023-01-03",
    "end_date": "2023-01-05",
    "points": 3,
    "total_items": 3,
    "total_pages": 1,
    "current_page": 1,
    "page_size": 1000,
    "has_next": false,
    "has_prev": false
  }
}
```

### Fuzzy Logic Endpoints

The fuzzy logic endpoints provide access to fuzzy set operations and fuzzification of indicator values.

#### GET `/api/v1/fuzzy/indicators`

Lists all available fuzzy indicators with their fuzzy sets.

**Example Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "rsi",
      "name": "RSI",
      "fuzzy_sets": ["low", "medium", "high"],
      "output_columns": ["rsi_low", "rsi_medium", "rsi_high"]
    }
  ]
}
```

#### GET `/api/v1/fuzzy/sets/{indicator}`

Gets detailed information about fuzzy sets for a specific indicator.

**Example Response:**
```json
{
  "success": true,
  "data": {
    "low": {
      "type": "triangular",
      "parameters": [0, 0, 30]
    },
    "medium": {
      "type": "triangular",
      "parameters": [20, 50, 80]
    },
    "high": {
      "type": "triangular",
      "parameters": [70, 100, 100]
    }
  }
}
```

#### POST `/api/v1/fuzzy/evaluate`

Applies fuzzy membership functions to indicator values.

**Example Request:**
```json
{
  "indicator": "rsi",
  "values": [30.5, 45.2, 68.7, 82.1],
  "dates": ["2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04"]
}
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "indicator": "rsi",
    "fuzzy_sets": ["low", "medium", "high"],
    "values": {
      "rsi_low": [0.78, 0.24, 0.05, 0.0],
      "rsi_medium": [0.22, 0.76, 0.56, 0.12],
      "rsi_high": [0.0, 0.0, 0.39, 0.88]
    },
    "points": 4
  }
}
```

#### POST `/api/v1/fuzzy/data`

Loads data, calculates indicators, and applies fuzzy membership functions in one operation.

**Example Request:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "indicators": [
    {
      "name": "rsi",
      "source_column": "close"
    },
    {
      "name": "macd",
      "source_column": "macd_line"
    }
  ],
  "start_date": "2023-01-01T00:00:00",
  "end_date": "2023-01-31T23:59:59"
}
```

**Example Response:**
```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "dates": ["2023-01-03", "2023-01-04", "2023-01-05"],
    "indicators": {
      "rsi": {
        "rsi_low": [0.78, 0.24, 0.05],
        "rsi_medium": [0.22, 0.76, 0.56],
        "rsi_high": [0.0, 0.0, 0.39]
      },
      "macd": {
        "macd_negative": [0.85, 0.62, 0.31],
        "macd_neutral": [0.15, 0.38, 0.69],
        "macd_positive": [0.0, 0.0, 0.0]
      }
    },
    "metadata": {
      "start_date": "2023-01-03",
      "end_date": "2023-01-05",
      "points": 3
    }
  }
}
```

## Error Handling

The API provides consistent error responses with the following structure:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional": "error details"
    }
  }
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| VALIDATION_ERROR | 422 | Invalid request parameters |
| DATA-NotFound | 404 | Requested data not found |
| DATA-LoadError | 400 | Error loading data |
| CONFIG-UnknownIndicator | 400 | Unknown indicator ID |
| PROC-CalculationFailed | 500 | Error during calculation |
| CONFIG-FuzzyEngineNotInitialized | 400 | Fuzzy engine not initialized |
| CONFIG-UnknownFuzzyIndicator | 400 | Unknown fuzzy indicator |

## Schema Validation

The API uses Pydantic models for request and response validation. Each endpoint has specific validation rules:

### Data Models

- `symbol`: Must be a non-empty string
- `timeframe`: Must be one of the supported timeframes (e.g., '1m', '1h', '1d')
- `start_date` and `end_date`: Must be valid ISO format datetime strings

### Indicator Models

- `period`: Must be a positive integer within the allowed range for each indicator
- `source`: Must be one of the supported source columns (e.g., 'close', 'open')
- `id`: Must refer to a valid, registered indicator

### Fuzzy Models

- `indicator`: Must refer to a valid fuzzy indicator with configured fuzzy sets
- `values`: Must be a non-empty array of numeric values

## Best Practices

### Performance Optimization

- Use pagination for large datasets with the `page` and `page_size` parameters
- Request only the data you need by specifying appropriate date ranges
- Consider using `/api/v1/data/range` to get available date ranges before loading full data

### Error Handling

- Always check the `success` field in responses
- Handle error responses appropriately with proper error messages to the user
- Implement retry logic with backoff for transient errors

### Authentication

Future versions of the API will require authentication. Currently, the API is designed to accommodate API keys via the `X-API-Key` header.

## Testing

To run the API tests:

```bash
# From the project root directory
python -m pytest tests/api/
```

## Examples

Additional API usage examples can be found in the `examples/` directory:

- `examples/api_models_example.py`: Examples of using the API models
- `examples/indicator_api_examples.py`: Examples of interacting with indicator endpoints