# Indicator API

The Indicator API provides endpoints for calculating technical indicators on financial data and managing indicator configurations.

## Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/indicators` | GET | List all available technical indicators |
| `/api/v1/indicators/calculate` | POST | Calculate indicators on provided data |
| `/api/v1/indicators/defaults` | GET | Get default parameters for indicators |
| `/api/v1/indicators/{indicator_name}/info` | GET | Get detailed information about an indicator |

## List Available Indicators

**Endpoint:** `GET /api/v1/indicators`

Returns a list of all available technical indicators with basic metadata.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category (e.g., "trend", "momentum", "volatility") |

### Response

```json
{
  "success": true,
  "data": {
    "indicators": [
      {
        "name": "sma",
        "display_name": "Simple Moving Average",
        "category": "trend",
        "description": "Calculates the arithmetic mean of price over a specified period"
      },
      {
        "name": "ema",
        "display_name": "Exponential Moving Average",
        "category": "trend",
        "description": "Moving average that gives more weight to recent prices"
      },
      {
        "name": "rsi",
        "display_name": "Relative Strength Index",
        "category": "momentum",
        "description": "Momentum oscillator that measures the speed and change of price movements"
      },
      {
        "name": "macd",
        "display_name": "Moving Average Convergence Divergence",
        "category": "trend",
        "description": "Trend-following momentum indicator showing relationship between two moving averages"
      },
      {
        "name": "bollinger_bands",
        "display_name": "Bollinger Bands",
        "category": "volatility",
        "description": "Volatility bands placed above and below a moving average"
      }
    ]
  }
}
```

## Calculate Indicators

**Endpoint:** `POST /api/v1/indicators/calculate`

Calculate one or more technical indicators on provided OHLCV data.

### Request Body

```json
{
  "data": {
    "symbol": "AAPL",
    "timeframe": "1d",
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
    ]
  },
  "indicators": [
    {
      "name": "sma",
      "parameters": {
        "period": 20,
        "source": "close"
      }
    },
    {
      "name": "rsi",
      "parameters": {
        "period": 14,
        "source": "close"
      }
    }
  ]
}
```

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `data` | object | Yes | OHLCV data to calculate indicators on |
| `data.symbol` | string | No | Symbol identifier (optional) |
| `data.timeframe` | string | No | Data timeframe (optional) |
| `data.ohlcv` | array | Yes | Array of OHLCV data points |
| `indicators` | array | Yes | Array of indicator configurations |
| `indicators[].name` | string | Yes | Indicator name |
| `indicators[].parameters` | object | No | Indicator-specific parameters |

### Response

```json
{
  "success": true,
  "data": {
    "input": {
      "symbol": "AAPL",
      "timeframe": "1d",
      "points": 252
    },
    "results": {
      "sma_20_close": [
        null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
        126.58, 127.11, 127.83, 128.21, 128.69, 129.56, 130.54, 131.14, 131.96, 132.90, 133.89, 134.30,
        // Additional values...
      ],
      "rsi_14_close": [
        null, null, null, null, null, null, null, null, null, null, null, null, null,
        41.43, 45.28, 52.69, 55.21, 45.98, 40.63, 42.38, 46.91, 53.07, 58.61, 62.04, 65.43, 66.89, 62.38, 65.56, 68.43, 71.94,
        // Additional values...
      ]
    },
    "metadata": {
      "sma_20_close": {
        "indicator": "sma",
        "parameters": {
          "period": 20,
          "source": "close"
        },
        "warmup_period": 19,
        "min_data_points": 20
      },
      "rsi_14_close": {
        "indicator": "rsi",
        "parameters": {
          "period": 14,
          "source": "close"
        },
        "warmup_period": 13,
        "min_data_points": 14
      }
    }
  }
}
```

## Get Default Parameters

**Endpoint:** `GET /api/v1/indicators/defaults`

Get default parameters for all available indicators.

### Response

```json
{
  "success": true,
  "data": {
    "sma": {
      "period": 20,
      "source": "close"
    },
    "ema": {
      "period": 20,
      "source": "close"
    },
    "rsi": {
      "period": 14,
      "source": "close"
    },
    "macd": {
      "fast_period": 12,
      "slow_period": 26,
      "signal_period": 9,
      "source": "close"
    },
    "bollinger_bands": {
      "period": 20,
      "std_dev": 2.0,
      "source": "close"
    }
  }
}
```

## Get Indicator Information

**Endpoint:** `GET /api/v1/indicators/{indicator_name}/info`

Get detailed information about a specific indicator, including description, parameters, and usage examples.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `indicator_name` | string | Yes | The name of the indicator to get information for |

### Response

```json
{
  "success": true,
  "data": {
    "name": "rsi",
    "display_name": "Relative Strength Index",
    "category": "momentum",
    "description": "The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and change of price movements. The RSI oscillates between zero and 100. Traditionally, the RSI is considered overbought when above 70 and oversold when below 30.",
    "parameters": [
      {
        "name": "period",
        "type": "integer",
        "default": 14,
        "min": 2,
        "max": 100,
        "description": "The number of periods used for RSI calculation"
      },
      {
        "name": "source",
        "type": "string",
        "default": "close",
        "options": ["open", "high", "low", "close"],
        "description": "The price source to use for calculation"
      }
    ],
    "output": [
      {
        "name": "rsi",
        "description": "RSI values between 0 and 100",
        "min": 0,
        "max": 100
      }
    ],
    "examples": [
      {
        "description": "Overbought/Oversold Levels",
        "details": "RSI values above 70 are traditionally considered overbought, while values below 30 are considered oversold."
      },
      {
        "description": "Divergence",
        "details": "Divergence between RSI and price can signal potential reversals. For example, if price makes a higher high but RSI makes a lower high, this can signal bearish divergence."
      }
    ],
    "formula": "RSI = 100 - (100 / (1 + RS))\nwhere RS = Average Gain / Average Loss",
    "references": [
      {
        "title": "Original Paper by J. Welles Wilder",
        "url": "https://example.com/rsi-paper"
      }
    ]
  }
}
```

## Error Responses

### Indicator Not Found

```json
{
  "success": false,
  "error": {
    "code": "INDICATOR_NOT_FOUND",
    "message": "Indicator 'invalid_indicator' not found",
    "details": {
      "indicator": "invalid_indicator",
      "available_indicators": ["sma", "ema", "rsi", "macd", "bollinger_bands"]
    }
  }
}
```

### Invalid Parameters

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "Invalid parameter 'period' for indicator 'rsi'",
    "details": {
      "indicator": "rsi",
      "parameter": "period",
      "error": "Value must be between 2 and 100",
      "value": 1
    }
  }
}
```

### Insufficient Data

```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Insufficient data for indicator calculation",
    "details": {
      "indicator": "sma",
      "required_points": 20,
      "provided_points": 15
    }
  }
}
```

## Examples

### Calculate RSI and Bollinger Bands

```bash
curl -X POST "http://localhost:8000/api/v1/indicators/calculate" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your-api-key" \
     -d '{
           "data": {
             "symbol": "AAPL",
             "timeframe": "1d",
             "ohlcv": [
               // OHLCV data...
             ]
           },
           "indicators": [
             {
               "name": "rsi",
               "parameters": {
                 "period": 14,
                 "source": "close"
               }
             },
             {
               "name": "bollinger_bands",
               "parameters": {
                 "period": 20,
                 "std_dev": 2.0,
                 "source": "close"
               }
             }
           ]
         }'
```

### Get Default Parameters

```bash
curl -X GET "http://localhost:8000/api/v1/indicators/defaults" \
     -H "X-API-Key: your-api-key"
```