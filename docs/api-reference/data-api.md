# Data API

The Data API provides endpoints for retrieving market data, available symbols, and timeframes.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/symbols` | GET | List all available trading symbols |
| `/api/v1/timeframes` | GET | List all available timeframes |
| `/api/v1/data/load` | POST | Load OHLCV data for a symbol and timeframe |
| `/api/v1/data/latest` | GET | Get the latest data point for a symbol |
| `/api/v1/data/status` | GET | Check data availability and freshness |

## Get Available Symbols

**Endpoint:** `GET /api/v1/symbols`

Returns a list of all available trading symbols with their metadata.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `asset_type` | string | No | Filter by asset type (e.g., "stock", "forex", "crypto") |

### Response

```json
{
  "success": true,
  "data": {
    "symbols": [
      {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "asset_type": "stock",
        "exchange": "NASDAQ"
      },
      {
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "asset_type": "stock",
        "exchange": "NASDAQ"
      },
      {
        "symbol": "EURUSD",
        "name": "Euro / US Dollar",
        "asset_type": "forex",
        "exchange": "IDEALPRO"
      }
    ]
  }
}
```

## Get Available Timeframes

**Endpoint:** `GET /api/v1/timeframes`

Returns a list of available timeframes for data retrieval.

### Response

```json
{
  "success": true,
  "data": {
    "timeframes": [
      {
        "id": "1m",
        "description": "1 Minute"
      },
      {
        "id": "5m",
        "description": "5 Minutes"
      },
      {
        "id": "15m",
        "description": "15 Minutes"
      },
      {
        "id": "1h",
        "description": "1 Hour"
      },
      {
        "id": "1d",
        "description": "1 Day"
      }
    ]
  }
}
```

## Load Historical Data

**Endpoint:** `POST /api/v1/data/load`

Load historical OHLCV (Open, High, Low, Close, Volume) data for a specified symbol and timeframe.

### Request Body

```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-12-31T23:59:59Z",
  "source": "auto"
}
```

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `symbol` | string | Yes | Trading symbol (e.g., "AAPL", "EURUSD") |
| `timeframe` | string | Yes | Data timeframe (e.g., "1m", "1h", "1d") |
| `start_date` | string | No | Start date in ISO 8601 format (default: 1 year ago) |
| `end_date` | string | No | End date in ISO 8601 format (default: current time) |
| `source` | string | No | Data source: "local", "ib" (Interactive Brokers), or "auto" (default) |

### Response

```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "start_date": "2023-01-01T00:00:00Z",
    "end_date": "2023-12-31T23:59:59Z",
    "points": 252,
    "ohlcv": [
      {
        "timestamp": "2023-01-03T00:00:00Z",
        "open": 130.28,
        "high": 130.90,
        "low": 124.17,
        "close": 125.07,
        "volume": 112117500
      },
      // Additional data points...
    ],
    "metadata": {
      "source": "local",
      "last_updated": "2024-05-01T12:34:56Z",
      "timezone": "UTC"
    }
  }
}
```

## Get Latest Data

**Endpoint:** `GET /api/v1/data/latest`

Get the latest data point for a specified symbol and timeframe.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | string | Yes | Trading symbol (e.g., "AAPL", "EURUSD") |
| `timeframe` | string | Yes | Data timeframe (e.g., "1m", "1h", "1d") |

### Response

```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "timestamp": "2023-12-29T00:00:00Z",
    "open": 193.61,
    "high": 194.40,
    "low": 191.09,
    "close": 192.53,
    "volume": 51580400,
    "metadata": {
      "last_updated": "2024-05-01T12:34:56Z",
      "is_market_open": false
    }
  }
}
```

## Check Data Status

**Endpoint:** `GET /api/v1/data/status`

Check data availability and freshness for a specified symbol and timeframe.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | string | Yes | Trading symbol (e.g., "AAPL", "EURUSD") |
| `timeframe` | string | Yes | Data timeframe (e.g., "1m", "1h", "1d") |

### Response

```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
    "available": true,
    "first_date": "2010-01-04T00:00:00Z",
    "last_date": "2023-12-29T00:00:00Z",
    "total_points": 3521,
    "last_updated": "2024-05-01T12:34:56Z",
    "requires_update": false,
    "gaps": []
  }
}
```

## Error Responses

### Symbol Not Found

```json
{
  "success": false,
  "error": {
    "code": "DATA_NOT_FOUND",
    "message": "Symbol 'INVALID' not found",
    "details": {
      "symbol": "INVALID"
    }
  }
}
```

### Invalid Timeframe

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "Invalid timeframe '2d'",
    "details": {
      "timeframe": "2d",
      "valid_timeframes": ["1m", "5m", "15m", "1h", "1d"]
    }
  }
}
```

### No Data Available

```json
{
  "success": false,
  "error": {
    "code": "DATA_NOT_FOUND",
    "message": "No data available for AAPL with timeframe 1m in the specified date range",
    "details": {
      "symbol": "AAPL",
      "timeframe": "1m",
      "start_date": "2010-01-01T00:00:00Z",
      "end_date": "2010-01-31T23:59:59Z"
    }
  }
}
```

## Examples

### Fetch AAPL Daily Data for 2023

```bash
curl -X POST "http://localhost:8000/api/v1/data/load" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{
           "symbol": "AAPL",
           "timeframe": "1d",
           "start_date": "2023-01-01T00:00:00Z",
           "end_date": "2023-12-31T23:59:59Z"
         }'
```

### Check if EURUSD Data is Up-to-Date

```bash
curl -X GET "http://localhost:8000/api/v1/data/status?symbol=EURUSD&timeframe=1h" \
     -H "X-API-Key: your-api-key"
```