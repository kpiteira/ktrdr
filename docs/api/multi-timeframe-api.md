# 🌐 Multi-Timeframe API Reference

## Overview

The Multi-Timeframe API provides REST endpoints for generating trading decisions across multiple timeframes, analyzing performance, and managing multi-timeframe configurations.

**Base URL**: `http://localhost:8000/api/v1/multi-timeframe-decisions`

## Table of Contents

1. [Authentication](#authentication)
2. [Endpoints](#endpoints)
3. [Request/Response Models](#requestresponse-models)
4. [Error Handling](#error-handling)
5. [Rate Limiting](#rate-limiting)
6. [Examples](#examples)

---

## 🔐 Authentication

Currently, the API uses no authentication in development mode. For production deployment, implement your preferred authentication method (JWT, API keys, etc.).

---

## 📡 Endpoints

### 1. Generate Decision

Generate a multi-timeframe trading decision for a symbol.

**Endpoint**: `POST /decide`

**Request Body**:
```json
{
  "symbol": "AAPL",
  "strategy_config_path": "strategies/my_strategy.yaml",
  "timeframes": ["1h", "4h", "1d"],
  "mode": "backtest",
  "model_path": "models/my_model.pt",
  "portfolio_state": {
    "total_value": 100000.0,
    "available_capital": 50000.0,
    "positions": {},
    "risk_exposure": 0.0
  }
}
```

**Response**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2024-01-15T10:30:00Z",
  "decision": {
    "signal": "BUY",
    "confidence": 0.85,
    "current_position": "FLAT",
    "reasoning": {
      "consensus_method": "weighted_majority",
      "timeframe_scores": {
        "1h": {"signal": "BUY", "confidence": 0.9},
        "4h": {"signal": "BUY", "confidence": 0.8},
        "1d": {"signal": "HOLD", "confidence": 0.6}
      },
      "multi_timeframe_metadata": {
        "data_quality_score": 0.95,
        "consensus_strength": 0.82
      }
    }
  },
  "consensus": {
    "method": "weighted_majority",
    "agreement_score": 0.82,
    "conflicting_timeframes": [],
    "primary_timeframe": "4h",
    "primary_timeframe_weight": 0.3,
    "timeframe_weights": {
      "1h": 0.5,
      "4h": 0.3,
      "1d": 0.2
    }
  },
  "metadata": {
    "processing_time_ms": 150,
    "timeframes_analyzed": ["1h", "4h", "1d"],
    "data_quality_score": 0.95,
    "model_used": true,
    "indicators_used": ["rsi", "sma", "ema"]
  }
}
```

---

### 2. Analyze Performance

Analyze multi-timeframe decision performance and consensus patterns.

**Endpoint**: `POST /analyze`

**Request Body**:
```json
{
  "symbol": "AAPL",
  "strategy_config_path": "strategies/my_strategy.yaml",
  "timeframes": ["1h", "4h", "1d"],
  "mode": "backtest",
  "analysis_params": {
    "history_limit": 50,
    "include_consensus_breakdown": true,
    "include_performance_metrics": true
  }
}
```

**Response**:
```json
{
  "symbol": "AAPL",
  "analysis_timestamp": "2024-01-15T10:30:00Z",
  "timeframes": ["1h", "4h", "1d"],
  "primary_timeframe": "4h",
  "timeframe_weights": {
    "1h": 0.5,
    "4h": 0.3,
    "1d": 0.2
  },
  "consensus_analysis": {
    "total_decisions": 50,
    "consensus_distribution": {
      "unanimous": 20,
      "majority": 25,
      "split": 5
    },
    "agreement_score_avg": 0.78,
    "conflicting_decisions": 8
  },
  "performance_metrics": {
    "avg_confidence": 0.75,
    "signal_distribution": {
      "BUY": 18,
      "SELL": 12,
      "HOLD": 20
    },
    "avg_processing_time_ms": 145,
    "data_quality_avg": 0.92
  },
  "timeframe_performance": {
    "1h": {
      "decisions_count": 50,
      "avg_confidence": 0.82,
      "signal_strength": 0.78
    },
    "4h": {
      "decisions_count": 50,
      "avg_confidence": 0.75,
      "signal_strength": 0.71
    },
    "1d": {
      "decisions_count": 50,
      "avg_confidence": 0.68,
      "signal_strength": 0.65
    }
  },
  "recent_decisions_count": 50
}
```

---

### 3. Check Data Status

Check data availability and quality across timeframes.

**Endpoint**: `GET /status/{symbol}`

**Query Parameters**:
- `timeframes`: Comma-separated list (e.g., "1h,4h,1d")
- `lookback`: Number of periods to check (default: 100)

**Example**: `GET /status/AAPL?timeframes=1h,4h,1d&lookback=200`

**Response**:
```json
{
  "symbol": "AAPL",
  "timestamp": "2024-01-15T10:30:00Z",
  "timeframes": ["1h", "4h", "1d"],
  "data_status": {
    "1h": {
      "available": true,
      "data_points": 200,
      "quality_score": 0.95,
      "last_update": "2024-01-15T10:00:00Z",
      "freshness_score": 0.98,
      "completeness": 0.96,
      "missing_periods": 8
    },
    "4h": {
      "available": true,
      "data_points": 50,
      "quality_score": 0.92,
      "last_update": "2024-01-15T08:00:00Z",
      "freshness_score": 0.95,
      "completeness": 0.94,
      "missing_periods": 3
    },
    "1d": {
      "available": true,
      "data_points": 12,
      "quality_score": 0.98,
      "last_update": "2024-01-15T00:00:00Z",
      "freshness_score": 0.92,
      "completeness": 1.0,
      "missing_periods": 0
    }
  },
  "overall_quality": 0.95,
  "recommendations": [
    "Data quality is excellent across all timeframes",
    "Consider refreshing 4h data for better freshness"
  ]
}
```

---

### 4. Batch Operations

Generate decisions for multiple symbols simultaneously.

**Endpoint**: `POST /batch`

**Request Body**:
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "strategy_config_path": "strategies/my_strategy.yaml",
  "timeframes": ["1h", "4h", "1d"],
  "mode": "backtest",
  "portfolio_state": {
    "total_value": 300000.0,
    "available_capital": 150000.0
  },
  "batch_params": {
    "max_concurrent": 3,
    "timeout_seconds": 30
  }
}
```

**Response**:
```json
{
  "batch_id": "batch_20240115_103000_abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "symbols_processed": 3,
  "symbols_failed": 0,
  "total_processing_time_ms": 450,
  "results": [
    {
      "symbol": "AAPL",
      "decision": {
        "signal": "BUY",
        "confidence": 0.85,
        "current_position": "FLAT"
      },
      "consensus": {
        "agreement_score": 0.82
      },
      "processing_time_ms": 150
    },
    {
      "symbol": "MSFT",
      "decision": {
        "signal": "HOLD",
        "confidence": 0.65,
        "current_position": "FLAT"
      },
      "consensus": {
        "agreement_score": 0.68
      },
      "processing_time_ms": 140
    },
    {
      "symbol": "GOOGL",
      "decision": {
        "signal": "SELL",
        "confidence": 0.78,
        "current_position": "FLAT"
      },
      "consensus": {
        "agreement_score": 0.75
      },
      "processing_time_ms": 160
    }
  ],
  "failed_symbols": [],
  "summary": {
    "signals": {
      "BUY": 1,
      "SELL": 1,
      "HOLD": 1
    },
    "avg_confidence": 0.76,
    "avg_agreement_score": 0.75
  }
}
```

---

### 5. Get Timeframe Configuration

Retrieve timeframe configuration from a strategy file.

**Endpoint**: `GET /config/timeframes`

**Query Parameters**:
- `strategy_path`: Path to strategy configuration file

**Example**: `GET /config/timeframes?strategy_path=strategies/my_strategy.yaml`

**Response**:
```json
{
  "strategy_name": "my_multi_timeframe_strategy",
  "timeframes": ["1h", "4h", "1d"],
  "timeframe_configs": {
    "1h": {
      "weight": 0.5,
      "primary": false,
      "lookback_periods": 50,
      "min_data_quality": 0.8
    },
    "4h": {
      "weight": 0.3,
      "primary": true,
      "lookback_periods": 30,
      "min_data_quality": 0.9
    },
    "1d": {
      "weight": 0.2,
      "primary": false,
      "lookback_periods": 20,
      "min_data_quality": 0.85
    }
  },
  "multi_timeframe_settings": {
    "consensus_method": "weighted_majority",
    "min_agreement_score": 0.6,
    "conflicting_signal_resolution": "favor_primary"
  }
}
```

---

## 📋 Request/Response Models

### MultiTimeframeDecisionRequest

```typescript
interface MultiTimeframeDecisionRequest {
  symbol: string;                    // Trading symbol (e.g., "AAPL")
  strategy_config_path: string;      // Path to strategy YAML file
  timeframes: string[];              // List of timeframes (["1h", "4h", "1d"])
  mode: "backtest" | "paper" | "live"; // Trading mode
  model_path?: string;               // Optional neural model path
  portfolio_state: PortfolioState;   // Current portfolio state
}

interface PortfolioState {
  total_value: number;               // Total portfolio value
  available_capital: number;         // Available capital for trading
  positions: Record<string, any>;    // Current positions
  risk_exposure: number;             // Current risk exposure (0.0-1.0)
}
```

### MultiTimeframeDecisionResponse

```typescript
interface MultiTimeframeDecisionResponse {
  symbol: string;
  timestamp: string;                 // ISO 8601 timestamp
  decision: TradingDecision;
  consensus: ConsensusInfo;
  metadata: DecisionMetadata;
}

interface TradingDecision {
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;                // 0.0 to 1.0
  current_position: "FLAT" | "LONG" | "SHORT";
  reasoning: Record<string, any>;    // Decision reasoning details
}

interface ConsensusInfo {
  method: string;                    // Consensus method used
  agreement_score: number;           // 0.0 to 1.0
  conflicting_timeframes: string[];  // Timeframes with conflicting signals
  primary_timeframe: string;         // Primary timeframe identifier
  primary_timeframe_weight: number;  // Weight of primary timeframe
  timeframe_weights: Record<string, number>; // All timeframe weights
}

interface DecisionMetadata {
  processing_time_ms: number;        // Processing time in milliseconds
  timeframes_analyzed: string[];     // Timeframes included in analysis
  data_quality_score: number;        // Overall data quality (0.0-1.0)
  model_used: boolean;               // Whether neural model was used
  indicators_used: string[];         // List of indicators analyzed
}
```

---

## ⚠️ Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid timeframe specified",
    "details": {
      "field": "timeframes",
      "value": "invalid_tf",
      "allowed_values": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123"
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Invalid request parameters | 400 |
| `STRATEGY_NOT_FOUND` | Strategy file not found | 404 |
| `DATA_UNAVAILABLE` | Required data not available | 422 |
| `PROCESSING_ERROR` | Error during decision generation | 500 |
| `TIMEOUT_ERROR` | Request timeout | 504 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |

### Error Examples

#### Invalid Symbol
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid symbol format",
    "details": {
      "field": "symbol",
      "value": "INVALID@SYMBOL",
      "pattern": "^[A-Za-z0-9\\-\\.]+$"
    }
  }
}
```

#### Missing Data
```json
{
  "error": {
    "code": "DATA_UNAVAILABLE",
    "message": "Insufficient data for decision generation",
    "details": {
      "symbol": "AAPL",
      "timeframe": "1h",
      "required_periods": 50,
      "available_periods": 10
    }
  }
}
```

#### Strategy File Error
```json
{
  "error": {
    "code": "STRATEGY_NOT_FOUND",
    "message": "Strategy configuration file not found",
    "details": {
      "path": "strategies/nonexistent.yaml",
      "suggestions": [
        "strategies/mean_reversion_strategy.yaml",
        "strategies/trend_momentum_strategy.yaml"
      ]
    }
  }
}
```

---

## 🚦 Rate Limiting

### Current Limits

- **Decision Generation**: 60 requests per minute per IP
- **Batch Operations**: 10 requests per minute per IP
- **Status Checks**: 120 requests per minute per IP
- **Analysis**: 30 requests per minute per IP

### Rate Limit Headers

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1642234800
X-RateLimit-Window: 60
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 60,
      "window_seconds": 60,
      "retry_after_seconds": 15
    }
  }
}
```

---

## 💡 Examples

### Python Client Example

```python
import requests
import json

class MultiTimeframeClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = f"{base_url}/api/v1/multi-timeframe-decisions"
    
    def generate_decision(self, symbol, strategy_path, timeframes, mode="backtest"):
        """Generate a multi-timeframe trading decision."""
        payload = {
            "symbol": symbol,
            "strategy_config_path": strategy_path,
            "timeframes": timeframes,
            "mode": mode,
            "portfolio_state": {
                "total_value": 100000.0,
                "available_capital": 50000.0,
                "positions": {},
                "risk_exposure": 0.0
            }
        }
        
        response = requests.post(f"{self.base_url}/decide", json=payload)
        response.raise_for_status()
        return response.json()
    
    def check_status(self, symbol, timeframes, lookback=100):
        """Check data status for symbol across timeframes."""
        params = {
            "timeframes": ",".join(timeframes),
            "lookback": lookback
        }
        
        response = requests.get(f"{self.base_url}/status/{symbol}", params=params)
        response.raise_for_status()
        return response.json()
    
    def analyze_performance(self, symbol, strategy_path, timeframes, history_limit=50):
        """Analyze multi-timeframe performance."""
        payload = {
            "symbol": symbol,
            "strategy_config_path": strategy_path,
            "timeframes": timeframes,
            "mode": "backtest",
            "analysis_params": {
                "history_limit": history_limit,
                "include_consensus_breakdown": True,
                "include_performance_metrics": True
            }
        }
        
        response = requests.post(f"{self.base_url}/analyze", json=payload)
        response.raise_for_status()
        return response.json()
    
    def batch_decisions(self, symbols, strategy_path, timeframes):
        """Generate decisions for multiple symbols."""
        payload = {
            "symbols": symbols,
            "strategy_config_path": strategy_path,
            "timeframes": timeframes,
            "mode": "backtest",
            "portfolio_state": {
                "total_value": 300000.0,
                "available_capital": 150000.0
            }
        }
        
        response = requests.post(f"{self.base_url}/batch", json=payload)
        response.raise_for_status()
        return response.json()

# Usage example
client = MultiTimeframeClient()

# Generate decision
decision = client.generate_decision(
    symbol="AAPL",
    strategy_path="strategies/my_strategy.yaml",
    timeframes=["1h", "4h", "1d"]
)
print(f"Decision: {decision['decision']['signal']} with confidence {decision['decision']['confidence']}")

# Check data status
status = client.check_status("AAPL", ["1h", "4h", "1d"])
print(f"Overall quality: {status['overall_quality']}")

# Analyze performance
analysis = client.analyze_performance(
    symbol="AAPL",
    strategy_path="strategies/my_strategy.yaml",
    timeframes=["1h", "4h", "1d"],
    history_limit=100
)
print(f"Average confidence: {analysis['performance_metrics']['avg_confidence']}")
```

### JavaScript/TypeScript Client Example

```typescript
interface MultiTimeframeClient {
  baseUrl: string;
}

class MultiTimeframeClient {
  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = `${baseUrl}/api/v1/multi-timeframe-decisions`;
  }

  async generateDecision(
    symbol: string,
    strategyPath: string,
    timeframes: string[],
    mode: "backtest" | "paper" | "live" = "backtest"
  ) {
    const payload = {
      symbol,
      strategy_config_path: strategyPath,
      timeframes,
      mode,
      portfolio_state: {
        total_value: 100000.0,
        available_capital: 50000.0,
        positions: {},
        risk_exposure: 0.0
      }
    };

    const response = await fetch(`${this.baseUrl}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async checkStatus(symbol: string, timeframes: string[], lookback: number = 100) {
    const params = new URLSearchParams({
      timeframes: timeframes.join(','),
      lookback: lookback.toString()
    });

    const response = await fetch(`${this.baseUrl}/status/${symbol}?${params}`);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async batchDecisions(symbols: string[], strategyPath: string, timeframes: string[]) {
    const payload = {
      symbols,
      strategy_config_path: strategyPath,
      timeframes,
      mode: "backtest",
      portfolio_state: {
        total_value: 300000.0,
        available_capital: 150000.0
      }
    };

    const response = await fetch(`${this.baseUrl}/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }
}

// Usage example
const client = new MultiTimeframeClient();

// Generate decision
const decision = await client.generateDecision(
  "AAPL",
  "strategies/my_strategy.yaml",
  ["1h", "4h", "1d"]
);
console.log(`Decision: ${decision.decision.signal} with confidence ${decision.decision.confidence}`);
```

### cURL Examples

```bash
# Generate decision
curl -X POST "http://localhost:8000/api/v1/multi-timeframe-decisions/decide" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy_config_path": "strategies/my_strategy.yaml",
    "timeframes": ["1h", "4h", "1d"],
    "mode": "backtest",
    "portfolio_state": {
      "total_value": 100000,
      "available_capital": 50000,
      "positions": {},
      "risk_exposure": 0.0
    }
  }'

# Check status
curl "http://localhost:8000/api/v1/multi-timeframe-decisions/status/AAPL?timeframes=1h,4h,1d&lookback=100"

# Batch decisions
curl -X POST "http://localhost:8000/api/v1/multi-timeframe-decisions/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "strategy_config_path": "strategies/my_strategy.yaml",
    "timeframes": ["1h", "4h", "1d"],
    "mode": "backtest"
  }'
```

---

## 🔗 Related Documentation

- [Multi-Timeframe Trading Guide](../user-guides/multi-timeframe-trading.md)
- [Strategy Configuration](../configuration/multi-timeframe-strategies.md)
- [CLI Commands](../cli/multi-timeframe-commands.md)
- [Error Handling Guide](../troubleshooting/api-errors.md)

---

*For more information, check the [API documentation home](./index.md) or visit the [getting started guide](../getting-started/quickstart.md).*